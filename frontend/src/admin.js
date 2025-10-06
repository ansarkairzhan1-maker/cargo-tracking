// frontend/src/admin.js

// === AUTHENTICATION CHECK ===
const USER_DATA = JSON.parse(localStorage.getItem('user_data') || '{}');
const AUTH_TOKEN = localStorage.getItem('access_token');

if (!AUTH_TOKEN || USER_DATA.role !== 'admin') {
    alert('Admin access required');
    window.location.href = '/login';
}

// === AUTH FETCH HELPER ===
async function authFetch(url, options = {}) {
    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${AUTH_TOKEN}`
    };
    
    const response = await fetch(url, options);
    
    if (response.status === 401 || response.status === 403) {
        alert('Session expired or access denied');
        localStorage.clear();
        window.location.href = '/login';
    }
    
    return response;
}

// === CALENDAR VARIABLES ===
let calendar;
let currentSelectedDate = null;
let currentDateTracks = [];

// === DOM INITIALIZATION ===
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("add-user-form");
    const usersTableContainer = document.getElementById("users-table-container");
    const usersTableBody = document.querySelector("#users-table tbody");
    const toggleBtn = document.getElementById("toggle-users-btn");
    const uploadBtn = document.getElementById("upload-tracks-btn");
    const dateInput = document.getElementById("china-date");
    const fileInput = document.getElementById("tracks-file");
    const statusSelect = document.getElementById("track-status-select");

    // Display admin name
    const adminNameElement = document.getElementById('admin-name');
    if (adminNameElement && USER_DATA.name) {
        adminNameElement.textContent = USER_DATA.name;
    }

    // === LOGOUT HANDLER ===
    document.querySelector('.logout')?.addEventListener('click', (e) => {
        e.preventDefault();
        localStorage.clear();
        window.location.href = '/login';
    });

    // === LOAD USERS FUNCTION ===
    async function loadUsers() {
        usersTableBody.innerHTML = "<tr><td colspan='7'>Загрузка...</td></tr>";
        try {
            const res = await authFetch("/api/users");
            if (!res.ok) throw new Error("Ошибка загрузки пользователей");
            
            const users = await res.json();
            usersTableBody.innerHTML = "";
            
            if (users.length === 0) {
                usersTableBody.innerHTML = "<tr><td colspan='7'>Нет пользователей</td></tr>";
                return;
            }
            
            users.forEach(user => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${user.personal_code}</td>
                    <td>${user.name}</td>
                    <td>${user.email || 'N/A'}</td>
                    <td>${user.whatsapp}</td>
                    <td>${user.branch}</td>
                    <td><span class="badge bg-${user.role === 'admin' ? 'danger' : 'primary'}">${user.role}</span></td>
                    <td>
                        <button class="btn btn-sm btn-danger delete-btn" data-id="${user.id}">Удалить</button>
                    </td>
                `;
                usersTableBody.appendChild(tr);
            });
        } catch (err) {
            console.error("Ошибка загрузки пользователей:", err);
            usersTableBody.innerHTML = "<tr><td colspan='7' class='text-danger'>Ошибка загрузки</td></tr>";
        }
    }

    // === ADD USER FORM HANDLER ===
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const formData = new FormData();
        formData.append('name', document.getElementById('user-name').value);
        formData.append('email', document.getElementById('user-email').value);
        formData.append('password', document.getElementById('user-password').value);
        formData.append('whatsapp', document.getElementById('user-whatsapp').value);
        formData.append('branch', document.getElementById('user-branch').value);
        formData.append('personal_code', document.getElementById('user-personal-code').value || '');
        formData.append('role', document.getElementById('user-role')?.value || 'client');
        
        try {
            const response = await authFetch('/api/users', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                const data = await response.json();
                alert(`✅ Пользователь создан успешно!\nИмя: ${data.name}\nКод: ${data.personal_code}\nEmail: ${data.email}`);
                form.reset();
                
                if (usersTableContainer.style.display !== "none") {
                    loadUsers();
                }
            } else {
                const error = await response.json();
                alert('❌ Ошибка: ' + (error.detail || 'Не удалось создать пользователя'));
            }
        } catch (error) {
            console.error('Error creating user:', error);
            alert('❌ Ошибка сети при создании пользователя');
        }
    });

    // === TOGGLE USERS TABLE ===
    toggleBtn.addEventListener("click", () => {
        if (usersTableContainer.style.display === "none") {
            usersTableContainer.style.display = "block";
            loadUsers();
            toggleBtn.textContent = "Скрыть";
        } else {
            usersTableContainer.style.display = "none";
            toggleBtn.textContent = "Показать";
        }
    });

    // === DELETE USER HANDLER ===
    usersTableBody.addEventListener("click", async (e) => {
        if (e.target.classList.contains("delete-btn")) {
            const userId = e.target.dataset.id;
            if (!confirm("Удалить пользователя?")) return;
            
            try {
                const res = await authFetch(`/api/users/${userId}`, { 
                    method: "DELETE" 
                });
                
                if (!res.ok) throw new Error("Ошибка удаления");
                
                alert("✅ Пользователь удален");
                loadUsers();
            } catch (err) {
                console.error(err);
                alert("❌ Не удалось удалить пользователя");
            }
        }
    });

    // === UPLOAD TRACKS HANDLER ===
    uploadBtn.addEventListener("click", async () => {
        const file = fileInput.files[0];
        const departureDate = dateInput.value;
        const status = statusSelect.value;

        if (!file || !departureDate || status === "Выберите статус для обновления") {
            alert("⚠️ Пожалуйста, выберите файл, дату отправления и статус.");
            return;
        }

        uploadBtn.disabled = true;
        const originalText = uploadBtn.textContent;
        uploadBtn.textContent = "Загрузка...";

        const formData = new FormData();
        formData.append("file", file);
        formData.append("departure_date", departureDate);
        formData.append("status", status);

        try {
            const res = await authFetch("/api/tracks", {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || "Ошибка загрузки треков");
            }

            const result = await res.json();

            let successMessage = `✅ Успешно обработано треков: ${result.count}\n`;
            successMessage += `📅 Дата отправления: ${departureDate}\n`;
            successMessage += `📦 Статус: ${status}\n`;
            successMessage += `📄 Файл: ${file.name}\n`;

            if (result.total_errors > 0) {
                successMessage += `\n⚠️ Ошибок при обработке: ${result.total_errors}`;
                if (result.errors && result.errors.length > 0) {
                    successMessage += `\nПервые ошибки:\n${result.errors.join('\n')}`;
                }
            }

            if (result.processed_tracks && result.processed_tracks.length > 0) {
                successMessage += `\n\n✅ Примеры обработанных треков:\n${result.processed_tracks.join(', ')}`;
            }

            alert(successMessage);

            fileInput.value = "";
            dateInput.value = "";
            statusSelect.value = "Выберите статус для обновления";
            
            // Reload calendar if exists
            if (calendar) {
                calendar.refetchEvents();
            }

        } catch (err) {
            console.error("Upload error:", err);
            alert(`❌ Ошибка загрузки: ${err.message}`);
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.textContent = originalText;
        }
    });

    // === TRACK SEARCH ===
    const trackSearchBtn = document.getElementById("track-search-btn");
    const trackSearchInput = document.getElementById("track-search");
    const trackResultDiv = document.getElementById("track-result");

    if (trackSearchBtn && trackSearchInput && trackResultDiv) {
        trackSearchBtn.addEventListener("click", async () => {
            const trackNumber = trackSearchInput.value.trim().toUpperCase();
            if (!trackNumber) {
                alert("⚠️ Введите трек-номер");
                return;
            }

            trackResultDiv.innerHTML = "<p>🔍 Поиск...</p>";

            try {
                const res = await fetch(`/api/tracks/search/${trackNumber}`);
                const data = await res.json();

                if (res.ok) {
                    trackResultDiv.innerHTML = `
                        <div class="alert alert-success">
                            <h5>Трек найден: ${data.track_number}</h5>
                            <p><strong>Статус:</strong> ${data.current_status}</p>
                            <p><strong>Привязан:</strong> ${data.is_assigned ? 'Да' : 'Нет'}</p>
                            ${data.personal_code ? `<p><strong>Код клиента:</strong> ${data.personal_code}</p>` : ''}
                            ${data.departure_date ? `<p><strong>Дата отправления:</strong> ${data.departure_date}</p>` : ''}
                        </div>
                    `;
                } else {
                    trackResultDiv.innerHTML = `<div class="alert alert-warning">❌ ${data.detail}</div>`;
                }
            } catch (error) {
                console.error("Search error:", error);
                trackResultDiv.innerHTML = `<div class="alert alert-danger">❌ Ошибка поиска</div>`;
            }
        });
    }

    // === CALENDAR INITIALIZATION ===
    initCalendar();
});

// === CALENDAR FUNCTIONS ===
function initCalendar() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;
    
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,dayGridWeek'
        },
        locale: 'ru',
        height: 'auto',
        events: async function(fetchInfo, successCallback, failureCallback) {
            try {
                const response = await authFetch('/api/admin/tracks-by-date');
                if (response.ok) {
                    const data = await response.json();
                    
                    const events = data.map(item => ({
                        title: item.title,
                        start: item.date,
                        backgroundColor: getColorByCount(item.count),
                        borderColor: getColorByCount(item.count),
                        extendedProps: {
                            count: item.count,
                            tracks: item.tracks,
                            date: item.date
                        }
                    }));
                    
                    successCallback(events);
                } else {
                    failureCallback(new Error('Failed to load calendar data'));
                }
            } catch (error) {
                console.error('Calendar loading error:', error);
                failureCallback(error);
            }
        },
        eventClick: function(info) {
            showDateTracksModal(info.event);
        }
    });
    
    calendar.render();
}

function getColorByCount(count) {
    if (count >= 50) return '#dc3545';
    if (count >= 20) return '#fd7e14';
    if (count >= 5) return '#ffc107';
    return '#28a745';
}

function showDateTracksModal(event) {
    const { count, tracks, date } = event.extendedProps;
    
    currentSelectedDate = date;
    currentDateTracks = tracks;
    
    document.getElementById('selected-date').textContent = date;
    document.getElementById('total-tracks').textContent = count;
    document.getElementById('modalDateTitle').textContent = `Посылки на ${date}`;
    
    const tbody = document.getElementById('tracks-list-body');
    tbody.innerHTML = '';
    
    tracks.forEach(track => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${track.track_number}</td>
            <td>${track.status || 'Не указан'}</td>
            <td>${track.personal_code || '<span class="text-muted">Не назначен</span>'}</td>
        `;
        tbody.appendChild(tr);
    });
    
    const modal = new bootstrap.Modal(document.getElementById('dateTracksModal'));
    modal.show();
}

// === BATCH UPDATE FORM ===
document.getElementById('batch-update-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const newStatus = document.getElementById('batch-new-status').value;
    
    if (!newStatus || !currentSelectedDate) {
        alert('⚠️ Выберите статус');
        return;
    }
    
    const confirmMsg = `Вы уверены, что хотите изменить статус всех ${currentDateTracks.length} посылок от ${currentSelectedDate} на "${newStatus}"?`;
    if (!confirm(confirmMsg)) return;
    
    try {
        const formData = new FormData();
        formData.append('departure_date', currentSelectedDate);
        formData.append('new_status', newStatus);
        
        const response = await authFetch('/api/admin/batch-update-status', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`✅ Успешно обновлено ${result.updated_count} посылок на статус "${newStatus}"!`);
            
            bootstrap.Modal.getInstance(document.getElementById('dateTracksModal')).hide();
            
            if (calendar) {
                calendar.refetchEvents();
            }
        } else {
            const error = await response.json();
            alert('❌ Ошибка: ' + error.detail);
        }
    } catch (error) {
        console.error('Batch update error:', error);
        alert('❌ Ошибка при обновлении');
    }
});
// === BARCODE SCANNER FUNCTIONALITY (NEW) ===
let scannedTracks = [];
let scanTimeout = null;

const scannerInput = document.getElementById('scanner-input');
const scannedContainer = document.getElementById('scanned-tracks-container');
const scannedTbody = document.getElementById('scanned-tracks-tbody');
const scannedCountSpan = document.getElementById('scanned-count');
const deliverCountSpan = document.getElementById('deliver-count');
const deleteCountSpan = document.getElementById('delete-count');

// Scanner input handler (detects barcode scanner speed)
scannerInput?.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        
        const trackNumber = this.value.trim().toUpperCase();
        if (trackNumber && !scannedTracks.some(t => t.track_number === trackNumber)) {
            addScannedTrack(trackNumber);
        }
        
        this.value = '';
    }
});

// Add scanned track to list
async function addScannedTrack(trackNumber) {
    try {
        // Validate track with backend
        const formData = new FormData();
        formData.append('track_numbers', trackNumber);
        
        const response = await authFetch('/api/admin/scanner/validate', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            const trackInfo = data.results[0];
            
            scannedTracks.push(trackInfo);
            renderScannedTracks();
            
            // Show success feedback
            scannerInput.style.borderColor = trackInfo.found ? 'green' : 'red';
            setTimeout(() => {
                scannerInput.style.borderColor = '';
            }, 500);
        }
    } catch (error) {
        console.error('Error validating track:', error);
        alert('❌ Ошибка при проверке трека');
    }
}

// Render scanned tracks table
function renderScannedTracks() {
    scannedTbody.innerHTML = '';
    scannedCountSpan.textContent = scannedTracks.length;
    deliverCountSpan.textContent = scannedTracks.filter(t => t.can_deliver).length;
    deleteCountSpan.textContent = scannedTracks.length;
    
    if (scannedTracks.length > 0) {
        scannedContainer.style.display = 'block';
    }
    
    scannedTracks.forEach((track, index) => {
        const tr = document.createElement('tr');
        tr.className = track.found ? '' : 'table-danger';
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${track.track_number}</strong></td>
            <td>
                ${track.found 
                    ? `<span class="badge bg-${track.can_deliver ? 'success' : 'warning'}">${track.status}</span>` 
                    : '<span class="badge bg-danger">Не найден</span>'
                }
            </td>
            <td>${track.personal_code || '<span class="text-muted">—</span>'}</td>
            <td>
                <button class="btn btn-sm btn-danger" onclick="removeScannedTrack(${index})">
                    ✕
                </button>
            </td>
        `;
        scannedTbody.appendChild(tr);
    });
}

// Remove track from scanned list
window.removeScannedTrack = function(index) {
    scannedTracks.splice(index, 1);
    renderScannedTracks();
    
    if (scannedTracks.length === 0) {
        scannedContainer.style.display = 'none';
    }
};

// Clear all scanned tracks
document.getElementById('clear-scanned-btn')?.addEventListener('click', () => {
    if (confirm('🔄 Очистить список отсканированных треков?')) {
        scannedTracks = [];
        renderScannedTracks();
        scannedContainer.style.display = 'none';
    }
});

// Deliver scanned parcels
document.getElementById('deliver-scanned-btn')?.addEventListener('click', async () => {
    const deliverable = scannedTracks.filter(t => t.found && t.can_deliver);
    
    if (deliverable.length === 0) {
        alert('⚠️ Нет посылок готовых к выдаче (должны быть на складе)');
        return;
    }
    
    const confirmMsg = `✅ Вы уверены, что хотите выдать клиентам ${deliverable.length} посылок?\n\nТреки:\n${deliverable.map(t => t.track_number).join('\n')}`;
    
    if (!confirm(confirmMsg)) return;
    
    try {
        const formData = new FormData();
        deliverable.forEach(t => formData.append('track_numbers', t.track_number));
        
        const response = await authFetch('/api/admin/scanner/deliver', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`✅ Успешно выдано ${result.delivered_count} посылок!`);
            
            // Clear delivered tracks from list
            scannedTracks = scannedTracks.filter(t => !deliverable.includes(t));
            renderScannedTracks();
            
            if (scannedTracks.length === 0) {
                scannedContainer.style.display = 'none';
            }
        } else {
            const error = await response.json();
            alert('❌ Ошибка: ' + error.detail);
        }
    } catch (error) {
        console.error('Deliver error:', error);
        alert('❌ Ошибка при выдаче посылок');
    }
});

// Delete scanned parcels
document.getElementById('delete-scanned-btn')?.addEventListener('click', async () => {
    const trackNumbers = scannedTracks.filter(t => t.found).map(t => t.track_number);
    
    if (trackNumbers.length === 0) {
        alert('⚠️ Нет треков для удаления');
        return;
    }
    
    const confirmMsg = `🗑️ ВЫ УВЕРЕНЫ, ЧТО ХОТИТЕ БЕЗВОЗВРАТНО УДАЛИТЬ ${trackNumbers.length} ПОСЫЛОК?\n\nЭто действие нельзя отменить!\n\nТреки:\n${trackNumbers.join('\n')}`;
    
    if (!confirm(confirmMsg)) return;
    
    // Second confirmation
    const secondConfirm = prompt(`Для подтверждения удаления введите слово "УДАЛИТЬ":`);
    if (secondConfirm !== 'УДАЛИТЬ') {
        alert('❌ Удаление отменено');
        return;
    }
    
    try {
        const formData = new FormData();
        trackNumbers.forEach(t => formData.append('track_numbers', t));
        
        const response = await authFetch('/api/admin/scanner/delete', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`✅ Успешно удалено ${result.deleted_count} посылок`);
            
            scannedTracks = [];
            renderScannedTracks();
            scannedContainer.style.display = 'none';
        } else {
            const error = await response.json();
            alert('❌ Ошибка: ' + error.detail);
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('❌ Ошибка при удалении посылок');
    }
});

// === ENHANCED TRACK SEARCH WITH EDIT/DELETE (UPDATED) ===
document.getElementById('track-search-btn')?.addEventListener('click', async () => {
    const trackNumber = document.getElementById('track-search').value.trim().toUpperCase();
    const trackResultDiv = document.getElementById('track-result');
    
    if (!trackNumber) {
        alert("⚠️ Введите трек-номер");
        return;
    }

    trackResultDiv.innerHTML = "<p>🔍 Поиск...</p>";

    try {
        const res = await fetch(`/api/tracks/search/${trackNumber}`);
        const data = await res.json();

        if (res.ok) {
            trackResultDiv.innerHTML = `
                <div class="alert alert-success">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <div>
                            <h5>Трек найден: ${data.track_number}</h5>
                            <p class="mb-1"><strong>Статус:</strong> ${data.current_status}</p>
                            <p class="mb-1"><strong>Привязан:</strong> ${data.is_assigned ? 'Да' : 'Нет'}</p>
                            ${data.personal_code ? `<p class="mb-1"><strong>Код клиента:</strong> ${data.personal_code}</p>` : ''}
                            ${data.departure_date ? `<p class="mb-0"><strong>Дата отправления:</strong> ${data.departure_date}</p>` : ''}
                        </div>
                        <div class="btn-group-vertical">
                            <button class="btn btn-sm btn-warning" onclick="editTrackStatus('${data.track_number}', '${data.current_status}')">
                                ✏️ Изменить статус
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="deleteTrack('${data.track_number}')">
                                🗑️ Удалить трек
                            </button>
                        </div>
                    </div>
                </div>
            `;
        } else {
            trackResultDiv.innerHTML = `<div class="alert alert-warning">❌ ${data.detail}</div>`;
        }
    } catch (error) {
        console.error("Search error:", error);
        trackResultDiv.innerHTML = `<div class="alert alert-danger">❌ Ошибка поиска</div>`;
    }
});

// Edit track status function
window.editTrackStatus = async function(trackNumber, currentStatus) {
    const statuses = [
        "Выехал из склада Китая",
        "В транзитном складе",
        "В Алматы (Склад)",
        "В Астане (Склад)",
        "Выдан клиенту"
    ];
    
    let options = statuses.map((s, i) => 
        `${i + 1}. ${s}${s === currentStatus ? ' (текущий)' : ''}`
    ).join('\n');
    
    const choice = prompt(`Выберите новый статус для ${trackNumber}:\n\n${options}\n\nВведите номер (1-5):`);
    
    if (!choice || choice < 1 || choice > 5) {
        alert('❌ Отменено');
        return;
    }
    
    const newStatus = statuses[parseInt(choice) - 1];
    
    if (newStatus === currentStatus) {
        alert('⚠️ Статус не изменился');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('new_status', newStatus);
        
        const response = await authFetch(`/api/admin/tracks/${trackNumber}/status`, {
            method: 'PUT',
            body: formData
        });
        
        if (response.ok) {
            alert(`✅ Статус трека ${trackNumber} изменён на "${newStatus}"`);
            document.getElementById('track-search-btn').click(); // Refresh
        } else {
            const error = await response.json();
            alert('❌ Ошибка: ' + error.detail);
        }
    } catch (error) {
        console.error('Update error:', error);
        alert('❌ Ошибка при обновлении');
    }
};

// Delete track function
window.deleteTrack = async function(trackNumber) {
    const confirmMsg = `🗑️ Вы уверены, что хотите БЕЗВОЗВРАТНО удалить трек ${trackNumber}?\n\nЭто действие нельзя отменить!`;
    
    if (!confirm(confirmMsg)) return;
    
    const secondConfirm = prompt(`Для подтверждения введите трек-номер полностью:\n${trackNumber}`);
    
    if (secondConfirm !== trackNumber) {
        alert('❌ Удаление отменено');
        return;
    }
    
    try {
        const response = await authFetch(`/api/admin/tracks/${trackNumber}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            alert(`✅ Трек ${trackNumber} успешно удалён`);
            document.getElementById('track-result').innerHTML = '';
            document.getElementById('track-search').value = '';
        } else {
            const error = await response.json();
            alert('❌ Ошибка: ' + error.detail);
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('❌ Ошибка при удалении');
    }
};
