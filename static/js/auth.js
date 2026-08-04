/**
 * 认证页面逻辑 v2.0
 * 适配新分栏布局 + Tab 切换
 */
class AuthManager {
    constructor() {
        this.initializeEventListeners();
        this.setupPasswordToggles();
    }

    initializeEventListeners() {
        // Tab 切换（新设计：data-tab 属性）
        document.querySelectorAll('.login-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.dataset.tab;
                document.querySelectorAll('.login-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                document.querySelectorAll('.login-form').forEach(f => f.classList.remove('active'));
                if (target === 'login') {
                    document.getElementById('loginForm')?.classList.add('active');
                } else if (target === 'register') {
                    document.getElementById('registerForm')?.classList.add('active');
                }
            });
        });

        // 兼容旧版翻转卡片（保留）
        document.getElementById('flipToRegister')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.switchToRegister();
        });
        document.getElementById('flipToLogin')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.switchToLogin();
        });

        document.getElementById('loginForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });
        document.getElementById('registerForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleRegister();
        });

        // 头像预览
        const savedAvatar = localStorage.getItem('userAvatar');
        ['loginUserAvatar', 'register-avatar-img'].forEach(id => {
            const el = document.getElementById(id);
            if (el && savedAvatar) el.src = savedAvatar;
        });
        document.getElementById('loginAvatarInput')?.addEventListener('change', this.handleAvatarUpload);
        document.getElementById('register-avatar-input')?.addEventListener('change', this.handleAvatarUpload);
    }

    handleAvatarUpload(e) {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function(evt) {
            if (evt.target.result) {
                localStorage.setItem('userAvatar', evt.target.result);
                ['loginUserAvatar', 'register-avatar-img', 'topbarAvatar'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.src = evt.target.result;
                });
            }
        };
        reader.readAsDataURL(file);
    }

    setupPasswordToggles() {
        const toggles = [
            { toggleId: 'loginPasswordToggle', inputId: 'login-password' },
            { toggleId: 'registerPasswordToggle', inputId: 'register-password' },
            { toggleId: 'confirmPasswordToggle', inputId: 'register-confirm' }
        ];
        toggles.forEach(({ toggleId, inputId }) => this.setupPasswordToggle(toggleId, inputId));
    }

    setupPasswordToggle(toggleId, inputId) {
        const toggle = document.getElementById(toggleId);
        const input = document.getElementById(inputId);
        if (!toggle || !input) return;
        toggle.addEventListener('click', () => {
            const isPass = input.getAttribute('type') === 'password';
            input.setAttribute('type', isPass ? 'text' : 'password');
            const icon = toggle.querySelector('i');
            if (icon) icon.className = isPass ? 'ri-eye-line' : 'ri-eye-off-line';
        });
    }

    switchToLogin() {
        document.getElementById('authCard')?.classList.remove('flipped');
        document.getElementById('registerForm')?.classList.remove('active');
        document.getElementById('loginForm')?.classList.add('active');
        document.querySelectorAll('.login-tab').forEach(t => t.classList.remove('active'));
        const loginTab = document.querySelector('.login-tab[data-tab="login"]');
        if (loginTab) loginTab.classList.add('active');
    }

    switchToRegister() {
        document.getElementById('authCard')?.classList.add('flipped');
        document.getElementById('loginForm')?.classList.remove('active');
        document.getElementById('registerForm')?.classList.add('active');
        document.querySelectorAll('.login-tab').forEach(t => t.classList.remove('active'));
        const regTab = document.querySelector('.login-tab[data-tab="register"]');
        if (regTab) regTab.classList.add('active');
    }

    async handleLogin() {
        const email = document.getElementById('login-username')?.value.trim();
        const password = document.getElementById('login-password')?.value;
        if (!this.validateLoginInput(email, password)) return;
        try {
            this.setButtonLoading('#loginForm', true);
            const data = await apiClient.login(email, password);
            if (data?.success) {
                const userId = data.user_id;
                storageManager.setCurrentUser(email, data.name || 'User', userId);
                // 后台预加载画像
                apiClient.getUserProfile(userId).then(profileResp => {
                    if (profileResp?.success) {
                        localStorage.setItem('cachedUserProfile', JSON.stringify({ userId, timestamp: Date.now(), data: profileResp }));
                    }
                }).catch(() => {});
                if (typeof storageManager.createNewChat === 'function') {
                    const newChat = storageManager.createNewChat();
                    storageManager.setCurrentChatId(newChat.id);
                }
                Utils.showToast('登录成功！正在跳转...', 2000);
                setTimeout(() => { window.location.href = 'dashboard.html'; }, 1000);
            } else {
                Utils.showToast(data?.message || '登录失败');
            }
        } catch (error) {
            Utils.showToast(error.message || '登录失败，请稍后重试');
        } finally {
            this.setButtonLoading('#loginForm', false);
        }
    }

    async handleRegister() {
        const name = document.getElementById('register-name')?.value.trim();
        const email = document.getElementById('register-username')?.value.trim();
        const password = document.getElementById('register-password')?.value;
        const confirm = document.getElementById('register-confirm')?.value;
        if (!this.validateRegisterInput(name, email, password, confirm)) return;
        try {
            this.setButtonLoading('#registerForm', true);
            const data = await apiClient.register(name, email, password);
            if (data?.success) {
                Utils.showToast('注册成功！请登录', 1500);
                setTimeout(() => { this.switchToLogin(); }, 1200);
            } else {
                Utils.showToast(data?.message || '注册失败');
            }
        } catch (error) {
            Utils.showToast(error.message || '注册失败，请稍后重试');
        } finally {
            this.setButtonLoading('#registerForm', false);
        }
    }

    validateLoginInput(email, password) {
        if (!email || !password) { Utils.showToast('请填写完整的登录信息'); return false; }
        if (!Utils.validateEmail(email)) { Utils.showEmailError('login-email-err', true, '邮箱格式不正确'); return false; }
        Utils.showEmailError('login-email-err', false);
        return true;
    }

    validateRegisterInput(name, email, password, confirm) {
        if (!name || !email || !password || !confirm) { Utils.showToast('请填写完整的注册信息'); return false; }
        if (name.length > 20) { Utils.showToast('姓名长度不能超过20个字符'); return false; }
        if (!Utils.validateEmail(email)) { Utils.showEmailError('register-email-err', true, '邮箱格式不正确'); return false; }
        if (password.length < 6) { Utils.showToast('密码长度至少6位'); return false; }
        if (password !== confirm) { Utils.showToast('两次输入的密码不一致'); return false; }
        Utils.showEmailError('register-email-err', false);
        return true;
    }

    setButtonLoading(formId, loading) {
        const form = document.querySelector(formId);
        if (!form) return;
        const btn = form.querySelector('button[type="submit"]');
        if (!btn) return;
        btn.disabled = loading;
        const span = btn.querySelector('span');
        if (span) span.textContent = loading ? (formId.includes('register') ? '注册中...' : '登录中...') : (formId.includes('register') ? '创建账户' : '登 录');
    }
}

document.head.appendChild(Object.assign(document.createElement('style'), {
    textContent: '@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}'
}));

document.addEventListener('DOMContentLoaded', () => { new AuthManager(); });
if (typeof module !== 'undefined' && module.exports) { module.exports = AuthManager; }
