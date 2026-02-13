let allData = [];
let filteredData = [];
let currentIndex = 0;

const talukaFilter = document.getElementById('taluka-filter');
const villageFilter = document.getElementById('village-filter');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const pageInfo = document.getElementById('page-info');
const tableBody = document.getElementById('table-body');
const thumbnailDisplay = document.getElementById('thumbnail-display');
const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');

// Modal elements
const modal = document.getElementById('image-modal');
const modalImg = document.getElementById('modal-img');
const captionText = document.getElementById('caption');
const closeModal = document.querySelector('.close-modal');

// Load CSV data
Papa.parse('downloads/combined_schedules.csv', {
    download: true,
    header: true,
    complete: function(results) {
        allData = results.data.filter(row => row['Spring ID']); // Filter out empty rows
        populateTalukas();
        applyFilters();
    },
    error: function(err) {
        console.error("Error loading CSV:", err);
        tableBody.innerHTML = '<tr><td colspan="2" style="color: red;">Error loading data. Please ensure the file exists at downloads/combined_schedules.csv and you are running this via a local server.</td></tr>';
    }
});

function populateTalukas() {
    const talukas = [...new Set(allData.map(row => row['Block']))].filter(Boolean).sort();
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
        filteredForVillages = allData.filter(row => row['Block'] === selectedTaluka);
    }

    const villages = [...new Set(filteredForVillages.map(row => row['Village']))].filter(Boolean).sort();
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
        const matchesTaluka = selectedTaluka === 'all' || row['Block'] === selectedTaluka;
        const matchesVillage = selectedVillage === 'all' || row['Village'] === selectedVillage;
        return matchesTaluka && matchesVillage;
    });

    currentIndex = 0;
    displayCurrentItem();
}

function displayCurrentItem() {
    tableBody.innerHTML = '';
    thumbnailDisplay.innerHTML = '';
    
    if (filteredData.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="2">No entries found for the selected filters.</td></tr>';
        pageInfo.textContent = 'Item 0 of 0';
        prevBtn.disabled = true;
        nextBtn.disabled = true;
        return;
    }

    const item = filteredData[currentIndex];
    pageInfo.textContent = `Item ${currentIndex + 1} of ${filteredData.length}`;
    
    const thumbnailColumns = ['Close-up shot', 'Wide angle shot', 'Selfie'];

    // Display all keys and values
    for (const [key, value] of Object.entries(item)) {
        if (thumbnailColumns.includes(key)) {
            if (value && value.startsWith('http')) {
                addThumbnail(key, value);
            }
            continue; // Don't show in the main table
        }

        const row = document.createElement('tr');
        const th = document.createElement('th');
        th.textContent = key;
        const td = document.createElement('td');
        
        // Handle images/links
        if (typeof value === 'string' && (value.startsWith('http://') || value.startsWith('https://'))) {
            if (value.match(/\.(jpg|jpeg|png|gif)$/i)) {
                const img = document.createElement('img');
                img.src = value;
                img.style.maxWidth = '300px';
                img.style.display = 'block';
                img.style.cursor = 'pointer';
                img.onclick = () => openModal(value, key);
                
                const link = document.createElement('a');
                link.href = value;
                link.target = '_blank';
                link.textContent = 'View Full Size';
                td.appendChild(img);
                td.appendChild(link);
            } else {
                const link = document.createElement('a');
                link.href = value;
                link.target = '_blank';
                link.textContent = value;
                td.appendChild(link);
            }
        } else {
            td.textContent = value || 'N/A';
        }
        
        row.appendChild(th);
        row.appendChild(td);
        tableBody.appendChild(row);
    }

    prevBtn.disabled = currentIndex === 0;
    nextBtn.disabled = currentIndex === filteredData.length - 1;
}

function addThumbnail(label, url) {
    const div = document.createElement('div');
    div.className = 'thumbnail-item';
    
    const img = document.createElement('img');
    img.src = url;
    img.alt = label;
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

    const index = allData.findIndex(row => row['Spring ID'] === searchTerm);
    if (index !== -1) {
        // Reset filters to show the found item
        talukaFilter.value = 'all';
        villageFilter.value = 'all';
        applyFilters();
        
        // Find the index in filteredData (which is now allData)
        currentIndex = index;
        displayCurrentItem();
    } else {
        alert('Spring ID not found');
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
