import os
import psycopg2
import simplekml
import json
import traceback

# ==========================================
# DATABASE CONFIGURATION
# Please update these values to match your environment
# ==========================================
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")
SSLMODE = os.getenv("SSLMODE")

import re

def sanitize_xml_string(value):
    """
    Remove characters that are not allowed in XML 1.0
    Ranges allowed: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    """
    if value is None:
        return ""
    
    val_str = str(value)
    
    # First, handle standard XML escaping
    # We do this BEFORE removing control chars so we don't double-escape if we were to do it later
    # Python's xml.sax.saxutils.escape does <, >, &
    # We also need " and '
    val_str = val_str.replace("&", "&amp;")
    val_str = val_str.replace("<", "&lt;")
    val_str = val_str.replace(">", "&gt;")
    val_str = val_str.replace('"', "&quot;")
    val_str = val_str.replace("'", "&apos;")

    # Remove invalid control characters
    # Ranges allowed: #x9 | #xA | #xD | [#x20-#xD7FF] | ...
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', val_str)

def main():
    conn = None
    try:
        print("Connecting to database...")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT,
            sslmode=SSLMODE 
        )
        cur = conn.cursor()

        # Step 1: Get unique taluka and village pairs
        print("Fetching unique village lists...")
        # Ensuring we don't pick up nulls which would break path creation or filenames
        cur.execute("""
            SELECT DISTINCT taluka, village 
            FROM dslr.village_boundaries 
            WHERE taluka IS NOT NULL AND village IS NOT NULL 
            ORDER BY taluka, village
        """)
        locations = cur.fetchall()
        print(f"Found {len(locations)} unique locations.")

        # Step 2: Iterate and generate KMLs
        for taluka, village in locations:
            taluka_str = str(taluka).strip()
            village_str = str(village).strip()
            
            print(f"Processing: Taluka='{taluka_str}', Village='{village_str}'")
            
            # Create taluka directory if it doesn't exist
            if not os.path.exists(taluka_str):
                os.makedirs(taluka_str)
            
            # Step 3: Fetch features for this village
            query = """
                SELECT *, ST_AsGeoJSON(ST_Transform(geom, 4326)) as geom_json 
                FROM dslr.village_boundaries 
                WHERE taluka = %s AND village = %s
            """
            cur.execute(query, (taluka, village))
            rows = cur.fetchall()
            
            if not rows:
                continue

            # Get column names to use as KML attributes
            col_names = [desc[0] for desc in cur.description]
            
            kml = simplekml.Kml()
            
            for row in rows:
                data = dict(zip(col_names, row))

                # Add direction link as first attribute
                # lat = data.get('latitude')
                # lon = data.get('longitude')
                # if lat is not None and lon is not None:
                #     link = f"https://maps.google.com?q={lat},{lon}&t=h"
                #     # Rebuild dictionary to make direction the first item
                #     new_data = {'direction': link}
                #     new_data.update(data)
                #     data = new_data
                
                # Extract and parse geometry
                raw_geom = data.get('geom_json')
                if not raw_geom:
                    continue
                    
                geometry = json.loads(raw_geom)
                
                # cleanup data for attributes
                if 'geom_json' in data: del data['geom_json']
                if 'geom' in data: del data['geom']
                if 'wkb_geometry' in data: del data['wkb_geometry']

                def add_attributes(kml_obj, attrs):
                    for k, v in attrs.items():
                        if v is not None:
                            # Sanitize the value before adding
                            safe_val = sanitize_xml_string(v)
                            kml_obj.extendeddata.newdata(k, safe_val)

                # Handle different geometry types
                geo_type = geometry['type']
                coords = geometry['coordinates']

                if geo_type == 'Point':
                    pnt = kml.newpoint()
                    pnt.coords = [tuple(coords)] 
                    add_attributes(pnt, data)

                elif geo_type == 'Polygon':
                    poly = kml.newpolygon()
                    poly.outerboundaryis = [tuple(c) for c in coords[0]]
                    if len(coords) > 1:
                        for inner in coords[1:]:
                            poly.innerboundaryis.append([tuple(c) for c in inner])
                    add_attributes(poly, data)

                elif geo_type == 'MultiPolygon':
                    for poly_coords in coords:
                        poly = kml.newpolygon()
                        poly.outerboundaryis = [tuple(c) for c in poly_coords[0]]
                        if len(poly_coords) > 1:
                            for inner in poly_coords[1:]:
                                poly.innerboundaryis.append([tuple(c) for c in inner])
                        add_attributes(poly, data)
                
                elif geo_type == 'LineString':
                    ls = kml.newlinestring()
                    ls.coords = [tuple(c) for c in coords]
                    add_attributes(ls, data)

            # Save the KML file
            file_path = os.path.join(taluka_str, f"{village_str}.kml")
            try:
                # Try saving normally
                kml.save(file_path)
            except Exception as save_err:
                print(f"Failed to save {file_path}: {save_err}")
                print(f"Columns: {col_names}")
                if rows:
                    print("First row data sample:", dict(zip(col_names, rows[0])))
                # fallback: try to write without formatting if simplekml supports it via kml()
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        # simplekml.kml() typically returns the string. 
                        # We pass format=False to skip minidom parsing
                        f.write(kml.kml(format=False))
                    print(f"Saved {file_path} without formatting (fallback).")
                except Exception as fallback_err:
                    print(f"Fallback save also failed: {fallback_err}")
                    traceback.print_exc()

        print("\nAll KML files generated successfully.")

    except psycopg2.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    main()
