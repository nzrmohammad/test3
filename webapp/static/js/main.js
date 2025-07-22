// file: webapp/static/js/main.js

function app() {
    return {
        // --- بخش وضعیت‌ها (State) ---
        isLoading: false,
        error: '',
        uuidInput: '',
        user: {},
        isLight: localStorage.getItem('theme') === 'light',
        activeView: 'dashboard', // همیشه با داشبورد شروع می‌شود
        qrVisible: false,
        qrTitle: '',
        currentLink: '',
        usageChartInstance: null,
        usageHistory: null,
        supportLink: typeof supportLink !== 'undefined' ? supportLink : '#',
        
        // --- وضعیت‌های مربوط به پلن‌های سرویس ---
        plansLoading: false,
        activePlanType: '',
        servicePlans: [],

        // --- مقداردهی اولیه ---
        init() {
            if (this.isLight) {
                document.documentElement.setAttribute('data-theme', 'light');
            }
        },

        // --- متد اصلی دریافت اطلاعات ---
        async fetchData() {
            if (!this.uuidInput.trim()) {
                this.error = 'لطفاً شناسه UUID را وارد کنید.';
                return;
            }
            this.isLoading = true;
            this.error = '';
            
            if (this.usageChartInstance) {
                this.usageChartInstance.destroy();
                this.usageChartInstance = null;
            }

            try {
                const [userResponse, historyResponse] = await Promise.all([
                    fetch(`/api/user/${this.uuidInput.trim()}`),
                    fetch(`/api/user/${this.uuidInput.trim()}/usage_history`)
                ]);

                const userData = await userResponse.json();
                if (!userResponse.ok) throw new Error(userData.error || 'خطا در دریافت اطلاعات.');
                
                const historyData = await historyResponse.json();
                if (!historyResponse.ok) console.warn("Could not fetch usage history.");

                this.user = this.processUserData(userData);
                this.usageHistory = historyData;
                
                // مهم: بعد از لاگین موفق، کاربر را به صفحه داشبورد می‌برد
                this.activeView = 'dashboard'; 

                this.$nextTick(() => {
                    if (this.activeView === 'chart') {
                       this.renderUsageChart();
                    }
                });

            } catch (err) {
                this.error = err.message;
                this.user = {}; // در صورت خطا، کاربر را خالی می‌کند تا به صفحه ورود برگردد
            } finally {
                this.isLoading = false;
            }
        },
        
        processUserData(data) {
             return { ...data, subscriptionUrl: `${window.location.origin}/sub/${data.uuid}` };
        },

        async fetchServicePlans(planType) {
            if (this.activePlanType === planType && this.servicePlans.length > 0) return;
            this.plansLoading = true;
            this.activePlanType = planType;
            this.servicePlans = [];
            try {
                const response = await fetch(`/api/service_plans/${planType}`);
                const data = await response.json();
                if (!response.ok) throw new Error(data.error);
                this.servicePlans = data;
            } catch (err) {
                console.error("Failed to fetch service plans:", err);
            } finally {
                this.plansLoading = false;
            }
        },

        // --- توابع قالب‌بندی متن ---
        getBirthdayText() {
            const days = this.user.days_until_birthday;
            if (days === null || days === undefined) return 'ثبت نشده';
            if (days === 0) return '🎉 امروز تولد شماست!';
            return `${days} روز تا تولد بعدی`;
        },
        getFormattedExpiryDate() {
            if (!this.user.expiry_date) return 'نامشخص';
            return new Intl.DateTimeFormat('fa-IR', { year: 'numeric', month: 'long', day: 'numeric' }).format(new Date(this.user.expiry_date));
        },
        getRemainingTime() {
            if (this.user.expire === null || this.user.expire === undefined) return 'سرویس دائمی';
            if (this.user.expire < 0) return 'پایان یافته';
            let totalSeconds = this.user.expire * 24 * 60 * 60;
            const days = Math.floor(totalSeconds / (3600 * 24));
            totalSeconds %= 3600 * 24;
            const hours = Math.floor(totalSeconds / 3600);
            return `( ${days} روز و ${hours} ساعت باقی‌مانده )`;
        },
        getPaymentText() {
            const count = this.user.payment_history?.count;
            if (!count) return 'پرداختی ثبت نشده';
            return `${count} پرداخت موفق`;
        },
        
        // --- توابع تعامل با رابط کاربری ---
        toggleTheme() {
            this.isLight = !this.isLight;
            const newTheme = this.isLight ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            if(this.usageChartInstance) {
                this.usageChartInstance.destroy();
                this.usageChartInstance = null;
                this.$nextTick(() => this.renderUsageChart());
            }
        },
        setView(view) {
            this.activeView = view;
            if (view === 'plans' && this.servicePlans.length === 0) {
                this.fetchServicePlans('combined');
            }
            if (view === 'chart' && this.usageHistory && !this.usageChartInstance) {
                 this.$nextTick(() => this.renderUsageChart());
            }
        },
        logout() {
            this.user = {};
            this.uuidInput = '';
            this.error = '';
            this.activeView = 'dashboard';
        },
        copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => alert('کپی شد!'));
        },
        openQr(link, title) {
            this.currentLink = link;
            this.qrTitle = title;
            this.qrVisible = true;
            this.$nextTick(() => this.generateQr(link));
        },
        
        // --- توابع ساخت نمودار و کد QR ---
        generateQr(link) {
            const canvas = document.getElementById('qr-canvas');
            if (!canvas) return;
            new QRious({ element: canvas, value: link, size: 220, background: 'white', foreground: 'black', level: 'H' });
        },
        renderUsageChart() {
            if (!this.usageHistory || this.usageHistory.error || this.usageChartInstance) return;
            Chart.defaults.font.family = "'Vazirmatn', sans-serif";
            const data = this.usageHistory;

            const ctx = document.getElementById('usageChart');
            if (!ctx) return;
            const textColor = this.isLight ? '#111827' : '#f9fafb';
            this.usageChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels.reverse(),
                    datasets: [
                        { label: 'سرور آلمان 🇩🇪', data: data.hiddify.reverse(), borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.2)', fill: true, tension: 0.4 },
                        { label: 'سرور فرانسه 🇫🇷', data: data.marzban.reverse(), borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.2)', fill: true, tension: 0.4 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: textColor } }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw.toFixed(2)} GB` } } },
                    scales: { y: { beginAtZero: true, ticks: { color: textColor }, grid: { color: 'rgba(255, 255, 255, 0.1)' }, title: { display: true, text: 'مصرف (GB)', color: textColor } }, x: { ticks: { color: textColor }, grid: { color: 'rgba(255, 255, 255, 0.1)' } } }
                }
            });
        },

        // --- عنوان داینامیک بالای صفحه ---
        get activeViewTitle() {
            switch(this.activeView) {
                case 'dashboard': return 'داشبورد';
                case 'chart': return 'نمودار مصرف';
                case 'links': return 'لینک اشتراک';
                case 'plans': return 'خرید سرویس';
                default: return 'پنل کاربری';
            }
        }
    };
}