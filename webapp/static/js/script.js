document.addEventListener('DOMContentLoaded', function() {
    let trafficChart = null; // متغیر برای نگهداری نمونه نمودار

    // --- منطق عمومی که در همه صفحات اجرا می‌شود ---
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    if (sidebar && sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        });
        if (localStorage.getItem('sidebarCollapsed') === 'true') {
            sidebar.classList.add('collapsed');
        }
    }

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        const themeIcon = themeToggle.querySelector('i');
        themeToggle.addEventListener('click', () => {
            const isDark = document.body.classList.toggle('dark-theme');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            if (themeIcon) themeIcon.className = isDark ? 'ri-sun-line' : 'ri-moon-line';

            // به‌روزرسانی رنگ نمودار هنگام تغییر تم
            if (trafficChart) {
                trafficChart.updateOptions({
                    plotOptions: {
                        radialBar: { dataLabels: { value: { color: isDark ? '#FFFFFF' : '#111827' } } }
                    }
                });
            }
        });

        if (localStorage.getItem('theme') === 'dark') {
            document.body.classList.add('dark-theme');
            if (themeIcon) themeIcon.className = 'ri-sun-line';
        }
    }

    function initializeUserDashboard() {
        const copyBtn = document.getElementById('copy-uuid-btn');
        const uuidContainer = document.getElementById('uuid-container');
        if (copyBtn && uuidContainer) {
            const uuidLabel = uuidContainer.querySelector('.uuid-label');
            const originalLabelText = uuidLabel.textContent; // ذخیره متن اصلی
            const fullUuid = copyBtn.dataset.uuid;

            uuidContainer.addEventListener('mouseenter', () => {
                uuidLabel.textContent = `شناسه یکتا : ${fullUuid}`;
                document.getElementById('uuid-masked').style.display = 'none';
            });
            uuidContainer.addEventListener('mouseleave', () => {
                uuidLabel.textContent = originalLabelText; // بازیابی متن اصلی
                document.getElementById('uuid-masked').style.display = 'inline-block';
            });
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(fullUuid).then(() => {
                    const originalIcon = copyBtn.innerHTML;
                    copyBtn.innerHTML = '<i class="ri-check-line"></i>';
                    setTimeout(() => { copyBtn.innerHTML = originalIcon; }, 2000);
                });
            });
        }

// --- Subscription Link & QR Code Logic ---
        const copySubBtn = document.getElementById('copy-sub-btn');
        const showQrBtn = document.getElementById('show-qr-btn');
        const fullSubLinkInput = document.getElementById('full-sub-link');
        const subLinkMasked = document.getElementById('sub-link-masked');

        if (subLinkMasked) {
            subLinkMasked.addEventListener('click', () => {
                subLinkMasked.style.display = 'none';
                fullSubLinkInput.style.display = 'block';
                fullSubLinkInput.select();
            });
        }

        if (copySubBtn) {
            copySubBtn.addEventListener('click', () => {
                fullSubLinkInput.style.display = 'block'; // Ensure it's visible to copy
                fullSubLinkInput.select();
                navigator.clipboard.writeText(fullSubLinkInput.value).then(() => {
                    const originalIcon = copySubBtn.innerHTML;
                    copySubBtn.innerHTML = '<i class="ri-check-line"></i>';
                    setTimeout(() => { copySubBtn.innerHTML = originalIcon; }, 2000);
                });
            });
        }
        
        const modal = document.getElementById('qr-modal');
        if (showQrBtn && modal) {
            const closeBtn = modal.querySelector('.close-button');
            const qrcodeContainer = document.getElementById('qrcode-container');

            showQrBtn.addEventListener('click', () => {
                qrcodeContainer.innerHTML = ''; // Clear previous QR code
                new QRCode(qrcodeContainer, {
                    text: fullSubLinkInput.value,
                    width: 256,
                    height: 256,
                    colorDark : "#000000",
                    colorLight : "#ffffff",
                    correctLevel : QRCode.CorrectLevel.H
                });
                modal.style.display = 'block';
            });

            closeBtn.onclick = () => { modal.style.display = 'none'; }
            window.onclick = (event) => {
                if (event.target == modal) {
                    modal.style.display = 'none';
                }
            }
        }

        const trafficCard = document.querySelector('.total-traffic-card[data-used-gb]');
        if (trafficCard && typeof ApexCharts !== 'undefined') {
            const used = parseFloat(trafficCard.dataset.usedGb) || 0;
            const total = parseFloat(trafficCard.dataset.totalGb) || 0;
            const percentage = total > 0 ? Math.round((used / total) * 100) : 0;
            const isCurrentlyDark = document.body.classList.contains('dark-theme');

            const options = {
                chart: { type: 'radialBar', height: 180, sparkline: { enabled: true } },
                series: [percentage],
                plotOptions: {
                    radialBar: {
                        hollow: { size: '70%' },
                        dataLabels: {
                            name: { show: false },
                            value: {
                                show: true,
                                fontSize: '22px',
                                fontWeight: 'bold',
                                color: isCurrentlyDark ? '#FFFFFF' : '#111827',
                                formatter: (val) => `${val}%`
                            }
                        }
                    }
                },
                fill: { colors: [percentage > 85 ? '#ef4444' : '#4ade80'] },
                stroke: { lineCap: 'round' }
            };
            trafficChart = new ApexCharts(document.querySelector("#traffic-doughnut-chart"), options);
            trafficChart.render();
        }
    }

    function initializeAdminDashboard() {
        // ... (کد داشبورد ادمین)
    }

    // --- اجرای توابع بر اساس صفحه فعلی ---
    if (document.querySelector('.uuid-card')) {
        initializeUserDashboard();
    } else if (document.getElementById('users-table-body')) {
        initializeAdminDashboard();
    }
});
