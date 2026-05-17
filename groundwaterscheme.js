let allData = [];
let filteredData = [];
let currentIndex = 0;

const talukaFilter = document.getElementById('taluka-filter');
const villageFilter = document.getElementById('village-filter');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const pageInfo = document.getElementById('page-info');
const scheduleContainer = document.getElementById('schedule-container');
const thumbnailDisplay = document.getElementById('thumbnail-display');
const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');

// Modal elements
const modal = document.getElementById('image-modal');
const modalImg = document.getElementById('modal-img');
const captionText = document.getElementById('caption');
const closeModal = document.querySelector('.close-modal');

// Load CSV data
Papa.parse('downloads/combined_groundWaterScheme.csv', {
    download: true,
    header: true,
    complete: function(results) {
        allData = results.data.filter(row => row['serial_no']); // Filter out empty rows
        populateTalukas();
        applyFilters();
    },
    error: function(err) {
        console.error("Error loading CSV:", err);
        scheduleContainer.innerHTML = '<div style="color: red;">Error loading data. Please ensure the file exists at downloads/combined_groundWaterScheme.csv and you are running this via a local server.</div>';
    }
});

function populateTalukas() {
    const talukas = [...new Set(allData.map(row => row['block_tehsil_name']))].filter(Boolean).sort();
    talukas.forEach(taluka => {
        const option = document.createElement('option');
        option.value = taluka;
        option.textContent = taluka;
        talukaFilter.appendChild(option);
    });
}

function populateVillages(selectedTaluka) {
    villageFilter.innerHTML = '<option value="all">All Villages</option>';

    let filteredForVillages = allData;
    if (selectedTaluka !== 'all') {
        filteredForVillages = allData.filter(row => row['block_tehsil_name'] === selectedTaluka);
    }

    const villages = [...new Set(filteredForVillages.map(row => row['village_name']))].filter(Boolean).sort();
    villages.forEach(village => {
        const option = document.createElement('option');
        option.value = village;
        option.textContent = village;
        villageFilter.appendChild(option);
    });
}

function applyFilters() {
    const selectedTaluka = talukaFilter.value;
    const selectedVillage = villageFilter.value;

    filteredData = allData.filter(row => {
        const matchesTaluka = selectedTaluka === 'all' || row['block_tehsil_name'] === selectedTaluka;
        const matchesVillage = selectedVillage === 'all' || row['village_name'] === selectedVillage;
        return matchesTaluka && matchesVillage;
    });

    currentIndex = 0;
    displayCurrentItem();
}

function displayCurrentItem() {
    scheduleContainer.innerHTML = '';
    thumbnailDisplay.innerHTML = '';

    if (filteredData.length === 0) {
        scheduleContainer.innerHTML = '<div>No entries found for the selected filters.</div>';
        pageInfo.textContent = 'Item 0 of 0';
        prevBtn.disabled = true;
        nextBtn.disabled = true;
        return;
    }

    const item = filteredData[currentIndex];
    pageInfo.textContent = `Item ${currentIndex + 1} of ${filteredData.length}`;

    // Rewrite image URL to GitHub raw content
    const rewriteImageUrl = (filename) => {
        if (!filename || typeof filename !== 'string') return null;
        filename = filename.trim();
        if (!filename) return null;
        return `https://raw.githubusercontent.com/alansaviolobo/micensus/refs/heads/master/img-waterbodies/waterbody-${filename}`;
    };

    if (item['image_name']) {
        const imgUrl = rewriteImageUrl(item['image_name']);
        if (imgUrl) addThumbnail('Scheme Image', imgUrl);
    }

    // Google Maps link
    let gmapdiv = document.createElement('div');
    gmapdiv.className = 'thumbnail-item';
    let gmapicon = document.createElement('img');
    gmapicon.src = 'icon.png';
    gmapicon.style.width = '32px';
    let gmaplink = document.createElement('a');
    gmaplink.href = 'http://maps.google.com/maps?z=12&t=m&q=loc:' + item['latitude'] + '+' + item['longitude'];
    gmaplink.target = '_blank';
    gmaplink.style.display = 'block';
    gmaplink.style.fontSize = '10px';
    gmaplink.textContent = 'Google Maps';
    gmapdiv.appendChild(gmapicon);
    gmapdiv.appendChild(gmaplink);
    thumbnailDisplay.appendChild(gmapdiv);

    // Determine scheme sub-type
    const schemeSubType = item['dugwell_type']
        ? `Dug Well - ${item['dugwell_type']}`
        : item['tubewell_type']
        ? `Tube Well - ${item['tubewell_type']}`
        : 'N/A';

  scheduleContainer.innerHTML = `
        <div class="schedule-header">
            <h3>Department of Water Resources, RD &amp; GR, Ministry of Jal Shakti</h3>
            <h3>7th MI Census and 2nd Census of Water Bodies</h3>
            <h2>MI CENSUS - GROUND WATER SCHEME</h2>
            <p>REFERENCE YEAR: 2023-24 (AGRICULTURAL YEAR)</p>
        </div>

        <div class="identification-box">
            <div class="section-title">I. Identification Particulars</div>
            <div class="grid-row">
                <div class="grid-item"><span class="label">(a) State</span><span class="value">${item.state_name || 'GOA'}</span></div>
                <div class="grid-item"><span class="label">(b) District</span><span class="value">${item.district_name || ''}</span></div>
                <div class="grid-item"><span class="label">(c) Block/Sub-District</span><span class="value">${item.block_tehsil_name || ''}</span></div>
            </div>
            <div class="grid-row">
                <div class="grid-item"><span class="label">(d) Village</span><span class="value">${item.village_name || ''}</span></div>
                <div class="grid-item"><span class="label">Sl. No. of Scheme</span><span class="value">${item.s_no_of_scheme || ''}</span></div>
                <div class="grid-item"><span class="label">Date of Enumeration</span><span class="value">${item.enumeration_date || ''}</span></div>
            </div>
            <div class="unique-id-key">
                <span class="label">Serial Number</span>
                <span class="value">${item.serial_no || ''}</span>
            </div>
        </div>

        <div class="section-title">II. Scheme Details</div>

        <div class="two-col">
            <div>
                <div class="info-item">
                    <span class="label">1. Scheme Type</span>
                    <span class="value">${item.scheme_type || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">1(a). Sub-type</span>
                    <span class="value">${schemeSubType}</span>
                </div>
                <div class="info-item">
                    <span class="label">2. Ownership</span>
                    <span class="value">${item.ownership || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Individual Owner Name</span>
                    <span class="value">${item.individual_owner_name || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Khasra / Plot / Survey No.</span>
                    <span class="value">${item.khasra_number || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Location Particulars</span>
                    <span class="value">${item.location_particulars || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Total Owners Holding</span>
                    <span class="value">${item.total_owners_holding || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Social Status / Gender</span>
                    <span class="value">${item.social_status || 'N/A'} / ${item.gender || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Commissioning Year</span>
                    <span class="value">${item.commissioning_year || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Latitude / Longitude</span>
                    <span class="value">${item.latitude} , ${item.longitude}</span>
                </div>
            </div>
            <div>
                <div class="info-item">
                    <span class="label">Scheme Depth (m)</span>
                    <span class="value">${item.scheme_depth || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Scheme Diameter (cm)</span>
                    <span class="value">${item.scheme_diameter || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Bore Depth (m)</span>
                    <span class="value">${item.scheme_bore_depth || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Nearest Scheme Distance (m)</span>
                    <span class="value">${item.nearest_scheme_distance || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Construction Cost (₹)</span>
                    <span class="value">${item.construction_cost || '0'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Machinery Cost (₹)</span>
                    <span class="value">${item.machinery_cost || '0'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Maintenance Cost (₹)</span>
                    <span class="value">${item.maintenance_cost || '0'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Finance Source</span>
                    <span class="value">${[item.finance_source1, item.finance_source2].filter(Boolean).join(', ') || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Construction Subsidy / Machinery Subsidy (₹)</span>
                    <span class="value">${item.construction_subsidy || '0'} / ${item.machinery_subsidy || '0'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Scheme Status</span>
                    <span class="value">${item.scheme_status || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">If Not In Use – Years / Reason</span>
                    <span class="value">${item.not_in_use_years || 'N/A'} / ${item.status_reason_temporarily || item.status_reason_permanently || 'N/A'}</span>
                </div>
            </div>
        </div>

        <div class="section-title">III. Lifting / Distribution</div>
        <div class="two-col">
            <div>
                <div class="info-item">
                    <span class="label">Water Distribution Method</span>
                    <span class="value">${item.water_distribution_method || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Lifting Device Type</span>
                    <span class="value">${item.lifting_device_type || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Energy Source</span>
                    <span class="value">${item.energy_source || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Horse Power of Lifting Device</span>
                    <span class="value">${item.horse_power_of_lifting_device || 'N/A'}</span>
                </div>
            </div>
            <div>
                <div class="info-item">
                    <span class="label">Pump Operating Days (Kharif / Rabi / Perennial / Other)</span>
                    <span class="value">${item.pump_operating_days_kharif_season || '0'} / ${item.pump_operating_days_rabi_season || '0'} / ${item.pump_operating_days_perennial_crop || '0'} / ${item.pump_operating_days_other_season || '0'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Avg Pumping/Day (Kharif / Rabi / Perennial / Other)</span>
                    <span class="value">${item.avg_pumping_per_day_kharif_season || '0'} / ${item.avg_pumping_per_day_rabi_season || '0'} / ${item.avg_pumping_per_day_perennial_crop || '0'} / ${item.avg_pumping_per_day_other_season || '0'}</span>
                </div>
            </div>
        </div>

        <div class="section-title">IV. Command Area &amp; Irrigation</div>
        <div class="two-col">
            <div>
                <div class="info-item">
                    <span class="label">Located in Command Area</span>
                    <span class="value">${item.located_in_command_area || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Reason (Command Area)</span>
                    <span class="value">${item.scheme_in_command_area_reason || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Name of MMI Project</span>
                    <span class="value">${item.name_of_mmi_project || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Recharge of Ground Water</span>
                    <span class="value">${item.recharge_ground_water_selection || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Culturable Command Area (Ha)</span>
                    <span class="value">${item.culturable_command_area || '0'}</span>
                </div>
            </div>
            <div>
                <div class="info-item">
                    <span class="label">IPC (Kharif / Rabi / Perennial / Other / Total)</span>
                    <span class="value">${item.ipc_kharif_season || '0'} / ${item.ipc_rabi_season || '0'} / ${item.ipc_perennial_crop || '0'} / ${item.ipc_other_season || '0'} / ${item.ipc_total || '0'}</span>
                </div>
                <div class="info-item">
                    <span class="label">IPU (Kharif / Rabi / Perennial / Other / Total)</span>
                    <span class="value">${item.ipu_kharif_season || '0'} / ${item.ipu_rabi_season || '0'} / ${item.ipu_perennial_crop || '0'} / ${item.ipu_other_season || '0'} / ${item.ipu_total || '0'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Scheme Under-utilisation</span>
                    <span class="value">${item.under_utilised_selection || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Reason for Under-utilisation</span>
                    <span class="value">${item.under_utilisation_reason || 'N/A'}</span>
                </div>
            </div>
        </div>

        <div class="section-title">V. Other</div>
        <div class="two-col">
            <div>
                <div class="info-item">
                    <span class="label">Drinking Water Purpose</span>
                    <span class="value">${item.drinking_water_purpose || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">Captured in Previous Census</span>
                    <span class="value">${item.captured_in_previous_census || 'N/A'}</span>
                </div>
            </div>
        </div>

        <div class="remark-box">
            <span class="label">Remark</span>
            <span class="value">${item.remark || 'No remarks'}</span>
        </div>

        <div class="officer-info">
            <div>
                <span class="label">Enumerator Name</span>
                <span class="value">${item.enumerator_name || 'N/A'}</span>
            </div>
        </div>
    `;

    prevBtn.disabled = currentIndex === 0;
    nextBtn.disabled = currentIndex === filteredData.length - 1;
}

function addThumbnail(label, url) {
    const div = document.createElement('div');
    div.className = 'thumbnail-item';

    const img = document.createElement('img');
    img.alt = label;
    img.src = url;
    img.onclick = () => openModal(url, label);

    const span = document.createElement('span');
    span.className = 'thumbnail-label';
    span.textContent = label;

    div.appendChild(img);
    div.appendChild(span);
    thumbnailDisplay.appendChild(div);
}

function openModal(url, caption) {
    modal.style.display = "block";
    modalImg.src = url;
    captionText.textContent = caption;
}

function performSearch() {
    const searchTerm = searchInput.value.trim();
    if (!searchTerm) return;

    const index = allData.findIndex(row => row['serial_no'] === searchTerm);
    if (index !== -1) {
        talukaFilter.value = 'all';
        villageFilter.value = 'all';
        applyFilters();

        currentIndex = index;
        displayCurrentItem();
    } else {
        alert('Serial number not found');
    }
}

// Event Listeners
talukaFilter.addEventListener('change', () => {
    populateVillages(talukaFilter.value);
    applyFilters();
});

villageFilter.addEventListener('change', () => {
    applyFilters();
});

prevBtn.addEventListener('click', () => {
    if (currentIndex > 0) {
        currentIndex--;
        displayCurrentItem();
        window.scrollTo(0, 0);
    }
});

nextBtn.addEventListener('click', () => {
    if (currentIndex < filteredData.length - 1) {
        currentIndex++;
        displayCurrentItem();
        window.scrollTo(0, 0);
    }
});

searchBtn.addEventListener('click', performSearch);
searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performSearch();
});

closeModal.onclick = () => {
    modal.style.display = "none";
};

window.onclick = (event) => {
    if (event.target === modal) {
        modal.style.display = "none";
    }
};
