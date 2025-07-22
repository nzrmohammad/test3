document.addEventListener('alpine:init', () => {
    Alpine.data('adminApp', () => ({
        // --- State ---
        isLoading: true,
        activeView: 'users',
        users: [],
        searchText: '',
        adminKey: '', // برای نگهداری کلید ادمین

        // --- Getters ---
        get activeViewTitle() {
            // ... (این بخش بدون تغییر باقی می‌ماند)
            switch (this.activeView) {
                case 'dashboard': return 'داشبورد';
                case 'users': return 'مدیریت کاربران';
                case 'plans': return 'مدیریت پلن‌ها';
                default: return '';
            }
        },
        get filteredUsers() {
            // ... (این بخش بدون تغییر باقی می‌ماند)
            if (!this.searchText) return this.users;
            const lowerSearchText = this.searchText.toLowerCase();
            return this.users.filter(user => 
                user.name.toLowerCase().includes(lowerSearchText) ||
                user.uuid.toLowerCase().includes(lowerSearchText)
            );
        },

        // --- Methods ---
        init() {
            console.log('Admin App Initialized');
            // FIX: کلید ادمین را از URL استخراج می‌کنیم
            const urlParams = new URLSearchParams(window.location.search);
            this.adminKey = urlParams.get('key');
            
            if (!this.adminKey) {
                alert('خطا: کلید دسترسی ادمین یافت نشد.');
                this.isLoading = false;
                return;
            }
            this.fetchUsers();
        },
        setView(view) {
            this.activeView = view;
        },
        async fetchUsers() {
            this.isLoading = true;
            try {
                // FIX: داده‌ها را از API واقعی دریافت می‌کنیم
                const response = await fetch(`/api/admin/users?key=${this.adminKey}`);
                if (!response.ok) {
                    throw new Error('خطا در ارتباط با سرور');
                }
                const data = await response.json();
                this.users = data;
            } catch (error) {
                console.error('Error fetching users:', error);
                alert('خطا در دریافت اطلاعات کاربران. لطفاً کنسول را بررسی کنید.');
            } finally {
                this.isLoading = false;
            }
        },
        editUser(user) {
            alert(`در حال ویرایش کاربر: ${user.name}`);
            // TODO: Open an edit modal
        },
        deleteUser(uuid) {
            if (confirm('آیا از حذف این کاربر اطمینان دارید؟')) {
                alert(`در حال حذف کاربر با شناسه: ${uuid}`);
                // TODO: Add API call to delete the user
            }
        },
        openCreateUserModal() {
            alert('باز کردن مودال ساخت کاربر جدید...');
            // TODO: Implement user creation modal
        },
        logout() {
            window.location.href = '/'; 
        },
        toggleTheme() {
            // ... (این بخش بدون تغییر باقی می‌ماند)
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        },
    }));
});