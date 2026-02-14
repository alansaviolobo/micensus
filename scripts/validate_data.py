import csv
import io
import urllib.request
from datetime import datetime
import re
import psycopg2
import pandas as pd
import os

def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

load_env()
URL = os.getenv("GSHEET_URL")
INPUT_FILE = os.getenv("INPUT_FILE")
OUTPUT_FILE = os.getenv("OUTPUT_FILE")
REVERT_FILE = os.getenv("REVERT_FILE")


def log(message):
    """Prints message to console and appends to output file."""
    print(message)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")

# DB Config
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")
SSLMODE = os.getenv("SSLMODE")

def fetch_csv(url):
    try:
        response = urllib.request.urlopen(url)
        return response.read().decode('utf-8')
    except Exception as e:
        print(f"Failed to fetch CSV: {e}")
        return None

def get_db_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT,
            sslmode=SSLMODE
        )
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

# --- Validators ---

def validate_required(value, name):
    if not value or str(value).strip() == "":
        return f"{name} is required."
    return True

def validate_regex(value, pattern, name, error_msg=None):
    if not value: return True 
    if not re.match(pattern, str(value)):
        return error_msg or f"{name} has invalid format."
    return True

def validate_numeric(value, name, min_val=None, max_val=None, custom_error=None):
    if not value or str(value).strip() == "": return True
    try:
        val = float(value)
        if min_val is not None and val < min_val:
            return custom_error or f"{name} must be >= {min_val}."
        if max_val is not None and val > max_val:
            return custom_error or f"{name} must be <= {max_val}."
        return True
    except ValueError:
        return f"{name} must be a number."

def validate_date(value, name, fmt="%Y-%m-%d %H:%M:%S"):
    if not value or str(value).strip() == "": return True
    try:
        datetime.strptime(str(value).strip(), fmt)
        return True
    except ValueError:
        return f"{name} must be in format {fmt}."

def validate_enum(value, options, name):
    if not value or str(value).strip() == "": return True
    if str(value).strip().lower() not in [o.lower() for o in options]:
        return f"{name} must be one of {options}."
    return True

def validate_url(value, name):
    if not value or str(value).strip() == "": return True
    if not str(value).strip().startswith("http"):
        return f"{name} must be a valid URL starting with http/https."
    return True

def validate_location_in_db(cursor, lat, lon, taluka, village):
    try:
        # Normalize village name using translation table if exists
        search_village = VILLAGE_TRANSLATIONS.get(village, village)

        # Normalize names: remove (CT) and other suffixes if necessary for broader matching
        # But first try exact match (case insensitive)
        
        # Check if point is inside the specific village and taluka polygon
        query = """
            SELECT village, taluka 
            FROM dslr.village_boundaries 
            WHERE ST_Contains(
                ST_Transform(geom, 4326), 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            )
            AND LOWER(taluka) = LOWER(%s)
            AND (
                LOWER(village) = LOWER(%s)
                OR LOWER(REPLACE(village, ' (Ct)', '')) = LOWER(REPLACE(%s, ' (Ct)', ''))
            )
            LIMIT 1
        """
        cursor.execute(query, (lon, lat, taluka, search_village, search_village))
        result = cursor.fetchone()
        
        if result:
            return True, f"{result[0]}, {result[1]}"
        
        # If not found in the specific village/taluka, check where it actually falls
        query_any = """
            SELECT village, taluka 
            FROM dslr.village_boundaries 
            WHERE ST_Contains(
                ST_Transform(geom, 4326), 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            )
            LIMIT 1
        """
        cursor.execute(query_any, (lon, lat))
        actual_loc = cursor.fetchone()
        
        if actual_loc:
            return False, f"Point falls in {actual_loc[0]}, {actual_loc[1]} instead of {village}, {taluka}"
        return False, f"Point falls outside all village boundaries (Expected: {village}, {taluka})"
    except Exception as e:
        return False, f"Geospatial check failed: {e}"

# ... (imports and existing functions remain similar, but adding WHITELIST and new validator)

# ... (imports)

# Whitelists
VILLAGE_TRANSLATIONS = {
    "Naqueri": "Naquerim",
    "Molcornem": "Molcarnem",
    "Nagorcem - Palolem" : "Nagorcem-Palolem",
    "Colomb" : "Colomba",
    "Porteem" : "Portem",
    "Kurpem" : "Curpem",
    "Cunchelim" : "Mapusa",
    "" : "",
    "" : "",
    "" : "",
}

WHITELIST_SPRING_NATURE = [
    'S-U-30-552-252082-932927-01',
    'S-R-30-552-5932-626864-04',
    'S-R-30-552-5932-626865-01',
    'S-R-30-552-5932-626868-04',
    'S-R-30-552-5932-626846-06',
    'S-R-30-552-5932-626861-05',
    'S-R-30-552-5932-626859-01',
    'S-R-30-552-5932-626861-03',
    'S-R-30-552-5932-626857-01',
    'S-R-30-552-5932-626853-01',
    'S-R-30-552-5932-626872-05',
    'S-R-30-552-5932-626872-03',
    'S-R-30-552-5938-924823-01',
    'S-R-30-552-5935-924820-03',
]

WHITELIST_NEWLY_EMERGED = [
    # Add IDs here to skip 'Newly Emerged' check
]

WHITELIST_SEASONAL_VARIABILITY = [
    'S-R-30-552-5932-626857-01',
    'S-R-30-552-5932-626861-05',
    'S-R-30-552-5932-626859-01',
    'S-R-30-552-5932-626861-03',
    'S-R-30-552-5932-626864-12',
    'S-R-30-552-5932-626864-11',
    'S-R-30-552-5932-626872-05',
    'S-R-30-552-5932-626872-04',
    'S-R-30-552-5932-626872-03',
    'S-R-30-552-5938-924823-01',
    'S-R-30-552-5935-924820-03',
]

WHITELIST_COLOUR = [
    'S-R-30-552-5932-626864-02',
    'S-R-30-552-5932-626853-01',
    'S-R-30-552-5932-626864-06',
    'S-R-30-552-5932-626872-02',
    'S-R-30-552-5937-626934-01',
    'S-R-30-552-5937-626939-01',
]

WHITELIST_ODOUR = [
    'S-R-30-552-5932-626864-02',
    'S-R-30-552-5932-626850-01',
    'S-R-30-552-6841-626971-08',
    'S-R-30-552-6841-626971-07',
    'S-R-30-552-5938-626913-01',
]

# Taluka to login username mapping used to populate revert_list.csv
TALUKA_LOGIN_MAP = {
    "Canacona": "bdo_can@yahoo.in",
    "Dharbandora": "bdo-darbandora.goa@nic.in",
    "Mormugao": "bdo-mormugao.goa@nic.in",
    "Ponda": "sdiv.wdii.wrdponda@gmail.com",
    "Quepem": "bdo.quepem@gmail.com",
    "Salcete": "bdosalcete@yahoo.co.in",
    "Sanguem": "bdo-sanguem.goa@nic.in",
}

WHITELIST_TASTE = [
    'S-R-30-552-5932-626864-02',
    'S-R-30-552-5932-626850-01',
    'S-R-30-552-5932-626864-06',
    'S-R-30-552-5932-626857-01',
    'S-R-30-552-6841-626971-07',
    'S-R-30-552-5937-626934-01',
    'S-R-30-552-5937-626939-01',
]

WHITELIST_DISCHARGE = [
    'S-R-30-552-5932-626854-11',
    'S-R-30-552-5932-626854-10',
    'S-R-30-552-5932-626854-03',
    'S-R-30-552-5932-626854-02',
    'S-R-30-552-5932-626870-02',
    'S-R-30-552-5932-626870-01',
]

WHITELIST_LOCATION = [
  'S-R-30-552-5932-626851-02',
  'S-R-30-552-5932-626870-06',
  'S-R-30-552-5932-626872-02',
]

# ... (DB functions) ...

def validate_spring_nature(value, row_id):
    if row_id in WHITELIST_SPRING_NATURE:
        return True
    
    val_str = str(value).strip()
    if val_str == "Seasonal":
        return "is the 'Spring Nature' really seasonal?"
    return True

def validate_newly_emerged(value, row_id):
    if row_id in WHITELIST_NEWLY_EMERGED:
        return True
    
    val_str = str(value).strip()
    if val_str.lower() == "yes":
        return "has the spring emerged in the last 10 years?"
    return True

def validate_seasonal_variability(value, row_id):
    if row_id in WHITELIST_SEASONAL_VARIABILITY:
        return True
    
    val_str = str(value).strip()
    if val_str.lower() == "high":
        return "is the seasonal variability high ?"
    return True

def validate_colour(value, row_id):
    if row_id in WHITELIST_COLOUR:
        return True
    
    val_str = str(value).strip()
    if val_str.lower() == "coloured":
        return "is the spring water really coloured?"
    return True

def validate_odour(value, row_id):
    if row_id in WHITELIST_ODOUR:
        return True
    
    val_str = str(value).strip()
    if val_str.lower() == "non-agreeable":
        return "is the smell/odour of water really non-agreeable?"
    return True

def validate_taste(value, row_id):
    if row_id in WHITELIST_TASTE:
        return True
    
    val_str = str(value).strip()
    if val_str.lower() == "objectionable":
        return "is the taste of water really objectionable?"
    return True

def validate_discharge(value, row_id):
    if row_id in WHITELIST_DISCHARGE:
        return True
    
    if str(value).strip().upper() == "N.A.":
        return True
        
    return validate_numeric(value, "Outlet 1 discharge (lpm)", max_val=10, custom_error="Please check Outlet volume and duration figures.")

# --- Main Validation Logic ---

def main():
    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("")
        
    log(f"Reading data from {INPUT_FILE}...")
    
    if not os.path.exists(INPUT_FILE):
        log(f"Error: File not found at {INPUT_FILE}")
        return

    try:
        # Read the combined CSV file
        df = pd.read_csv(INPUT_FILE)
        # Convert DataFrame to list of dicts for compatibility with existing logic
        # Replace NaN with empty strings to match CSV behavior
        df = df.fillna("")
        reader = df.to_dict('records')
    except Exception as e:
        log(f"Failed to read file: {e}")
        return

    log("Connecting to database...")
    conn = get_db_connection()
    if not conn:
        log("Cannot proceed without DB connection.")
        return
    
    cursor = conn.cursor()

    # reader variable is already set above
    # reader = csv.DictReader(io.StringIO(csv_content))

    # Nested Grouping: Block -> Surveyor Name -> List of Errors
    grouped_issues = {}
    
    row_count = 0
    errors_found = 0
    revert_list = []
    
    print("\n*Validation Report* 📋\n")

    for i, row in enumerate(reader):
        row_count += 1
        row_errors = []
        
        # Identify row context
        block = row.get("Block", "Unknown Block")
        surveyor = row.get("Surveyor Name", "Unknown Surveyor")
        row_id = row.get("Spring ID", f"Row {i+2}")

        # Define rules per row to inject row_id if needed
        rules = {
            "Latitude °N": [
                lambda v: validate_required(v, "Latitude"),
                lambda v: validate_numeric(v, "Latitude", 14.5, 16.0) 
            ],
            "Longitude °E": [
                lambda v: validate_required(v, "Longitude"),
                lambda v: validate_numeric(v, "Longitude", 73.5, 74.5)
            ],
            "Close-up shot": [lambda v: validate_url(v, "Close-up shot")],
            "Wide angle shot": [lambda v: validate_url(v, "Wide angle shot")],
            "Selfie": [lambda v: validate_url(v, "Selfie")],
            "Spring Video": [lambda v: validate_url(v, "Spring Video")],
            "Spring Type": [lambda v: validate_required(v, "Spring Type")],
            "Outlet 1 discharge (lpm)": [
                lambda v: validate_discharge(v, row_id)
            ],
            "Temperature of spring water": [
                lambda v: True
            ],
            "Local Nomenclature for spring": [
                 lambda v: validate_regex(v, r"(?i).*zara.*", "Local Nomenclature", "Correct local name to 'Zara'")
            ],
            "Whether the spring has undergone any springshed/watershed management program?": [
                lambda v: True
            ],
            "Spring Nature": [
                lambda v: validate_spring_nature(v, row_id)
            ],
            "Whether this is a newly emerged spring": [
                lambda v: validate_newly_emerged(v, row_id)
            ],
            "Seasonal variability (across the year)": [
                lambda v: validate_seasonal_variability(v, row_id)
            ],
            "Colour of spring water": [
                lambda v: validate_colour(v, row_id)
            ],
            "Smell/odour of water": [
                lambda v: validate_odour(v, row_id)
            ],
            "Taste of water ": [
                lambda v: validate_taste(v, row_id)
            ],
            "Dominant land use land cover in spring upstream": [
                lambda v: validate_required(v, "Dominant land use land cover in spring upstream")
            ],
            "Land use land cover in and around spring location ": [
                lambda v: validate_required(v, "Land use land cover in and around spring location")
            ],
            "Resource threat": [
                lambda v: validate_required(v, "Resource threat")
            ]
        }

        # 1. Standard Column Checks
        for col, validators in rules.items():
            val = row.get(col)
            for validator in validators:
                result = validator(val)
                if result is not True:
                    row_errors.append(result)

        # 2. Cross-column validation: Temperature vs Spring Nature
        temp = row.get("Temperature of spring water", "").strip()
        spring_nature = row.get("Spring Nature", "").strip()
        watershed = row.get("Whether the spring has undergone any springshed/watershed management program?", "").strip()
        resource_threat = row.get("Resource threat", "").strip()
        
        if spring_nature == "Dried":
            if temp.upper() != "N.A.":
                row_errors.append("If 'Spring Nature' is 'Dried', then 'Temperature of spring water' must be 'N.A.'")
            if watershed.upper() != "N.A.":
                row_errors.append("If 'Spring Nature' is 'Dried', then 'Whether the spring has undergone any springshed/watershed management program?' must be 'N.A.'")
            if resource_threat.upper() != "N.A.":
                row_errors.append("If 'Spring Nature' is 'Dried', then 'Resource threat' must be 'N.A.'")
        else:
            if temp.lower() != "cold":
                row_errors.append("Temperature of spring water must be 'Cold'")
            if watershed.lower() != "no":
                row_errors.append("Whether the spring has undergone any springshed/watershed management program? must be 'No'")
            if resource_threat.upper() == "N.A.":
                row_errors.append("Resource threat cannot be 'N.A.'")

        # 2.1. Cross-column validation: Land Use vs Spring Nature
        land_use_upstream = row.get("Dominant land use land cover in spring upstream", "").strip()
        land_use_around = row.get("Land use land cover in and around spring location ", "").strip()
        
        if land_use_upstream.upper() == "N.A." and spring_nature != "Dried":
            row_errors.append("Dominant land use land cover in spring upstream cannot be 'N.A.'")
        
        if land_use_around.upper() == "N.A." and spring_nature != "Dried":
            row_errors.append("Land use land cover in and around spring location cannot be 'N.A.'")

        # 3. Cross-column validation: Seep type
        spring_type = str(row.get("Spring Type", "")).strip().lower()
        discharge_measurable = str(row.get("Whether spring discharge could be measured? ", "")).strip().upper()
        num_outlets = str(row.get("No. of spring outlets", "")).strip()

        if spring_type == "Seep":
            if discharge_measurable != "No":
                row_errors.append("When Spring Type is 'seep', Spring Discharge measurement must be 'No'")
            
            try:
                if num_outlets == "" or float(num_outlets) != 0:
                    row_errors.append("When Spring Type is 'seep', Number of spring outlets must be 0")
            except ValueError:
                row_errors.append("When Spring Type is 'seep', Number of spring outlets must be 0")

        # 3.01 Cross-column validation: Measurable discharge vs outlets
        if discharge_measurable == "YES":
            try:
                if num_outlets == "" or float(num_outlets) <= 0:
                    row_errors.append("If Spring discharge could be measured, then no. of spring outlets should be greater than zero")
            except ValueError:
                row_errors.append("If Spring discharge could be measured, then no. of spring outlets should be greater than zero")

        # 3.1 Cross-column validation: Perennial discharge
        discharge_val = str(row.get("Outlet 1 discharge (lpm)", "")).strip()
        
        # New validation: if number of outlets is zero then there should not be any discharge
        try:
            if num_outlets != "" and float(num_outlets) == 0:
                if discharge_val.upper() != "N.A." and float(discharge_val) != 0:
                    row_errors.append("If number of outlets is zero then there should not be any discharge")
        except (ValueError, TypeError):
            pass

        if spring_nature == "Perennial" and discharge_measurable == "YES":
            try:
                if float(discharge_val) == 0:
                    row_errors.append("If a spring nature is perennial and Spring discharge can be measured then it can’t have zero discharge")
            except (ValueError, TypeError):
                pass

        # 3.2 Cross-column validation: Dependent Type vs Land Use
        dependent_type = str(row.get("Dependent Type", "")).strip()
        if dependent_type.lower() == "wild animals":
            allowed_land_use = ["forest", "shrubs", "pasture"]
            if land_use_around.lower() not in allowed_land_use:
                row_errors.append("If dependent type is Wild animals, then Land use land cover in and around spring location should be forest or shrubs or pasture only")

        # 3.3 Cross-column validation: Dependent Type vs Dependent Villages
        if dependent_type.lower() in ["wild animals", "non-residents"]:
            dependent_villages = str(row.get("Name Dependent Villages", "")).strip()
            if dependent_villages != "" and dependent_villages.upper() != "N.A.":
                row_errors.append(f"If dependent type is {dependent_type}, then there will be no dependent villages")

        # 3.4 Cross-column validation: Dependency level vs Other source
        dependency = str(row.get("Dependency", "")).strip().lower()
        if dependency in ["low", "moderate"]:
            other_source = str(row.get("Other available source of water", "")).strip()
            # "कोई नहीं" means "None" in Hindi
            if other_source.lower() in ["none", "n.a.", "कोई नहीं", ""]:
                row_errors.append(f"If dependency level is {dependency}, then other available source of water cannot be None")

        # 3.5 Cross-column validation: Water quality vs Usage
        colour = str(row.get("Colour of spring water", "")).strip().lower()
        odour = str(row.get("Smell/odour of water", "")).strip().lower()
        taste = str(row.get("Taste of water ", "")).strip().lower()
        usage = str(row.get("Usage of spring water", "")).strip().lower()

        if colour == "coloured" and odour == "non-agreeable":
            if taste != "objectionable":
                row_errors.append("If Spring water is coloured and smell of water is non-agreeable, then taste of water should be objectionable")
            if "drinking" in usage:
                row_errors.append("If Spring water is coloured and smell of water is non-agreeable, then water should not be used for drinking purpose")

        # 4. Row-level Geospatial ID Check
        lat = row.get("Latitude °N")
        lon = row.get("Longitude °E")
        taluka = str(row.get("Block", "")).strip()
        village = str(row.get("Village", "")).strip()
        
        if not village or village.lower() == "nan":
            village = str(row.get("Town", "")).strip()
        
        if lat and lon and row_id not in WHITELIST_LOCATION:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                is_valid_loc, msg = validate_location_in_db(cursor, lat_f, lon_f, taluka, village)
                if not is_valid_loc:
                    row_errors.append(msg)
            except ValueError:
                pass

        if row_errors:
            errors_found += 1
            revert_list.append({
                "Taluka": block,
                "Username to login": TALUKA_LOGIN_MAP.get(block, ""),
                "Enumerator Name": surveyor,
                "Spring ID": row_id
            })
            
            # Initialize structure if needed
            if block not in grouped_issues:
                grouped_issues[block] = {}
            if surveyor not in grouped_issues[block]:
                grouped_issues[block][surveyor] = []
            
            # Add errors with row ID context
            grouped_issues[block][surveyor].append(f"🚨 *Issue in {row_id}*")
            grouped_issues[block][surveyor].extend([f"- {err}" for err in row_errors])

    # Output Grouped Results
    for block, surveyors in grouped_issues.items():
        log(f"🏙️ *Block: {block}*\n")
        for surveyor, issues in surveyors.items():
            log(f"👤 *Surveyor: {surveyor}*")
            for issue in issues:
                log(issue) # Issues already contain prefixes
            log("") # Spacing between surveyors
        log("--------------------\n") # Spacing between blocks

    if errors_found == 0:
        log(f"✅ *Validation Complete*")
        log(f"Processed {row_count} rows. All good! 👍")
    else:
        log(f"⚠️ *Validation Complete*")
        log(f"Processed {row_count} rows. Found issues in {errors_found} rows.")
        
        # Save revert list to CSV
        revert_df = pd.DataFrame(revert_list)
        # Drop duplicates in case the same spring ID appears multiple times with different errors
        revert_df = revert_df.drop_duplicates()
        # Sort by Taluka, Enumerator Name, and Spring ID
        revert_df = revert_df.sort_values(by=["Taluka", "Enumerator Name", "Spring ID"])
        revert_df.to_csv(REVERT_FILE, index=False)
        log(f"Saved list of springs to revert to {REVERT_FILE}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
