// frontend/src/auth-disabled.js
// Temporary file to disable authentication for testing

console.log('⚠️ AUTH DISABLED - FOR TESTING ONLY');

// Mock authentication
localStorage.setItem('access_token', 'test-token-for-development');
localStorage.setItem('user_data', JSON.stringify({
    id: 1,
    email: 'client@test.com',
    name: 'Test User',
    personal_code: '106',
    role: 'client',
    branch: 'Test'
}));

console.log('✅ Mock auth data set:', JSON.parse(localStorage.getItem('user_data')));
