// frontend/src/auth.js

// ==============================
// Token Management
// ==============================
function saveToken(token, user) {
    localStorage.setItem('access_token', token);
    localStorage.setItem('user_data', JSON.stringify(user));
}

function getToken() {
    return localStorage.getItem('access_token');
}

function getUserData() {
    const userData = localStorage.setItem('user_data');
    return userData ? JSON.parse(userData) : null;
}

function clearAuth() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_data');
}

function isAuthenticated() {
    return getToken() !== null;
}

// ==============================
// API Helper with Auth
// ==============================
async function apiCall(url, options = {}) {
    const token = getToken();
    
    if (token) {
        options.headers = {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        };
    }
    
    try {
        const response = await fetch(url, options);
        
        if (response.status === 401) {
            clearAuth();
            window.location.href = '/login';
            throw new Error('Unauthorized');
        }
        
        return response;
    } catch (error) {
        console.error('API call error:', error);
        throw error;
    }
}

// ==============================
// Login Form Handler
// ==============================
document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const alertContainer = document.getElementById('alert-container');
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            saveToken(data.access_token, data.user);
            
            // Redirect based on role
            if (data.user.role === 'admin') {
                window.location.href = '/admin';
            } else {
                window.location.href = '/';
            }
        } else {
            alertContainer.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    ${data.detail || 'Login failed'}
                </div>
            `;
        }
    } catch (error) {
        alertContainer.innerHTML = `
            <div class="alert alert-danger" role="alert">
                Connection error. Please try again.
            </div>
        `;
    }
});

// ==============================
// Registration Link
// ==============================
document.getElementById('register-link')?.addEventListener('click', (e) => {
    e.preventDefault();
    // You can create a separate register.html page
    alert('Registration functionality coming soon!');
});

// ==============================
// Logout Function
// ==============================
function logout() {
    clearAuth();
    window.location.href = '/login';
}

// ==============================
// Check Auth on Protected Pages
// ==============================
function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = '/login';
    }
}

// Export functions for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        saveToken,
        getToken,
        getUserData,
        clearAuth,
        isAuthenticated,
        apiCall,
        logout,
        requireAuth
    };
}
