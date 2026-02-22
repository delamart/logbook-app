const fileInput = document.getElementById('file-input');
const csvInput = document.getElementById('csv-input'); // New ref
const editor = document.getElementById('editor');
const image = document.getElementById('image');
const reviewImage = document.getElementById('review-image'); // New ref
const themeBtn = document.getElementById('theme-btn');
let cropper;
let currentExtractedEntries = [];
let allEntries = []; // Master list for sorting/filtering
let editingRowId = null;
let currentBlob = null; // Store for re-scanning
let sortCol = 'date';
let sortAsc = false;
let timeFilterMonths = 'all';
// ---- Custom Dialog Logic ----
function showCustomDialog(message, isConfirm = false) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('custom-dialog-overlay');
        const msgEl = document.getElementById('custom-dialog-message');
        const cancelBtn = document.getElementById('custom-dialog-cancel');
        const confirmBtn = document.getElementById('custom-dialog-confirm');

        msgEl.textContent = message;

        cancelBtn.style.display = isConfirm ? 'inline-block' : 'none';
        overlay.classList.add('active');

        const cleanup = () => {
            overlay.classList.remove('active');
            confirmBtn.onclick = null;
            cancelBtn.onclick = null;
        };

        confirmBtn.onclick = () => {
            cleanup();
            resolve(true);
        };

        cancelBtn.onclick = () => {
            cleanup();
            resolve(false);
        };
    });
}

const customAlert = (msg) => showCustomDialog(msg, false);
const customConfirm = (msg) => showCustomDialog(msg, true);

let map;

// ---- CSV Import Listener ----
if (csvInput) {
    csvInput.addEventListener('change', function (e) {
        if (this.files && this.files[0]) {


            const formData = new FormData();
            formData.append('file', this.files[0]);

            // Show global loading if possible, or just alert state
            // Try to find the button in the specific location, or fallback
            // Since we extracted to sidebar, the button might be there
            const btn = document.querySelector('a[onclick*="csv-input"]') || document.querySelector('button[onclick*="csv-input"]');
            const originalText = btn ? btn.innerText : "Import";
            if (btn) {
                btn.innerText = "⏳ Importing...";
                // btn.disabled = true; // Link/Anchor can't be disabled easily
            }

            fetch('/import/foreflight', {
                method: 'POST',
                body: formData
            })
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        customAlert("Error: " + data.message);
                        return;
                    }

                    // Use the existing validation UI
                    document.getElementById('loader').style.display = 'none'; // Ensure loader is off

                    // We might need to hide other things or switch views if we were on a different tab?
                    // But here we                    
                    showValidation(data, true);

                    // Scroll to validation
                    document.getElementById('validation-zone').scrollIntoView({ behavior: 'smooth' });
                })
                .catch(err => {
                    console.error(err);
                    customAlert("Error processing CSV: " + err);
                })
                .finally(() => {
                    this.value = ''; // Reset
                    if (btn) {
                        btn.innerText = originalText;
                    }
                });
        }
    });
}

// Theme Logic
function initTheme() {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (saved === 'dark' || (!saved && prefersDark)) {
        document.body.classList.add('dark');
        if (themeBtn) themeBtn.textContent = '☀️';
    } else {
        document.body.classList.remove('dark');
        if (themeBtn) themeBtn.textContent = '🌙';
    }
}

function toggleTheme() {
    document.body.classList.toggle('dark');
    const isDark = document.body.classList.contains('dark');
    if (themeBtn) themeBtn.textContent = isDark ? '☀️' : '🌙';
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// Init theme immediately
initTheme();


// Labels Map
const FIELD_LABELS = {
    date: "Date (YYYY-MM-DD)",
    departure_place: "Departure Place",
    departure_time: "Dep Time",
    arrival_place: "Arrival Place",
    arrival_time: "Arr Time",
    aircraft_model: "Aircraft Model",
    aircraft_registration: "Registration",
    single_pilot_se: "Single Pilot SE",
    single_pilot_me: "Single Pilot ME",
    multi_pilot: "Multi Pilot",
    total_flight_time: "Total Flight Time",
    name_pic: "PIC Name",
    landings_day: "Landings (Day)",
    landings_night: "Landings (Night)",
    time_night: "Night Time",
    time_ifr: "IFR Time",
    time_pic: "PIC Time",
    time_copi: "Co-Pilot Time",
    time_dual: "Dual Time",
    time_instructor: "Instructor Time",
    remarks: "Remarks"
};


window.addEventListener('load', () => {
    // Common init
    initTheme();

    // Page Specific Init
    if (document.getElementById('master-table')) {
        loadAllEntries();
    } else if (document.getElementById('recent-table')) {
        loadRecentEntries();
        loadStats();
    }

    if (document.getElementById('map')) {
        initMap();
    }

    if (document.querySelector('.model-select')) {
        loadModels();
    }

    fetchDefaultPrompt();
});

if (fileInput) {
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) startEditor(file);
    });
}

function loadModels() {
    const selects = document.querySelectorAll('.model-select');
    if (selects.length === 0) return;

    fetch('/api/models')
        .then(r => r.json())
        .then(data => {
            const options = data.models.map(m =>
                `<option value="${m}" ${m.includes('flash') ? 'selected' : ''}>${m}</option>`
            ).join('');

            selects.forEach(s => s.innerHTML = options);
        })
        .catch(err => {
            console.error("Failed to load models", err);
            selects.forEach(s => s.innerHTML = '<option value="models/gemini-2.0-flash">Gemini 2.0 Flash (Fallback)</option>');
        });
}

function loadRecentEntries() {
    fetch('/entries/')
        .then(r => r.json())
        .then(entries => {
            const tbody = document.getElementById('recent-tbody');
            if (!tbody) return;
            const recent = entries.slice(0, 5); // Top 5

            if (recent.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No flights yet.</td></tr>';
                return;
            }

            tbody.innerHTML = recent.map(e => `
                <tr>
                    <td>${e.date}</td>
                    <td>${e.departure_place || '-'} ➝ ${e.arrival_place || '-'}</td>
                    <td>${e.aircraft_registration || '-'}</td>
                    <td>${formatDuration(e.total_flight_time)}</td>
                </tr>
            `).join('');
        });
}

function loadStats() {
    fetch('/entries/')
        .then(r => r.json())
        .then(entries => {
            calculateStats(entries);
        });
}

function initMap() {
    const mapEl = document.getElementById('map');
    if (!mapEl) return;

    map = L.map('map').setView([20, 0], 2);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO'
    }).addTo(map);

    // Dark Mode Map Handling
    if (document.body.classList.contains('dark')) {
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap &copy; CARTO'
        }).addTo(map);
    }

    Promise.all([
        fetch('/map_data').then(r => r.json()),
        fetch('/entries/').then(r => r.json())
    ]).then(([airports, entries]) => {

        const airportIcon = L.divIcon({
            className: 'custom-div-icon',
            html: "<div style='background-color:#3b82f6; width:8px; height:8px; border-radius:50%; border:1px solid white;'></div>",
            iconSize: [8, 8],
            iconAnchor: [4, 4]
        });

        // Flight Colors
        const colors = [
            '#e11d48', '#2563eb', '#16a34a', '#d97706', '#7c3aed', '#db2777',
            '#0891b2', '#84cc16', '#f59e0b', '#6366f1'
        ];
        const aircraftColors = {};
        let colorIndex = 0;

        // Draw Lines
        entries.forEach(e => {
            if (e.departure_place && e.arrival_place) {
                const dep = e.departure_place.toUpperCase().trim();
                const arr = e.arrival_place.toUpperCase().trim();

                if (airports[dep] && airports[arr]) {
                    const latlngs = [
                        [airports[dep].lat, airports[dep].lon],
                        [airports[arr].lat, airports[arr].lon]
                    ];
                    // Assign color to aircraft
                    const reg = e.aircraft_registration || 'Unknown';
                    if (!aircraftColors[reg]) {
                        aircraftColors[reg] = colors[colorIndex % colors.length];
                        colorIndex++;
                    }

                    L.polyline(latlngs, {
                        color: aircraftColors[reg],
                        weight: 2,
                        opacity: 0.8
                    }).addTo(map);
                }
            }
        });

        // Draw Markers (only used)
        const markersData = [];
        Object.entries(airports).forEach(([code, data]) => {
            const latlng = [data.lat, data.lon];
            L.marker(latlng, { icon: airportIcon }).addTo(map)
                .bindPopup(`<b>${code}</b><br>${data.name}`);
            markersData.push(latlng);
        });

        if (markersData.length > 0) {
            map.fitBounds(markersData, { padding: [50, 50] });
        }

        // Add Legend
        const legend = L.control({ position: 'bottomright' });
        legend.onAdd = function (map) {
            const div = L.DomUtil.create('div', 'info legend');
            div.style.background = 'var(--surface)';
            div.style.padding = '10px';
            div.style.border = '1px solid var(--border)';
            div.style.borderRadius = '8px';
            div.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
            div.style.fontSize = '0.85rem';

            div.innerHTML = '<strong>Aircraft</strong><br>';

            Object.keys(aircraftColors).sort().forEach(reg => {
                const color = aircraftColors[reg];
                div.innerHTML += `
                    <div style="display:flex; align-items:center; gap:5px; margin-top:4px;">
                        <i style="background:${color}; width:12px; height:12px; border-radius:2px; display:inline-block;"></i>
                        <span style="color:var(--text);">${reg}</span>
                    </div>
                `;
            });
            return div;
        };
        legend.addTo(map);
    });
}

// Initial Prompt Loader
function fetchDefaultPrompt() {
    fetch('/prompt')
        .then(r => r.json())
        .then(data => {
            const promptEditor = document.getElementById('prompt-editor');
            const initialPromptEditor = document.getElementById('initial-prompt-editor');
            if (promptEditor) promptEditor.value = data.prompt;
            if (initialPromptEditor) initialPromptEditor.value = data.prompt;
        });
}

function startEditor(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        image.src = e.target.result;
        editor.style.display = 'block';
        document.getElementById('validation-zone').style.display = 'none';

        if (cropper) cropper.destroy();
        cropper = new Cropper(image, { viewMode: 1, autoCropArea: 0.95 });
    };
    reader.readAsDataURL(file);
}

function processImage() {
    if (!cropper) return;
    document.getElementById('loader').style.display = 'block';

    // Set review image source immediately from current crop
    reviewImage.src = cropper.getCroppedCanvas().toDataURL();

    // Get prompt from initial editor
    const initialPrompt = document.getElementById('initial-prompt-editor').value;
    const initialModel = document.getElementById('initial-model-select').value;

    cropper.getCroppedCanvas().toBlob((blob) => {
        currentBlob = blob; // Save for later
        uploadBlob(blob, initialPrompt, initialModel);
    }, 'image/png');
}

function uploadBlob(blob, customPrompt = null, modelName = null) {
    const formData = new FormData();
    formData.append('file', blob, 'edited_logbook.png');
    if (customPrompt) {
        formData.append('custom_prompt', customPrompt);
    }

    // Append Selected Model
    if (modelName) {
        formData.append('model', modelName);
    }

    fetch('/upload/', { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            document.getElementById('loader').style.display = 'none';
            editor.style.display = 'none'; // Hide editor if open

            // Sync Prompt to Validation Editor
            if (customPrompt) {
                document.getElementById('prompt-editor').value = customPrompt;
            }
            // Sync Model to Validation Editor
            if (modelName) {
                const valSelect = document.getElementById('validation-model-select');
                if (valSelect) valSelect.value = modelName;
            }

            showValidation(data);
        })
        .catch(err => customAlert("Upload error: " + err));
}

function rescanWithPrompt() {
    if (!currentBlob) { customAlert("No image to scan!"); return; }
    const newPrompt = document.getElementById('prompt-editor').value;
    const newModel = document.getElementById('validation-model-select').value;

    // Show loader in validation table
    document.getElementById('validation-table').innerHTML = '<div style="text-align:center; padding: 20px;">⏳ Re-scanning with new prompt...</div>';

    uploadBlob(currentBlob, newPrompt, newModel);
}

function showValidation(data, isCSV = false) {
    document.getElementById('validation-zone').style.display = 'block';

    // Toggle AI-specific elements
    const displayStyle = isCSV ? 'none' : 'block';
    const aiSettings = document.getElementById('ai-settings-details');
    const reviewImage = document.getElementById('review-image-container');
    const debugResponse = document.getElementById('debug-response-details');

    if (aiSettings) aiSettings.style.display = displayStyle;
    if (reviewImage) reviewImage.style.display = displayStyle;
    if (debugResponse) debugResponse.style.display = displayStyle;

    // Assign keys for React-like behavior (editing)
    currentExtractedEntries = (data.extracted_entries || []).map((e, i) => ({ ...e, id: `temp-${i}` }));

    // Only show debug if not CSV (or maybe show CSV headers?)
    if (!isCSV) {
        document.getElementById('debug-pre').textContent = JSON.stringify(data.raw_json, null, 2);
    }

    document.getElementById('validation-table').innerHTML = renderTable(currentExtractedEntries, true);
}

function saveEntries() {
    if (currentExtractedEntries.length === 0) return;
    // Strip temp IDs
    const payload = currentExtractedEntries.map(({ id, ...rest }) => rest);

    fetch('/save_entries/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(() => {
        document.getElementById('validation-zone').style.display = 'none';
        loadAllEntries();
        customAlert("Import Successful!");

        // Reset state for new scan
        currentExtractedEntries = [];
        fileInput.value = '';
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        document.getElementById('editor').style.display = 'none';
    });
}

function loadAllEntries() {
    fetch('/entries/')
        .then(r => r.json())
        .then(entries => {
            allEntries = entries;
            renderMasterTable();
            calculateStats(entries);
        });
}

function calculateStats(entries) {
    let totalTime = 0;
    let totalPic = 0;
    let totalLandings = 0;
    const aircraft = new Set();
    const airports = new Set();

    entries.forEach(e => {
        totalTime += (e.total_flight_time || 0);
        totalPic += (e.time_pic || 0);
        totalLandings += (e.landings_day || 0) + (e.landings_night || 0);
        if (e.aircraft_registration) aircraft.add(e.aircraft_registration);
        if (e.departure_place) airports.add(e.departure_place.toUpperCase().trim());
        if (e.arrival_place) airports.add(e.arrival_place.toUpperCase().trim());
    });

    if (document.getElementById('stat-total-time')) document.getElementById('stat-total-time').innerText = formatDuration(totalTime);
    if (document.getElementById('stat-pic-time')) document.getElementById('stat-pic-time').innerText = formatDuration(totalPic);
    if (document.getElementById('stat-landings')) document.getElementById('stat-landings').innerText = totalLandings;
    if (document.getElementById('stat-aircraft')) document.getElementById('stat-aircraft').innerText = aircraft.size;
    if (document.getElementById('stat-airports')) document.getElementById('stat-airports').innerText = airports.size;

    // Generate/Update Datalist for Airports Autocomplete
    let datalist = document.getElementById('airports-list');
    if (!datalist) {
        datalist = document.createElement('datalist');
        datalist.id = 'airports-list';
        document.body.appendChild(datalist);
    }
    datalist.innerHTML = Array.from(airports).sort().map(a => `<option value="${a}">`).join('');
}

function renderMasterTable() {
    const tbody = document.getElementById('master-tbody');
    if (!tbody) return;

    let filtered = allEntries;

    // 1. Time Filter
    if (timeFilterMonths !== 'all') {
        const cutoff = new Date();
        cutoff.setMonth(cutoff.getMonth() - parseInt(timeFilterMonths));
        filtered = filtered.filter(e => new Date(e.date) >= cutoff);
    }

    // 2. Text Filter
    const filterInput = document.getElementById('filter-input');
    if (filterInput) {
        const q = filterInput.value.toLowerCase();
        if (q) {
            filtered = filtered.filter(e => Object.values(e).some(val => String(val).toLowerCase().includes(q)));
        }
    }

    // Sort
    filtered.sort((a, b) => {
        let valA = a[sortCol];
        let valB = b[sortCol];
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();

        if (valA < valB) return sortAsc ? -1 : 1;
        if (valA > valB) return sortAsc ? 1 : -1;
        return 0;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="18" style="text-align: center; padding: 40px;">No entries found.</td></tr>';
    } else {
        tbody.innerHTML = renderTableRows(filtered, true);
    }
}

function toggleEdit(id) {
    editingRowId = id;
    renderMasterTable();
    if (document.getElementById('validation-zone').style.display === 'block') {
        document.getElementById('validation-table').innerHTML = renderTable(currentExtractedEntries, true);
    }
}

function cancelEdit() {
    editingRowId = null;
    renderMasterTable();
    if (document.getElementById('validation-zone').style.display === 'block') {
        document.getElementById('validation-table').innerHTML = renderTable(currentExtractedEntries, true);
    }
}

function saveInline(id) {
    const row = document.querySelector(`tr[data-id="${id}"]`);
    const updateData = {};
    const inputs = row.querySelectorAll('input');

    // Helper to parse HH:MM or decimal back to integer minutes
    const parseDuration = (val) => {
        if (!val) return null;
        if (typeof val === 'string' && val.includes(':')) {
            const parts = val.split(':');
            const h = parseInt(parts[0], 10) || 0;
            const m = parseInt(parts[1], 10) || 0;
            return (h * 60) + m;
        }
        const floatVal = parseFloat(val);
        return isNaN(floatVal) ? null : Math.round(floatVal * 60);
    };

    inputs.forEach(input => {
        const key = input.getAttribute('data-key');
        if (key) {
            let val = input.value.trim();
            if (val === '') {
                val = null;
            } else if (['single_pilot_se', 'single_pilot_me', 'multi_pilot', 'total_flight_time', 'time_night', 'time_ifr', 'time_pic', 'time_copi', 'time_dual', 'time_instructor'].includes(key)) {
                val = parseDuration(val);
            } else if (['landings_day', 'landings_night'].includes(key)) {
                val = parseInt(val, 10);
                if (isNaN(val)) val = 0;
            }
            updateData[key] = val;
        }
    });
    // Handle Temp/Local Edit
    if (String(id).startsWith('temp-')) {
        const idx = currentExtractedEntries.findIndex(e => e.id === id);
        if (idx !== -1) {
            Object.assign(currentExtractedEntries[idx], updateData);
            // Keep ID
            currentExtractedEntries[idx].id = id;
            editingRowId = null;
            document.getElementById('validation-table').innerHTML = renderTable(currentExtractedEntries, true);
        }
        return;
    }

    data.id = id;

    fetch(`/entries/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(() => {
        editingRowId = null;
        loadAllEntries();
    });
}

function filterEntries() {
    renderMasterTable();
}

function setTimeFilter(val) {
    timeFilterMonths = val;
    renderMasterTable();
}

function sortBy(col) {
    if (sortCol === col) sortAsc = !sortAsc;
    else {
        sortCol = col;
        sortAsc = true;
    }
    renderMasterTable();
}

function addEntry() {
    // Create a blank entry immediately
    const today = new Date().toISOString().split('T')[0];
    fetch('/entries/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            date: today,
            remarks: "New Entry"
        })
    }).then(r => r.json()).then(entry => {
        // Reload and jump to edit mode
        // We need to set a flag or just reload and search?
        // loadAllEntries is async. We need to chain it.
        // But loadAllEntries doesn't return a promise.
        // Let's modify loadAllEntries or just manually handle it here.

        // Fetch all, update global, render, then toggle edit.
        fetch('/entries/')
            .then(r => r.json())
            .then(entries => {
                allEntries = entries;
                renderMasterTable();
                setTimeout(() => {
                    const row = document.querySelector(`tr[data-id="${entry.id}"]`);
                    if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    toggleEdit(entry.id);
                }, 100);
            });
    });
}

async function deleteAllEntries() {
    if (await customConfirm("Are you sure you want to delete ALL entries? This cannot be undone.")) {
        if (await customConfirm("Really? Delete everything?")) {
            fetch('/entries/all', { method: 'DELETE' })
                .then(() => loadAllEntries());
        }
    }
}

async function deleteEntry(id) {
    if (!(await customConfirm("Are you sure you want to delete this entry?"))) return;

    if (String(id).startsWith('temp-')) {
        currentExtractedEntries = currentExtractedEntries.filter(e => e.id !== id);
        document.getElementById('validation-table').innerHTML = renderTable(currentExtractedEntries, true);
        return;
    }

    fetch(`/entries/${id}`, { method: 'DELETE' })
        .then(() => loadAllEntries());
}



function formatDuration(minutesArray) {
    if (minutesArray == null || minutesArray === '') return '-';
    // The database now stores INT minutes
    const mins = parseInt(minutesArray, 10);
    if (isNaN(mins)) return '-';
    if (mins === 0) return '0:00';

    const hours = Math.floor(mins / 60);
    const m = mins % 60;
    return `${hours}:${m.toString().padStart(2, '0')}`;
}

// Utility to escape HTML to prevent XSS in table rendering
function escapeAttribute(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function renderTable(entries, showActions) {
    return `
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 40px; padding: 12px 16px;"><input type="checkbox" class="validationAllCheckbox" onchange="toggleSelectAll(this.checked, true)"></th>
                        <th style="min-width: 90px;">Date</th>
                        <th>Depart</th>
                        <th>Arrive</th>
                        <th>Aircraft</th>
                        <th>SE</th>
                        <th>ME</th>
                        <th>Multi</th>
                        <th>Total</th>
                        <th>PIC Name</th>
                        <th>Ldgs</th>
                        <th>Night</th>
                        <th>IFR</th>
                        <th>PIC</th>
                        <th>Copi</th>
                        <th>Dual</th>
                        <th>Instr</th>
                        <th>Remarks</th>
                        ${showActions ? '<th style="text-align: right;">Actions</th>' : ''}
                    </tr>
                </thead>
                <tbody>${renderTableRows(entries, showActions)}</tbody>
            </table>
        </div>
    `;
}

function formatDatePretty(dateStr) {
    if (!dateStr) return { main: '-', sub: '' };
    const parts = dateStr.split('-');
    if (parts.length !== 3) return { main: dateStr, sub: '' };

    const date = new Date(parts[0], parts[1] - 1, parts[2]);
    const months = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."];
    const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

    return {
        main: `${days[date.getDay()]} ${months[date.getMonth()]} ${date.getDate()}`,
        sub: date.getFullYear()
    };
}

function renderTableRows(entries, showActions) {
    return entries.map(e => {
        const dateObj = formatDatePretty(e.date);
        // Use loose equality (==) to handle string/number ID mismatch
        if (editingRowId == e.id && showActions) {
            return `
            <tr data-id="${e.id}" class="editing">
                <td style="width: 40px; padding: 12px 16px;"><input type="checkbox" class="row-checkbox" data-id="${e.id}" onchange="updateSelectedCount()"></td>
                <td><input data-key="date" type="date" value="${e.date || ''}" style="width: 120px; font-family: var(--font-mono);"></td>
                <td>
                    <input data-key="departure_place" list="airports-list" value="${escapeAttribute(e.departure_place)}" placeholder="Place" style="width: 70px; margin-bottom: 2px;">
                    <input data-key="departure_time" type="text" value="${escapeAttribute(e.departure_time)}" placeholder="HH:MM" style="width: 70px; font-family: var(--font-mono); font-size: 0.75rem;">
                </td>
                <td>
                    <input data-key="arrival_place" list="airports-list" value="${escapeAttribute(e.arrival_place)}" placeholder="Place" style="width: 70px; margin-bottom: 2px;">
                    <input data-key="arrival_time" type="text" value="${escapeAttribute(e.arrival_time)}" placeholder="HH:MM" style="width: 70px; font-family: var(--font-mono); font-size: 0.75rem;">
                </td>
                <td>
                    <input data-key="aircraft_registration" value="${escapeAttribute(e.aircraft_registration)}" placeholder="Reg" style="width: 80px; margin-bottom: 2px;">
                    <input data-key="aircraft_model" value="${escapeAttribute(e.aircraft_model)}" placeholder="Model" style="width: 80px;">
                </td>
                
                <!-- Durations (Formatted HH:MM for easy editing) -->
                <td><input data-key="single_pilot_se" value="${formatDuration(e.single_pilot_se) !== '-' ? formatDuration(e.single_pilot_se) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                <td><input data-key="single_pilot_me" value="${formatDuration(e.single_pilot_me) !== '-' ? formatDuration(e.single_pilot_me) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                <td><input data-key="multi_pilot" value="${formatDuration(e.multi_pilot) !== '-' ? formatDuration(e.multi_pilot) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                <td><input data-key="total_flight_time" value="${formatDuration(e.total_flight_time) !== '-' ? formatDuration(e.total_flight_time) : ''}" placeholder="HH:MM" style="width: 60px; font-weight: 500;"></td>
                
                <td><input data-key="name_pic" value="${escapeAttribute(e.name_pic)}" style="width: 100px;"></td>
                
                <!-- Landings -->
                <td style="display:flex; flex-direction:column; gap:2px;">
                    <input data-key="landings_day" value="${e.landings_day || 0}" placeholder="Day" style="width: 50px;">
                    <input data-key="landings_night" value="${e.landings_night || 0}" placeholder="Night" style="width: 50px;">
                </td>
                
                <td><input data-key="time_night" value="${formatDuration(e.time_night) !== '-' ? formatDuration(e.time_night) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                <td><input data-key="time_ifr" value="${formatDuration(e.time_ifr) !== '-' ? formatDuration(e.time_ifr) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                
                <td><input data-key="time_pic" value="${formatDuration(e.time_pic) !== '-' ? formatDuration(e.time_pic) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                <td><input data-key="time_copi" value="${formatDuration(e.time_copi) !== '-' ? formatDuration(e.time_copi) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                <td><input data-key="time_dual" value="${formatDuration(e.time_dual) !== '-' ? formatDuration(e.time_dual) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                <td><input data-key="time_instructor" value="${formatDuration(e.time_instructor) !== '-' ? formatDuration(e.time_instructor) : ''}" placeholder="HH:MM" style="width: 60px;"></td>
                
                <td><input data-key="remarks" value="${escapeAttribute(e.remarks)}" style="width: 180px;"></td>
                
                <td>
                    <div class="actions">
                        <button class="btn-icon save" onclick="saveInline('${e.id}')" title="Save">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                        </button>
                        <button class="btn-icon cancel" onclick="cancelEdit()" title="Cancel">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                        </button>
                    </div>
                </td>
            </tr>
            `;
        }

        return `
        <tr data-id="${e.id}">
            <td style="width: 40px; padding: 12px 16px;">
                <input type="checkbox" class="row-checkbox" data-id="${e.id}" onchange="updateSelectedCount()">
            </td>
            <td>
                <div style="font-weight:500; white-space:nowrap;">${dateObj.main}</div>
                <div style="font-size:0.8em; color:var(--text-light);">${dateObj.sub}</div>
            </td>
            <td>
                <div style="font-weight:500;">${e.departure_place || '-'}</div>
                <div style="font-size:0.8em; color:var(--text-light);">${e.departure_time || ''}</div>
            </td>
            <td>
                <div style="font-weight:500;">${e.arrival_place || '-'}</div>
                <div style="font-size:0.8em; color:var(--text-light);">${e.arrival_time || ''}</div>
            </td>
            <td>
                <div style="font-weight:500;">${e.aircraft_registration || '-'}</div>
                <div style="font-size:0.8em; color:var(--text-light);">${e.aircraft_model || ''}</div>
            </td>
            
            <!-- Durations -->
            <td>${formatDuration(e.single_pilot_se)}</td>
            <td>${formatDuration(e.single_pilot_me)}</td>
            <td>${formatDuration(e.multi_pilot)}</td>
            <td style="font-weight: 500;">${formatDuration(e.total_flight_time)}</td>
            
            <td>${e.name_pic || '-'}</td>
            
            <!-- Landings -->
            <td>${(e.landings_day || 0)}/${(e.landings_night || 0)}</td>
            
            <!-- Conditions -->
            <td>${formatDuration(e.time_night)}</td>
            <td>${formatDuration(e.time_ifr)}</td>
            
            <!-- Function -->
            <td>${formatDuration(e.time_pic)}</td>
            <td>${formatDuration(e.time_copi)}</td>
            <td>${formatDuration(e.time_dual)}</td>
            <td>${formatDuration(e.time_instructor)}</td>
            
            <td style="color: var(--text-light); font-size: 0.85em; max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${e.remarks || ''}</td>
            
            ${showActions ? `
                <td>
                    <div class="actions">
                        <button class="btn-icon edit" onclick="toggleEdit('${e.id}')" title="Edit">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" /></svg>
                        </button>
                        <button class="btn-icon delete" onclick="deleteEntry('${e.id}')" title="Delete">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
                        </button>
                    </div>
                </td>
            ` : ''}
        </tr>
    `}).join('');
}

// Checkbox & Bulk Actions
function toggleSelectAll(checked, isValidation = false) {
    const context = isValidation ? '#validation-table' : '#master-table';
    const checkboxes = document.querySelectorAll(`${context} .row-checkbox`);
    checkboxes.forEach(cb => cb.checked = checked);
    updateSelectedCount(isValidation);
}

function updateSelectedCount(isValidation = false) {
    const context = isValidation ? '#validation-table' : '#master-table';
    const btnId = isValidation ? 'btn-delete-selected-validation' : 'btn-delete-selected';
    const masterCbId = isValidation ? '.validationAllCheckbox' : '#selectAllCheckbox';

    const checkedBoxes = document.querySelectorAll(`${context} .row-checkbox:checked`);
    const deleteBtn = document.getElementById(btnId);
    if (!deleteBtn) return;

    const count = checkedBoxes.length;
    if (count > 0) {
        deleteBtn.disabled = false;
        deleteBtn.style.opacity = '1';
        deleteBtn.style.cursor = 'pointer';
        deleteBtn.innerText = `Delete Selected (${count})`;
    } else {
        deleteBtn.disabled = true;
        deleteBtn.style.opacity = '0.5';
        deleteBtn.style.cursor = 'not-allowed';
        deleteBtn.innerText = `Delete Selected (0)`;

        const selectAllCb = document.querySelector(masterCbId);
        if (selectAllCb) selectAllCb.checked = false;
    }
}

function deleteSelectedEntries(isValidation = false) {
    const context = isValidation ? '#validation-table' : '#master-table';
    const checkedBoxes = Array.from(document.querySelectorAll(`${context} .row-checkbox:checked`));
    if (checkedBoxes.length === 0) return;

    customConfirm(`Are you sure you want to delete ${checkedBoxes.length} selected entries? This cannot be undone.`).then(confirmed => {
        if (!confirmed) return;

        const idsToDelete = checkedBoxes.map(cb => cb.getAttribute('data-id'));

        if (isValidation) {
            // In-Memory deletion for Validation zone
            currentExtractedEntries = currentExtractedEntries.filter(e => !idsToDelete.includes(e.id));
            document.getElementById('validation-table').innerHTML = renderTable(currentExtractedEntries, true);
            const selectAllCb = document.querySelector('.validationAllCheckbox');
            if (selectAllCb) selectAllCb.checked = false;
            updateSelectedCount(true);
            return;
        }

        // Execute all deletions concurrently on the backend
        Promise.all(idsToDelete.map(id => {
            return fetch(`/entries/${id}`, { method: 'DELETE' });
        }))
            .then(() => {
                customAlert(`Successfully deleted ${checkedBoxes.length} entries.`).then(() => {
                    const selectAllCb = document.getElementById('selectAllCheckbox');
                    if (selectAllCb) selectAllCb.checked = false;
                    document.querySelectorAll('#master-table .row-checkbox').forEach(cb => cb.checked = false); // Ensure only master table checkboxes are unchecked
                    updateSelectedCount(); // reset button text immediately
                    loadAllEntries(); // refetch and render table
                });
            })
            .catch(err => {
                console.error(err);
                customAlert("An error occurred during bulk deletion. Please refer to console logs.");
            });
    });
}
