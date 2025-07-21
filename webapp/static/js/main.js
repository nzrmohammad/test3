// file: webapp/static/js/main.js
function app() {
    return {
        // --- State ---
        isLoading: false,
        error: '',
        uuidInput: '',
        user: {}, // Holds all user data from the API
        isLight: localStorage.getItem('theme') === 'light',
        openSection: null, // Manages collapsible sections ('chart', 'links', 'plans')
        qrVisible: false,
        qrTitle: '',
        currentLink: '',
        usageChartInstance: null,
        supportLink: typeof supportLink !== 'undefined' ? supportLink : '#', // Use link from Flask
        
        // --- State for Service Plans ---
        plansLoading: false,
        activePlanType: '',
        servicePlans: [],

        // --- Initialization ---
        init() {
            if (this.isLight) {
                document.documentElement.setAttribute('data-theme', 'light');
            }
        },

        // --- Main Data Fetching Method ---
        async fetchData() {
            if (!this.uuidInput.trim()) {
                this.error = 'لطفاً شناسه UUID را وارد کنید.';
                return;
            }
            this.isLoading = true;
            this.error = '';
            this.user = {};
            if (this.usageChartInstance) {
                this.usageChartInstance.destroy();
            }

            try {
                // Fetch user data and usage history in parallel for better performance
                const [userResponse, historyResponse] = await Promise.all([
                    fetch(`/api/user/${this.uuidInput.trim()}`),
                    fetch(`/api/user/${this.uuidInput.trim()}/usage_history`)
                ]);

                const userData = await userResponse.json();
                if (!userResponse.ok) {
                    throw new Error(userData.error || 'خطا در دریافت اطلاعات کاربر.');
                }
                
                const historyData = await historyResponse.json();
                if (!historyResponse.ok) {
                    console.warn("Could not fetch usage history. Chart will not be shown.");
                }

                this.user = this.processUserData(userData);
                
                // Use $nextTick to ensure the canvas element is visible in the DOM
                this.$nextTick(() => {
                    if (historyData && !historyData.error) {
                        this.renderUsageChart(historyData);
                    }
                });

            } catch (err) {
                this.error = err.message;
            } finally {
                this.isLoading = false;
            }
        },
        
        // --- Helper to process raw user data ---
        processUserData(data) {
             return {
                ...data,
                // Add the smart subscription link for easy access
                subscriptionUrl: `${window.location.origin}/sub/${data.uuid}`
            };
        },

        // --- Method for Fetching Service Plans ---
        async fetchServicePlans(planType) {
            if (this.activePlanType === planType && this.servicePlans.length > 0) return; // Avoid re-fetching
            
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
                alert(err.message); // Inform user about the error
            } finally {
                this.plansLoading = false;
            }
        },

        // --- Dynamic Text Formatters ---
        getExpireText() {
            if (this.user.expire === null || this.user.expire === undefined) return 'نامحدود';
            return this.user.expire >= 0 ? `${this.user.expire} روز` : 'منقضی شده';
        },
        getBirthdayText() {
            const days = this.user.days_until_birthday;
            if (days === null || days === undefined) return 'ثبت نشده';
            if (days === 0) return '🎉 امروز تولد شماست!';
            return `${days} روز تا تولد بعدی`;
        },
        getPaymentText() {
            const count = this.user.payment_history?.count;
            if (!count) return 'پرداختی ثبت نشده';
            return `${count} پرداخت موفق`;
        },
        
        // --- UI Interaction Methods ---
        toggleTheme() {
            this.isLight = !this.isLight;
            const newTheme = this.isLight ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            // Re-render chart if visible, to update colors
            if(this.usageChartInstance) {
                this.usageChartInstance.destroy();
                this.$nextTick(() => this.fetchData());
            }
        },
        toggleSection(section) {
            if (this.openSection === section) {
                this.openSection = null;
            } else {
                this.openSection = section;
                // If opening plans for the first time, fetch combined plans by default
                if(section === 'plans' && this.servicePlans.length === 0) {
                    this.fetchServicePlans('combined');
                }
            }
        },
        copyToClipboard(text) {
            navigator.clipboard.writeText(text)
                .then(() => alert('کپی شد!'))
                .catch(() => alert('خطا در کپی کردن.'));
        },
        openQr(link, title) {
            this.currentLink = link;
            this.qrTitle = title;
            this.qrVisible = true;
            this.$nextTick(() => {
                this.generateQr(link);
            });
        },
        
        // --- Chart & QR Generation ---
        generateQr(link) {
            const canvas = document.getElementById('qr-canvas');
            if (!canvas) return;
            const fgColor = getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim();
            const bgColor = getComputedStyle(document.documentElement).getPropertyValue('--bg-card').trim();
            new QRious({ element: canvas, value: link, size: 220, background: bgColor, foreground: fgColor, level: 'H' });
        },
        renderUsageChart(data) {
            const ctx = document.getElementById('usageChart');
            if (!ctx) return;
            const textColor = this.isLight ? '#1f2937' : '#ffffff';
            this.usageChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels.reverse(),
                    datasets: [{
                        label: 'سرور آلمان 🇩🇪', data: data.hiddify.reverse(), borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.2)', fill: true, tension: 0.4
                    }, {
                        label: 'سرور فرانسه 🇫🇷', data: data.marzban.reverse(), borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.2)', fill: true, tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: textColor } }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw.toFixed(2)} GB` } } },
                    scales: { y: { beginAtZero: true, ticks: { color: textColor }, grid: { color: 'rgba(255, 255, 255, 0.1)' }, title: { display: true, text: 'مصرف (GB)', color: textColor } }, x: { ticks: { color: textColor }, grid: { color: 'rgba(255, 255, 255, 0.1)' } } }
                }
            });
        }
    };
}