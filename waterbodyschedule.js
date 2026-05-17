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
Papa.parse('downloads/combined_waterBodySchedule.csv', {
    download: true,
    header: true,
    complete: function(results) {
        allData = results.data.filter(row => row['unique_id']); // Filter out empty rows
        populateTalukas();
        applyFilters();
    },
    error: function(err) {
        console.error("Error loading CSV:", err);
        scheduleContainer.innerHTML = '<div style="color: red;">Error loading data. Please ensure the file exists at downloads/combined_waterBodySchedule.csv and you are running this via a local server.</div>';
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
    // Clear existing options except "All"
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
    
    // Function to rewrite image URL
    const rewriteImageUrl = (url) => {
        if (!url || typeof url !== 'string') return url;
        const filename = url.substring(url.lastIndexOf('/') + 1);
        return `https://raw.githubusercontent.com/alansaviolobo/micensus/refs/heads/master/img-waterbodies/waterbody-${filename}`;
    };

    if (item['image_path']) {
        const rewrittenUrl = rewriteImageUrl(item['image_path']);
        addThumbnail('Water Body Image', rewrittenUrl);
    }

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

    // Build the PDF-like layout
  scheduleContainer.innerHTML = `
        <div class="schedule-header">
            <h3>Department of Water Resources, RD & GR, Ministry of Jal Shakti</h3>
            <h3>7th MI Census and 2nd Census of Water Bodies</h3>
            <h2>CENSUS OF WATER BODIES</h2>
            <h3>WATER BODY SCHEDULE (Code: 05)</h3>
            <p>REFERENCE YEAR: 2023-24 (AGRICULTURAL YEAR)</p>
        </div>

        <div class="identification-box">
            <div class="section-title">I. Identification Particulars</div>
            <div class="grid-row">
                <div class="grid-item"><span class="label">Rural-1/Urban-2</span><span class="value">${item.rural_or_urban === 'Rural' ? 'Rural-1' : 'Urban-2'}</span></div>
                <div class="grid-item"><span class="label">(a) State</span><span class="value">${item.state_name || 'GOA'}</span></div>
                <div class="grid-item"><span class="label">(b) District</span><span class="value">${item.district_name || ''}</span></div>
            </div>
            <div class="grid-row">
                <div class="grid-item"><span class="label">(c) Block/Sub-District</span><span class="value">${item.block_tehsil_name || ''}</span></div>
                <div class="grid-item"><span class="label">(d) Village/Town</span><span class="value">${item.village_name || item.town_municipality_name || ''}</span></div>
                <div class="grid-item"><span class="label">Sl. number within village/Town</span><span class="value">${item.serial_number || ''}</span></div>
            </div>
            <div class="grid-row">
                <div class="grid-item"><span class="label">Date of Enumeration</span><span class="value">${item.enumeration_date || ''}</span></div>
            </div>
            <div class="unique-id-key">
                <span class="label">Unique Identification key for Water body</span>
                <span class="value">${item.unique_id || ''}</span>
            </div>
        </div>

        <div class="section-title">II. Specific Information</div>
        
        <div class="two-col">
            <div>
                <div class="info-item">
                    <span class="label">1.1 (a) Name of Water body / permanent land marks</span>
                    <span class="value">${item.water_body_name || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">1.1 (b) Basin & Sub-basin</span>
                    <span class="value">Basin: ${item.basin_name || 'N/A'}, Sub-basin: ${item.sub_basin_name || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">1.2 (a) Type of Water Body</span>
                    <span class="value">${item.water_body_type || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">1.3 Khasra / Plot / Survey Number</span>
                    <span class="value">${item.khasra_number || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">2. Latitude / 3. Longitude</span>
                    <span class="value">${item.latitude} , ${item.longitude}</span>
                </div>
                <div class="info-item">
                    <span class="label">4. Whether located in</span>
                    <span class="value">${item.water_body_location || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">5. Ownership</span>
                    <span class="value">${item.ownership || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">6(1) Whether Water body is in use</span>
                    <span class="value">${item.water_body_in_use || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">6(2) If in use, primary use</span>
                    <span class="value">${item.water_body_uses_1 || 'N/A'}</span>
                </div>
            </div>
            <div>
                <div class="info-item">
                    <span class="label">7(1). Nature of Water Body</span>
                    <span class="value">${item.water_body_nature || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">10. Under repair/renovation/restoration?</span>
                    <span class="value">${item.water_body_presently_under_repair_renovation_restoration || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">11(1). Associated with central scheme?</span>
                    <span class="value">${item.associated_with_central_scheme || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">12(1). Contains water throughout the year?</span>
                    <span class="value">${item.water_throughout_year || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">13. Water spread area (Reference Year)</span>
                    <span class="value">${item.water_spread_area_reference_year || '0'} Sq. Meter</span>
                </div>
                <div class="info-item">
                    <span class="label">13(1). Water spread area (Current Year)</span>
                    <span class="value">${item.water_spread_area_current_year || '0'} Sq. Meter</span>
                </div>
                <div class="info-item">
                    <span class="label">14. Max. depth of water body (fully filled)</span>
                    <span class="value">${item.max_depth_water_body_fully_filled || '0'} Meter</span>
                </div>
                <div class="info-item">
                    <span class="label">15. Storage Capacity (Present)</span>
                    <span class="value">${item.storage_capacity_water_body_present || '0'} Cu. Meter</span>
                </div>
            </div>
        </div>

        <div class="section-title">III. Additional Details</div>
        <div class="two-col">
            <div>
                <div class="info-item">
                    <span class="label">16. Filled up Storage (During 2023-24)</span>
                    <span class="value">${item.filled_up_storage || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">17. Presence of silt reducing capacity?</span>
                    <span class="value">${item.presence_of_silt || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">18. Status of filling up of storage space</span>
                    <span class="value">${item.filled_up_storage_space || 'N/A'}</span>
                </div>
            </div>
            <div>
                <div class="info-item">
                    <span class="label">22(1). Whether area is encroached?</span>
                    <span class="value">${item.water_body_encroached || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">23. Standalone or connected</span>
                    <span class="value">${item.standalone_or_connected || 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="label">24. Captured during previous census?</span>
                    <span class="value">${item.captured_in_previous_census || 'N/A'}</span>
                </div>
            </div>
        </div>

        <div class="remark-box">
            <span class="label">27. Remark</span>
            <span class="value">${item.remark || 'No remarks'}</span>
        </div>

        <div class="officer-info">
            <div>
                <span class="label">Enumerator Name</span>
                <span class="value">${item.enumerator_name || 'N/A'}</span>
            </div>
            <div>
                <span class="label">Data Collected On</span>
                <span class="value">${item.created_on || 'N/A'}</span>
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

    const index = allData.findIndex(row => row['unique_id'] === searchTerm);
    if (index !== -1) {
        // Reset filters to show the found item
        talukaFilter.value = 'all';
        villageFilter.value = 'all';
        applyFilters();
        
        // Find the index in filteredData (which is now allData)
        currentIndex = index;
        displayCurrentItem();
    } else {
        alert('Unique ID not found');
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
