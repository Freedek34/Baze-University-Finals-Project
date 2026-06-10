/**
 * CryptoVault - Auth Page Logic
 */
document.addEventListener('DOMContentLoaded', () => {
    if (API.isAuthenticated()) { window.location.href = 'dashboard.html'; return; }

    const isLogin = window.location.pathname.includes('login');

    if (isLogin) {
        const form = document.getElementById('loginForm');
        if (form) form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            if (!username || !password) { Utils.showError('Please fill in all fields'); return; }
            const btn = form.querySelector('button[type="submit"]');
            Utils.setBtnLoading(btn);
            try {
                const result = await API.login(username, password);
                console.log('Login successful, result:', result);
                Utils.showSuccess('Welcome back!');
                setTimeout(() => window.location.href = 'dashboard.html', 800);
            } catch (err) { 
                console.error('Login error:', err);
                Utils.showError(err.message || 'Login failed'); 
            }
            finally { Utils.setBtnLoading(btn, false); }
        });
    } else {
        const form = document.getElementById('registerForm');
        if (form) form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value.trim();
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;
            const confirm = document.getElementById('confirmPassword').value;
            if (!username || !email || !password || !confirm) { Utils.showError('Please fill in all fields'); return; }
            if (password !== confirm) { Utils.showError('Passwords do not match'); return; }
            if (password.length < 6) { Utils.showError('Password must be at least 6 characters'); return; }
            const btn = form.querySelector('button[type="submit"]');
            Utils.setBtnLoading(btn);
            try {
                await API.register(username, email, password);
                Utils.showSuccess('Account created! Redirecting to login...');
                setTimeout(() => window.location.href = 'login.html', 1200);
            } catch (err) { Utils.showError(err.message || 'Registration failed'); }
            finally { Utils.setBtnLoading(btn, false); }
        });
    }

    // Password toggle
    document.querySelectorAll('.toggle-password').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = btn.closest('.input-group').querySelector('input');
            const isPass = input.type === 'password';
            input.type = isPass ? 'text' : 'password';
            btn.innerHTML = `<i class="fas fa-eye${isPass ? '-slash' : ''}"></i>`;
        });
    });
});
