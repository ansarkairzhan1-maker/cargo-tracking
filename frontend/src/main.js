// frontend/src/main.js

const AUTH_TOKEN = localStorage.getItem('access_token');
const USER_DATA = JSON.parse(localStorage.getItem('user_data') || '{}');

console.log('🔐 DEBUG: Token =', AUTH_TOKEN);
console.log('👤 DEBUG: User =', USER_DATA);

// Check authentication on page load
if (!AUTH_TOKEN) {
    console.log('❌ No token, redirecting to login...');
    window.location.href = '/login';
} else {
    console.log('✅ Token found, continuing...');
}

const USER_CODE = USER_DATA.personal_code || "106";
console.log('🔢 User Code:', USER_CODE);
// === DOM ELEMENTS ===
const PARCELS_LIST = document.getElementById("parcels-list");
const ADD_BTN = document.getElementById("add-btn");
const REFRESH_BTN = document.getElementById("refresh-btn");
const TRACK_MODAL = document.getElementById("track-modal");
const MODAL_CLOSE_BTN = document.querySelector(".close-btn");
const SUBMIT_TRACK_BTN = document.getElementById("submit-track-btn");
const TRACK_NUMBER_INPUT = document.getElementById("track-number-input");
const MODAL_MESSAGE = document.getElementById("modal-message");
const SEARCH_INPUT = document.getElementById("search-input");
const SEARCH_RESULT_CARD = document.getElementById("search-result-card");
const SEARCH_RESULT_CONTAINER = document.getElementById("search-result-container");
const USER_PARCELS_CARD = document.getElementById("user-parcels-card");

// === AUTHENTICATED FETCH HELPER ===
async function authFetch(url, options = {}) {
    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${AUTH_TOKEN}`,
        'Content-Type': 'application/json'
    };
    
    const response = await fetch(url, options);
    
    if (response.status === 401) {
        localStorage.clear();
        alert('Session expired. Please login again.');
        window.location.href = '/login';
    }
    
    return response;
}

// === RENDER FUNCTIONS ===

/**
 * Generates HTML for one timeline status item.
 */
function renderStatusItem(event) {
    const isCompleted = event.completed;
    const iconClass = isCompleted ? "completed" : "pending";
    const dateText = event.date !== "—" && isCompleted ? event.date : "нет данных";
    const dateClass = dateText === "нет данных" ? "no-data" : "";
    const iconContent = isCompleted ? "✔" : "";

    return `
        <div class="track-status-item">
            <div class="status-icon ${iconClass}">${iconContent}</div>
            <div class="status-content">
                <div class="status-title">${event.status}</div>
                <div class="status-date ${dateClass}">${dateText}</div>
            </div>
        </div>
    `;
}

/**
 * Generates HTML card for a track.
 */
function renderTrackCard(track, isSearchResult = false) {
    const headerClass = isSearchResult ? "track-header search-result" : "track-header";
    
    const assignmentNote = (isSearchResult && track.is_assigned && track.personal_code !== USER_CODE)
        ? `<p class="alert alert-warning p-2 mt-2 mb-0" style="font-size: 14px;">
            ⚠️ Трек найден в системе, но привязан к другому клиенту (Код: ${track.personal_code}).
           </p>`
        : '';
    
    const deleteButton = !isSearchResult ? 
        `<button class="delete-btn" data-track="${track.track_number}" title="Удалить трек">🗑️</button>`
        : '';

    const timelineHTML = track.status_timeline
        .map(item => renderStatusItem(item))
        .join('');

    return `
        <div class="track-card" id="track-${track.track_number}">
            <div class="${headerClass}">
                <span>${track.track_number}</span>
                ${deleteButton}
            </div>
            <div class="track-body">
                ${assignmentNote}
                <div class="track-notes">
                    Текущий статус: <strong>${track.current_status || 'Ожидание обновления'}</strong>
                </div>
                ${timelineHTML}
            </div>
        </div>
    `;
}

// === DATA LOADING FUNCTIONS ===

/**
 * Loads and displays user's tracks.
 */
async function loadUserTracks() {
    PARCELS_LIST.innerHTML = `<p class="no-tracks-text">Загружаю ваши треки...</p>`;
    USER_PARCELS_CARD.style.display = 'block';
    SEARCH_RESULT_CARD.style.display = 'none';

    try {
        const res = await authFetch(`/api/users/${USER_CODE}/tracks`);
        if (!res.ok) throw new Error("Ошибка загрузки треков");
        
        const tracks = await res.json();

        if (tracks.length === 0) {
            PARCELS_LIST.innerHTML = `<p class="no-tracks-text">У вас нет привязанных треков. Нажмите "Добавить", чтобы начать отслеживание.</p>`;
        } else {
            PARCELS_LIST.innerHTML = tracks.map(t => renderTrackCard(t, false)).join('');
        }
    } catch (error) {
        console.error("Ошибка при загрузке треков пользователя:", error);
        PARCELS_LIST.innerHTML = `<p class="no-tracks-text text-danger">Не удалось загрузить данные. ❌</p>`;
    }
}

// === MODAL FUNCTIONS ===

/**
 * Opens modal for adding track.
 */
function openTrackModal() {
    TRACK_NUMBER_INPUT.value = '';
    MODAL_MESSAGE.textContent = '';
    TRACK_MODAL.style.display = 'flex';
}

/**
 * Closes track modal.
 */
function closeTrackModal() {
    TRACK_MODAL.style.display = 'none';
}

/**
 * Handles track submission.
 */
async function handleSubmitTrack() {
    const trackNumber = TRACK_NUMBER_INPUT.value.trim().toUpperCase();
    MODAL_MESSAGE.textContent = '';

    if (!trackNumber) {
        MODAL_MESSAGE.textContent = "Введите, пожалуйста, трек-номер.";
        return;
    }

    SUBMIT_TRACK_BTN.disabled = true;

    try {
        const res = await authFetch("/api/tracks/assign", {
            method: "POST",
            body: JSON.stringify({
                track_number: trackNumber,
                personal_code: USER_CODE
            })
        });

        const data = await res.json();

        if (res.ok) {
            MODAL_MESSAGE.textContent = "✅ Трек успешно добавлен к вашему списку!";
            MODAL_MESSAGE.style.color = "green";
            setTimeout(() => {
                closeTrackModal();
                loadUserTracks(); 
            }, 1500);
        } else {
            MODAL_MESSAGE.textContent = `❌ Ошибка: ${data.detail || "Не удалось добавить трек."}`;
            MODAL_MESSAGE.style.color = "red";
        }

    } catch (error) {
        console.error("Network error during track assignment:", error);
        MODAL_MESSAGE.textContent = "❌ Ошибка сети. Проверьте подключение.";
        MODAL_MESSAGE.style.color = "red";
    } finally {
        SUBMIT_TRACK_BTN.disabled = false;
    }
}

// === SEARCH FUNCTIONS ===

/**
 * Searches for a track by number.
 */
async function handleTrackSearch(trackNumber) {
    if (!trackNumber) {
        USER_PARCELS_CARD.style.display = 'block';
        SEARCH_RESULT_CARD.style.display = 'none';
        return;
    }

    SEARCH_RESULT_CONTAINER.innerHTML = `<p class="no-tracks-text">🔍 Ищу трек ${trackNumber}...</p>`;
    USER_PARCELS_CARD.style.display = 'none';
    SEARCH_RESULT_CARD.style.display = 'block';

    try {
        // Public search doesn't require auth
        const res = await fetch(`/api/tracks/search/${trackNumber.toUpperCase()}`);
        const data = await res.json();

        if (res.ok) {
            SEARCH_RESULT_CONTAINER.innerHTML = renderTrackCard(data, true);
        } else if (res.status === 404) {
            SEARCH_RESULT_CONTAINER.innerHTML = `
                <p class="alert alert-info text-center">
                    Трек-номер <strong>${trackNumber}</strong> пока не найден в нашей системе. 
                    Нажмите "Добавить" для привязки и ожидайте статуса.
                </p>`;
        } else {
            SEARCH_RESULT_CONTAINER.innerHTML = `<p class="text-danger">Ошибка сервера: ${data.detail || "Неизвестная ошибка."}</p>`;
        }
    } catch (error) {
        console.error("Ошибка сети при поиске:", error);
        SEARCH_RESULT_CONTAINER.innerHTML = `<p class="text-danger">❌ Ошибка сети при поиске.</p>`;
    }
}

// === INITIALIZATION ===

document.addEventListener("DOMContentLoaded", () => {
    console.log("✅ DELTA CARGO User Panel загружен");
    
    // Update user code display
    const userCodeElement = document.getElementById('user-code');
    if (userCodeElement && USER_DATA.personal_code) {
        userCodeElement.textContent = USER_DATA.personal_code;
    }
    
    // Add logout functionality
    document.querySelector('.logout')?.addEventListener('click', (e) => {
        e.preventDefault();
        localStorage.clear();
        window.location.href = '/login';
    });
    
    // Load user tracks on start
    loadUserTracks();

    // Modal handlers
    ADD_BTN.addEventListener('click', openTrackModal);
    MODAL_CLOSE_BTN.addEventListener('click', closeTrackModal);
    SUBMIT_TRACK_BTN.addEventListener('click', handleSubmitTrack);
    window.addEventListener('click', (event) => {
        if (event.target === TRACK_MODAL) {
            closeTrackModal();
        }
    });

    // Search handler
    SEARCH_INPUT.addEventListener('keyup', (e) => {
        const value = e.target.value.trim();
        if (e.key === 'Enter' && value) {
            handleTrackSearch(value);
        } else if (!value) {
            handleTrackSearch('');
        }
    });

    // Delete track handler (event delegation)
    PARCELS_LIST.addEventListener('click', async (e) => {
        if (e.target.classList.contains('delete-btn')) {
            const trackNumber = e.target.dataset.track;
            if (!confirm(`Вы уверены, что хотите удалить трек ${trackNumber} из списка?`)) return;

            try {
                const res = await authFetch(`/api/tracks/archive/${trackNumber}`, { 
                    method: 'POST' 
                });
                
                if (!res.ok) throw new Error("Ошибка удаления трека");
                
                e.target.closest('.track-card').remove();
                loadUserTracks(); 
            } catch (error) {
                alert("Не удалось удалить трек. Попробуйте обновить страницу.");
                console.error("Ошибка при удалении трека:", error);
            }
        }
    });
    
    // Refresh button
    REFRESH_BTN.addEventListener("click", () => { 
        loadUserTracks();
    });
    
    // Navigation tabs
    document.querySelectorAll(".nav-btn").forEach(btn => {
        btn.addEventListener("click", () => {
             document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove('active'));
             btn.classList.add('active');
             
             if (btn.dataset.tab === 'parcels') {
                 loadUserTracks();
             } else {
                 USER_PARCELS_CARD.style.display = 'none';
                 SEARCH_RESULT_CARD.style.display = 'block';
                 SEARCH_RESULT_CONTAINER.innerHTML = `<p class="alert alert-light text-center">
                    Контент для вкладки "${btn.textContent}" находится в разработке.
                 </p>`;
             }
        });
    });
});
// === CHANGE PASSWORD FUNCTIONALITY ===
document.getElementById('change-password-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const alertContainer = document.getElementById('password-alert-container');
    const submitBtn = document.getElementById('submit-password-btn');
    
    alertContainer.innerHTML = '';
    
    if (newPassword !== confirmPassword) {
        alertContainer.innerHTML = `
            <div class="alert alert-danger" role="alert">
                ❌ Новые пароли не совпадают
            </div>
        `;
        return;
    }
    
    if (newPassword.length < 6) {
        alertContainer.innerHTML = `
            <div class="alert alert-danger" role="alert">
                ❌ Пароль должен быть минимум 6 символов
            </div>
        `;
        return;
    }
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Изменение...';
    
    try {
        const formData = new FormData();
        formData.append('old_password', currentPassword);
        formData.append('new_password', newPassword);
        
        const response = await authFetch('/api/auth/change-password', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alertContainer.innerHTML = `
                <div class="alert alert-success" role="alert">
                    ✅ Пароль успешно изменён!
                </div>
            `;
            
            document.getElementById('change-password-form').reset();
            
            setTimeout(() => {
                const modal = bootstrap.Modal.getInstance(document.getElementById('changePasswordModal'));
                modal.hide();
                alertContainer.innerHTML = '';
            }, 2000);
        } else {
            alertContainer.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    ❌ ${data.detail || 'Ошибка при изменении пароля'}
                </div>
            `;
        }
    } catch (error) {
        console.error('Change password error:', error);
        alertContainer.innerHTML = `
            <div class="alert alert-danger" role="alert">
                ❌ Ошибка сети. Попробуйте позже.
            </div>
        `;
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Изменить пароль';
    }
});

document.getElementById('changePasswordModal')?.addEventListener('hidden.bs.modal', function () {
    document.getElementById('change-password-form').reset();
    document.getElementById('password-alert-container').innerHTML = '';
});

// Update user name in header
const userNameElement = document.getElementById('user-name');
if (userNameElement && USER_DATA.name) {
    userNameElement.textContent = USER_DATA.name;
}
