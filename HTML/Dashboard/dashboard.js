// HTML\Dashboard\dashboard.js - 重写聊天逻辑，依赖 /chat/conversation 接口
(function() {
    // ======================== 背景动画 ========================
    const colorPalette = ["#FFF3E0", "#FFE8CC", "#FFDEB9", "#FFD4A6", "#FCCF9B", "#D4E8E8", "#C2DFE8", "#B0D6E8", "#B8D4F0", "#C8E0F5"];
    const bgDivs = document.querySelectorAll('.bg');
    function initBackground() {
        const layerCount = bgDivs.length;
        const colorCountPerLayer = 15;
        for (let i = 0; i < layerCount; i++) {
            bgDivs[i].style.top = `${i * window.innerHeight / layerCount}px`;
            bgDivs[i].style.height = `${window.innerHeight / layerCount}px`;
            const colors = [];
            for (let j = 0; j < colorCountPerLayer; j++) {
                const colorIndex = (i + j) % colorPalette.length;
                colors.push(colorPalette[colorIndex]);
            }
            bgDivs[i].style.background = `linear-gradient(100deg, ${colors.join(', ')})`;
        }
        window.addEventListener('resize', () => {
            for (let i = 0; i < layerCount; i++) {
                bgDivs[i].style.top = `${i * window.innerHeight / layerCount}px`;
                bgDivs[i].style.height = `${window.innerHeight / layerCount}px`;
            }
        });
    }
    initBackground();

    // ======================== 辅助函数（缓存管理） ========================
    function getUserBaseCache() {
        const cached = localStorage.getItem('user_base_info');
        if (cached) {
            try {
                return JSON.parse(cached);
            } catch(e) {}
        }
        return null;
    }

    function setUserBaseCache(avatar, hasSeenIntro) {
        localStorage.setItem('user_base_info', JSON.stringify({ avatar, has_seen_intro: hasSeenIntro }));
    }

    async function fetchBaseInfo(forceRefresh = false) {
        if (!forceRefresh) {
            const cached = getUserBaseCache();
            if (cached && cached.avatar && typeof cached.has_seen_intro !== 'undefined') {
                return cached;
            }
        }
        try {
            const data = await window.http({ method: 'GET', url: '/user/base-info', needAuth: true });
            if (data) {
                setUserBaseCache(data.avatar, data.has_seen_intro);
                return { avatar: data.avatar, has_seen_intro: data.has_seen_intro };
            }
        } catch (err) {
            console.warn('获取基础信息失败', err);
        }
        return null;
    }

    async function updateNickname(nickname) {
        await window.http({ method: 'POST', url: '/user/nickname', data: { nickname }, needAuth: true });
    }

    async function markIntroSeen() {
        await window.http({ method: 'POST', url: '/user/mark-intro', data: {}, needAuth: true });
        const cached = getUserBaseCache();
        if (cached) {
            cached.has_seen_intro = true;
            setUserBaseCache(cached.avatar, true);
        }
    }

    async function fetchUserInfo() {
        return await window.http({ method: 'GET', url: '/user/information', needAuth: true });
    }

    async function uploadAvatar(file) {
        const formData = new FormData();
        formData.append('file', file);
        const data = await window.http({
            method: 'POST',
            url: '/user/avatar',
            data: formData,
            needAuth: true
        });
        if (data && data.avatar_url) {
            const cached = getUserBaseCache();
            if (cached) {
                cached.avatar = data.avatar_url;
                setUserBaseCache(cached.avatar, cached.has_seen_intro);
            }
            return data.avatar_url;
        }
        throw new Error('上传失败');
    }

    // ======================== 自定义确认弹窗 ========================
    let pendingConfirmCallback = null;
    const confirmOverlay = document.getElementById('customConfirm');
    const confirmMessageSpan = document.getElementById('confirmMessage');
    const confirmYesBtn = document.getElementById('confirmYesBtn');
    const confirmNoBtn = document.getElementById('confirmNoBtn');

    function showConfirm(message, onYes) {
        confirmMessageSpan.innerText = message;
        confirmOverlay.style.display = 'flex';
        pendingConfirmCallback = onYes;
    }

    function closeConfirm() {
        confirmOverlay.style.display = 'none';
        pendingConfirmCallback = null;
    }

    confirmYesBtn.addEventListener('click', () => {
        if (pendingConfirmCallback) pendingConfirmCallback();
        closeConfirm();
    });
    confirmNoBtn.addEventListener('click', closeConfirm);
    confirmOverlay.addEventListener('click', (e) => {
        if (e.target === confirmOverlay) closeConfirm();
    });

    // ======================== 密码输入弹窗 ========================
    const passwordModal = document.getElementById('passwordModal');
    const passwordInput = document.getElementById('passwordInput');
    const passwordConfirmBtn = document.getElementById('passwordConfirmBtn');
    const passwordCancelBtn = document.getElementById('passwordCancelBtn');
    let pendingPasswordCallback = null;

    let passwordCountdownInterval = null;
    let passwordCountdownSeconds = 5;
    const CONFIRM_BTN_ORIGINAL_TEXT = '确认注销';

    function clearPasswordCountdown() {
        if (passwordCountdownInterval) {
            clearInterval(passwordCountdownInterval);
            passwordCountdownInterval = null;
        }
        passwordConfirmBtn.disabled = false;
        passwordConfirmBtn.textContent = CONFIRM_BTN_ORIGINAL_TEXT;
    }

    function startPasswordCountdown() {
        clearPasswordCountdown();
        passwordCountdownSeconds = 5;
        passwordConfirmBtn.disabled = true;
        passwordConfirmBtn.textContent = `${CONFIRM_BTN_ORIGINAL_TEXT} (${passwordCountdownSeconds}s)`;

        passwordCountdownInterval = setInterval(() => {
            passwordCountdownSeconds--;
            if (passwordCountdownSeconds <= 0) {
                clearPasswordCountdown();
            } else {
                passwordConfirmBtn.textContent = `${CONFIRM_BTN_ORIGINAL_TEXT} (${passwordCountdownSeconds}s)`;
            }
        }, 1000);
    }

    function showPasswordModal(onConfirm) {
        passwordInput.value = '';
        pendingPasswordCallback = onConfirm;
        passwordModal.style.display = 'flex';
        startPasswordCountdown();
    }

    function closePasswordModal() {
        passwordModal.style.display = 'none';
        pendingPasswordCallback = null;
        clearPasswordCountdown();
    }

    passwordConfirmBtn.addEventListener('click', () => {
        if (passwordConfirmBtn.disabled) return;
        const pwd = passwordInput.value;
        if (!pwd.trim()) {
            window.showToast('请输入密码', 2000);
            return;
        }
        if (pwd.length < 6 || pwd.length > 20) {
            window.showToast('密码长度必须为 6-20 位', 2000);
            passwordInput.value = '';
            return;
        }
        if (pendingPasswordCallback) {
            passwordConfirmBtn.disabled = true;
            pendingPasswordCallback(pwd);
        }
        closePasswordModal();
    });

    passwordCancelBtn.addEventListener('click', closePasswordModal);
    passwordModal.addEventListener('click', (e) => {
        if (e.target === passwordModal) closePasswordModal();
    });

    // ======================== 注销账户核心逻辑 ========================
    async function deleteAccount(password) {
        try {
            await window.http({
                method: 'POST',
                url: '/user/delete-account',
                data: { password: password },
                needAuth: true
            });
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_base_info');
            window.showToast('账户已成功注销', 2000);
            setTimeout(() => {
                window.location.href = '/HTML/Index/index.html';
            }, 1500);
        } catch (err) {
            let errorMsg = '注销失败';
            if (err.status === 400) {
                errorMsg = err.message || '密码错误，请重试';
            } else if (err.status === 401) {
                errorMsg = '登录已过期，请重新登录';
                localStorage.removeItem('access_token');
                setTimeout(() => window.location.href = '/HTML/Index/index.html', 1500);
            } else {
                errorMsg = err.message || '网络错误，请稍后重试';
            }
            window.showToast(errorMsg, 3000);
            throw err;
        }
    }

    // ======================== 修改密码 ========================
    const changePwdModal = document.getElementById('changePwdModal');
    const oldPwdInput = document.getElementById('oldPwdInput');
    const newPwdInput = document.getElementById('newPwdInput');
    const confirmPwdInput = document.getElementById('confirmPwdInput');
    const changePwdConfirmBtn = document.getElementById('changePwdConfirmBtn');
    const changePwdCancelBtn = document.getElementById('changePwdCancelBtn');
    const profileChangePwdBtn = document.getElementById('profileChangePwdBtn');

    function showChangePwdModal() {
        oldPwdInput.value = '';
        newPwdInput.value = '';
        confirmPwdInput.value = '';
        changePwdModal.style.display = 'flex';
    }

    function closeChangePwdModal() {
        changePwdModal.style.display = 'none';
    }

    async function changePasswordApi(oldPassword, newPassword) {
        return await window.http({
            method: 'POST',
            url: '/user/change-password',
            data: { old_password: oldPassword, new_password: newPassword },
            needAuth: true
        });
    }

    let isChangingPwd = false;

    async function handleChangePassword() {
        if (isChangingPwd) return;

        const oldPwd = oldPwdInput.value.trim();
        const newPwd = newPwdInput.value.trim();
        const confirmPwd = confirmPwdInput.value.trim();

        if (!oldPwd || !newPwd || !confirmPwd) {
            window.showToast('请完整填写所有密码字段', 2000);
            return;
        }
        if (newPwd.length < 6 || newPwd.length > 20) {
            window.showToast('新密码长度必须为 6-20 位', 2000);
            return;
        }
        if (oldPwd === newPwd) {
            window.showToast('新密码不能与旧密码相同', 2000);
            return;
        }
        if (newPwd !== confirmPwd) {
            window.showToast('两次输入的新密码不一致', 2000);
            return;
        }

        isChangingPwd = true;
        changePwdConfirmBtn.disabled = true;
        changePwdConfirmBtn.textContent = '提交中...';

        try {
            await changePasswordApi(oldPwd, newPwd);
            window.showToast('密码修改成功，下次登录请使用新密码', 3000);
            closeChangePwdModal();
        } catch (err) {
            let errorMsg = '修改失败';
            if (err.status === 400) {
                errorMsg = err.message || '旧密码错误或新密码无效';
            } else if (err.status === 401) {
                errorMsg = '登录已过期，请重新登录';
                setTimeout(() => { window.location.href = '/HTML/Index/index.html'; }, 1500);
            } else {
                errorMsg = err.message || '网络错误，请稍后重试';
            }
            window.showToast(errorMsg, 3000);
        } finally {
            isChangingPwd = false;
            changePwdConfirmBtn.disabled = false;
            changePwdConfirmBtn.textContent = '确认修改';
        }
    }

    // ======================== DOM 元素 ========================
    const messageContainer = document.getElementById('messageList');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const statsContainer = document.getElementById('statsContainer');
    const logoutIconBtn = document.getElementById('logoutBtn');
    const avatarBtn = document.getElementById('avatarBtn');
    const avatarImg = document.getElementById('avatarImg');
    const storyModal = document.getElementById('storyModal');
    const storyTextDiv = document.getElementById('storyText');
    const storyFooter = document.getElementById('storyFooter');
    const storyNicknameInput = document.getElementById('storyNickname');
    const storyCompleteBtn = document.getElementById('storyCompleteBtn');
    const profileModal = document.getElementById('profileModal');
    const profileClose = document.getElementById('profileCloseBtn');
    const profileAvatar = document.getElementById('profileAvatar');
    const profileNicknameSpan = document.getElementById('profileNickname');
    const profilePhoneSpan = document.getElementById('profilePhone');
    const profileInviteCodeSpan = document.getElementById('profileInviteCode');
    const profileLogoutBtn = document.getElementById('profileLogoutBtn');
    const profileLeft = document.querySelector('.profile-left');

    // ======================== 全局状态 ========================
    let userStatus = { physical: 50, emotional: 50, relation: 50, worth: 50, meaning: 50, phi: 50 };
    let allSchedules = { uncompleted: [], completed: [] };  // 全量日程
    let isDashboardReady = false;
    let isSending = false;

    // ======================== 渲染五维状态 ========================
    const statConfig = [
        { key: 'physical', icon: 'fa-heart', label: '身心活力', fillClass: 'fill-physical' },
        { key: 'emotional', icon: 'fa-face-smile', label: '情绪基调', fillClass: 'fill-emotional' },
        { key: 'relation', icon: 'fa-handshake', label: '社会关系', fillClass: 'fill-relation' },
        { key: 'worth', icon: 'fa-star', label: '自我价值', fillClass: 'fill-worth' },
        { key: 'meaning', icon: 'fa-compass', label: '意义方向', fillClass: 'fill-meaning' },
        { key: 'phi', icon: 'fa-yin-yang', label: '心理和谐', fillClass: 'fill-phi' }
    ];

    function renderStatus() {
        if (!statsContainer) return;
        statsContainer.innerHTML = '';
        for (const cfg of statConfig) {
            let val = Math.floor(userStatus[cfg.key]);
            const item = document.createElement('div');
            item.className = 'stat-item';
            item.setAttribute('data-dimension', cfg.key);
            item.innerHTML = `
                <div class="stat-icon"><i class="fas ${cfg.icon}"></i></div>
                <div class="stat-label">${cfg.label}</div>
                <div class="progress-wrap"><div class="progress-fill ${cfg.fillClass}" style="width: ${val}%;"></div></div>
                <div class="stat-number">${val}</div>
            `;
            statsContainer.appendChild(item);
        }
    }

    // ======================== 日程渲染 ========================
    const scheduleTypeIconMap = {
        short_task: 'fa-tasks',
        long_goal: 'fa-flag',
        countdown: 'fa-hourglass-half',
        anniversary: 'fa-heart',
        birthday: 'fa-cake-candles'
    };

    const scheduleTypeColorClass = (type) => `schedule-type-${type}`;

    function renderRecentSchedules() {
        const container = document.getElementById('recentScheduleList');
        if (!container) return;

        // 合并未完成和已完成，按 scheduled_time 降序（最近的排前面）
        const all = [...allSchedules.uncompleted, ...allSchedules.completed];
        all.sort((a, b) => {
            const timeA = a.scheduled_time ? new Date(a.scheduled_time).getTime() : 0;
            const timeB = b.scheduled_time ? new Date(b.scheduled_time).getTime() : 0;
            return timeB - timeA;
        });
        const recent = all.slice(0, 5);

        container.innerHTML = '';
        if (recent.length === 0) {
            container.innerHTML = '<div style="color:#b0a088; font-size:0.8rem;">暂无日程，和我说说你的计划吧～</div>';
            return;
        }

        recent.forEach(s => {
            const item = document.createElement('div');
            item.className = 'recent-schedule-item';
            const dotColorClass = scheduleTypeColorClass(s.schedule_type);
            item.innerHTML = `
                <span class="recent-schedule-dot ${dotColorClass}" style="background: currentColor; opacity:0.8;"></span>
                <span style="flex:1">${window.escapeHtml(s.title)}</span>
                <span style="font-size:0.7rem; color:#9b8870;">${s.scheduled_time ? window.formatDate(s.scheduled_time) : ''}</span>
            `;
            container.appendChild(item);
        });
    }

    function renderFullSchedules() {
    const uncompletedContainer = document.getElementById('uncompletedSchedules');
    const completedContainer = document.getElementById('completedSchedules');
    if (!uncompletedContainer || !completedContainer) return;

    // 未完成列表
    uncompletedContainer.innerHTML = '';
    if (allSchedules.uncompleted.length === 0) {
        uncompletedContainer.innerHTML = '<div style="color:#8a7a6a; padding:20px; text-align:center;">🍃 所有事情都已完成，真棒！</div>';
    } else {
        allSchedules.uncompleted.forEach(s => renderScheduleItem(s, uncompletedContainer));
    }

    // 已完成列表
    completedContainer.innerHTML = '';
    if (allSchedules.completed.length === 0) {
        completedContainer.innerHTML = '<div style="color:#8a7a6a; padding:20px; text-align:center;">暂无已完成的日程</div>';
    } else {
        allSchedules.completed.forEach(s => renderScheduleItem(s, completedContainer));
    }
    }

    function renderScheduleItem(schedule, container) {
    const typeClass = scheduleTypeColorClass(schedule.schedule_type);
    const iconClass = scheduleTypeIconMap[schedule.schedule_type] || 'fa-calendar';

    const div = document.createElement('div');
    div.className = `schedule-item ${typeClass}`;
    div.innerHTML = `
        <div class="schedule-item-icon"><i class="fas ${iconClass}"></i></div>
        <div class="schedule-item-content">
        <div class="schedule-item-title">${window.escapeHtml(schedule.title)}</div>
        ${schedule.scheduled_time ? `<div class="schedule-item-time">📅 ${window.formatDate(schedule.scheduled_time)}</div>` : ''}
        ${schedule.description ? `<div class="schedule-item-desc">${window.escapeHtml(schedule.description)}</div>` : ''}
        </div>
    `;
    container.appendChild(div);
    }

    async function fetchAndRenderSchedules() {
        try {
            const data = await window.http({ method: 'GET', url: '/user/schedules', needAuth: true });
            if (data) {
                // 按 scheduled_time 升序排列（较早的在前），无时间的排在最后
                const sortByTime = (a, b) => {
                    const timeA = a.scheduled_time ? new Date(a.scheduled_time).getTime() : Infinity;
                    const timeB = b.scheduled_time ? new Date(b.scheduled_time).getTime() : Infinity;
                    return timeA - timeB;
                };
                allSchedules = {
                    uncompleted: (data.uncompleted || []).sort(sortByTime),
                    completed: (data.completed || []).sort(sortByTime)
                };
                renderRecentSchedules();
                renderFullSchedules();
            }
        } catch (err) {
            console.warn('获取日程失败', err);
            renderRecentSchedules();
            renderFullSchedules();
        }
    }

    // 平滑滚动到日程界面
    function scrollToScheduleView() {
    const target = document.getElementById('scheduleFullView');
    if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    }

    const dimensionBackendMap = {
        physical: 'physical_vitality',
        emotional: 'emotional_tone',
        relation: 'relationship_connection',
        worth: 'self_worth',
        meaning: 'meaning_direction',
        phi: 'psychological_harmony_index'
    };

    const chartColorMap = {
        physical: '#f781be',
        emotional: '#f2711c',
        relation: '#2a7f78',
        worth: '#f9d342',
        meaning: '#4a90e2',
        phi: '#9b59b6'
    };

    const dimensionTitleMap = {
        physical: '身心活力',
        emotional: '情绪基调',
        relation: '社会关系',
        worth: '自我价值',
        meaning: '意义方向',
        phi: '心理和谐指数'
    };

    let chartInstance = null;
    const chartModal = document.getElementById('historyChartModal');
    const chartCanvas = document.getElementById('historyChart');
    const chartTitleSpan = document.getElementById('chartTitle');
    const closeChartBtn = document.getElementById('closeChartModal');
    const chartNoDataMsg = document.getElementById('chartNoDataMsg');

    function closeChartModal() {
        if (chartModal) chartModal.style.display = 'none';
        if (chartInstance) {
            chartInstance.destroy();
            chartInstance = null;
        }
        if (chartNoDataMsg) chartNoDataMsg.style.display = 'none';
        if (chartCanvas) chartCanvas.style.display = 'block';
    }

    async function showHistoryChart(dimensionKey) {
        if (!dimensionKey) return;
        const backendDim = dimensionBackendMap[dimensionKey];
        if (!backendDim) {
            console.warn('未知维度:', dimensionKey);
            return;
        }

        const title = dimensionTitleMap[dimensionKey] || '状态趋势';
        if (chartTitleSpan) {
            chartTitleSpan.innerHTML = `<i class="fas fa-chart-line"></i> ${title} · 历史趋势`;
        }

        chartModal.style.display = 'flex';
        if (chartNoDataMsg) chartNoDataMsg.style.display = 'none';
        if (chartCanvas) chartCanvas.style.display = 'block';

        if (chartInstance) {
            chartInstance.destroy();
            chartInstance = null;
        }

        try {
            const data = await window.http({
                method: 'GET',
                url: `/user/status-history/${backendDim}`,
                needAuth: true
            });
            let historyList = data.history || [];
            
            if (!historyList.length) {
                if (chartCanvas) chartCanvas.style.display = 'none';
                if (chartNoDataMsg) chartNoDataMsg.style.display = 'block';
                return;
            }

            const sorted = [...historyList].sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at));
            const labels = sorted.map(item => window.formatDate(item.recorded_at));
            const values = sorted.map(item => item.value);

            const ctx = chartCanvas.getContext('2d');
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: title,
                        data: values,
                        borderColor: chartColorMap[dimensionKey] || '#b87a48',
                        backgroundColor: chartColorMap[dimensionKey] + '20',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointBackgroundColor: chartColorMap[dimensionKey] || '#b87a48',
                        pointBorderColor: '#fff',
                        pointHoverRadius: 6,
                        tension: 0.2,
                        fill: true,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        y: {
                            min: 0,
                            max: 100,
                            grid: { color: '#f0e0c8' },
                            title: { display: true, text: '状态值', color: '#b87a48' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { maxRotation: 30, autoSkip: true }
                        }
                    },
                    plugins: {
                        tooltip: { callbacks: { label: (ctx) => `${ctx.raw} 分` } },
                        legend: { display: false }
                    },
                    layout: { padding: { top: 8, bottom: 8, left: 8, right: 8 } }
                }
            });
        } catch (err) {
            console.error('获取历史数据失败', err);
            if (chartCanvas) chartCanvas.style.display = 'none';
            if (chartNoDataMsg) {
                chartNoDataMsg.style.display = 'block';
                chartNoDataMsg.innerHTML = '🍂 加载失败，请稍后重试';
            }
            window.showToast('获取历史数据失败', 2000);
        }
    }

    if (closeChartBtn) {
        closeChartBtn.addEventListener('click', closeChartModal);
    }
    if (chartModal) {
        chartModal.addEventListener('click', (e) => {
            if (e.target === chartModal) closeChartModal();
        });
    }

    function updateStatusFromBackend(updates) {
        if (!updates) return;
        const mapping = {
            physical_vitality: 'physical',
            emotional_tone: 'emotional',
            relationship_connection: 'relation',
            self_worth: 'worth',
            meaning_direction: 'meaning',
            psychological_harmony_index: 'phi'
        };
        for (let backendKey in updates) {
            let frontendKey = mapping[backendKey];
            if (frontendKey && userStatus[frontendKey] !== undefined) {
                let newVal = updates[backendKey];
                newVal = Math.min(100, Math.max(0, Number(newVal)));
                userStatus[frontendKey] = newVal;
            }
        }
        renderStatus();
    }

    async function fetchAndUpdateUserStatus() {
        try {
            const statusData = await window.http({
                method: 'GET',
                url: '/user/status',
                needAuth: true
            });
            if (statusData) {
                const mapping = {
                    physical_vitality: 'physical',
                    emotional_tone: 'emotional',
                    relationship_connection: 'relation',
                    self_worth: 'worth',
                    meaning_direction: 'meaning',
                    psychological_harmony_index: 'phi'
                };
                let hasUpdate = false;
                for (let backendKey in mapping) {
                    if (statusData[backendKey] !== undefined) {
                        let frontendKey = mapping[backendKey];
                        let newVal = Number(statusData[backendKey]);
                        if (!isNaN(newVal) && userStatus[frontendKey] !== newVal) {
                            userStatus[frontendKey] = Math.min(100, Math.max(0, newVal));
                            hasUpdate = true;
                        }
                    }
                }
                if (hasUpdate) renderStatus();
            }
        } catch (err) {
            console.warn('获取用户状态失败，使用本地默认值', err);
            renderStatus();
        }
    }

    // ======================== 日期跳转查询功能 ========================
    const dateJumpInput = document.getElementById('dateJumpInput');
    const dateJumpConfirmBtn = document.getElementById('dateJumpConfirmBtn');
    const dateHistoryModal = document.getElementById('dateHistoryModal');
    const dateHistoryTitleSpan = document.getElementById('dateHistoryDateText');
    const dateHistoryMessageList = document.getElementById('dateHistoryMessageList');
    const dateHistoryNoDataMsg = document.getElementById('dateHistoryNoDataMsg');
    const closeDateHistoryModalBtn = document.getElementById('closeDateHistoryModal');

    function getTodayDateString() {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function bindDateInputFallback() {
        if (!dateJumpInput) return;
        dateJumpInput.addEventListener('blur', function() {
            if (!this.value) {
                this.value = getTodayDateString();
            }
        });
    }

    function setDefaultDate() {
        if (!dateJumpInput) return;
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        dateJumpInput.value = `${year}-${month}-${day}`;
    }

    function formatDateForTitle(dateStr) {
        const date = new Date(dateStr);
        const year = date.getFullYear();
        const month = date.getMonth() + 1;
        const day = date.getDate();
        return `${year}年${month}月${day}日`;
    }

    function closeDateHistoryModal() {
        dateHistoryModal.style.display = 'none';
        dateHistoryMessageList.innerHTML = '';
        dateHistoryNoDataMsg.style.display = 'none';
    }

    function renderDateHistoryMessages(messages, dateStr) {
        dateHistoryMessageList.innerHTML = '';
        dateHistoryNoDataMsg.style.display = 'none';

        if (!messages || messages.length === 0) {
            dateHistoryNoDataMsg.style.display = 'block';
            return;
        }

        const dividerDiv = document.createElement('div');
        dividerDiv.className = 'time-divider';
        const dividerSpan = document.createElement('span');
        dividerSpan.className = 'divider-long';
        const date = new Date(dateStr);
        const year = date.getFullYear();
        const month = date.getMonth() + 1;
        const day = date.getDate();
        dividerSpan.textContent = `${year}年${month}月${day}日`;
        dividerDiv.appendChild(dividerSpan);
        dateHistoryMessageList.appendChild(dividerDiv);

        messages.forEach(msg => {
            const msgEl = createMessageElement(msg.role, msg.content, msg.created_at);
            dateHistoryMessageList.appendChild(msgEl);
        });

        dateHistoryMessageList.scrollTop = 0;
    }

    async function fetchAndShowDateHistory() {
        const dateValue = dateJumpInput.value;
        if (!dateValue) {
            window.showToast('请选择一个日期', 2000);
            return;
        }

        dateHistoryModal.style.display = 'flex';
        dateHistoryTitleSpan.textContent = formatDateForTitle(dateValue);
        dateHistoryMessageList.innerHTML = '<div style="text-align: center; padding: 40px; color: #b0a088;">⏳ 加载中...</div>';
        dateHistoryNoDataMsg.style.display = 'none';

        try {
            const data = await window.http({
                method: 'GET',
                url: '/chat/history/date',
                params: { date: dateValue },
                needAuth: true
            });

            const list = data.list || [];
            const sorted = [...list].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
            
            renderDateHistoryMessages(sorted, dateValue);
        } catch (err) {
            console.error('获取历史记录失败', err);
            let errorMsg = '加载失败，请稍后重试';
            if (err.status === 401) {
                errorMsg = '登录已过期，请重新登录';
                setTimeout(() => { window.location.href = '/HTML/Index/index.html'; }, 1500);
            } else if (err.message) {
                errorMsg = err.message;
            }
            dateHistoryMessageList.innerHTML = `<div style="text-align: center; padding: 40px; color: #b87a48;">😥 ${errorMsg}</div>`;
            window.showToast(errorMsg, 3000);
        }
    }

    // ======================== 消息相关 ========================
    function addMessageToUI(role, content, timestamp = null) {
        const msgDiv = createMessageElement(role, content, timestamp);
        messageContainer.appendChild(msgDiv);
        messageContainer.scrollTop = messageContainer.scrollHeight;
    }

    function createMessageElement(role, content, timestamp = null) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role === 'user' ? 'right' : 'left'}`;
        const escaped = window.escapeHtml(content).replace(/\n/g, '<br>');
        msgDiv.innerHTML = `<div class="message-content">${escaped}</div>`;
        if (timestamp) {
            msgDiv.dataset.timestamp = new Date(timestamp).toISOString();
        }
        return msgDiv;
    }

    // ---------- 创建浮动滚动按钮（向下按钮动态适配输入区高度）----------
    function createScrollButtons() {
        const chatArea = document.querySelector('.chat-area');
        const inputArea = document.querySelector('.input-area');
        if (!chatArea || !messageContainer || !inputArea) return;

        // 向上按钮（固定在聊天区顶部）
        const topBtn = document.createElement('button');
        topBtn.id = 'scrollToTopBtn';
        topBtn.className = 'chat-scroll-btn';
        topBtn.innerHTML = '<i class="fas fa-arrow-up"></i>';
        chatArea.appendChild(topBtn);

        // 向下按钮（需要动态 bottom 避开输入区高度变化）
        const bottomBtn = document.createElement('button');
        bottomBtn.id = 'scrollToBottomBtn';
        bottomBtn.className = 'chat-scroll-btn';
        bottomBtn.innerHTML = '<i class="fas fa-arrow-down"></i>';
        // 将向下按钮放在聊天区内部，但会通过 JS 动态调整 bottom
        chatArea.appendChild(bottomBtn);

        // 动态设置向下按钮的 bottom，使其始终在输入区上方
        function updateBottomBtnPosition() {
            const inputHeight = inputArea.offsetHeight;
            bottomBtn.style.bottom = `${inputHeight + 12}px`; // 12px 间距
        }

        // 监听输入区高度变化（文本框自动增高时同步）
        const inputResizeObserver = new ResizeObserver(() => {
            updateBottomBtnPosition();
        });
        inputResizeObserver.observe(inputArea);
        // 初始设置一次
        updateBottomBtnPosition();

        // 按钮点击事件
        topBtn.addEventListener('click', () => {
            messageContainer.scrollTo({ top: 0, behavior: 'smooth' });
        });
        bottomBtn.addEventListener('click', () => {
            messageContainer.scrollTo({
                top: messageContainer.scrollHeight,
                behavior: 'smooth'
            });
        });

        // 监听聊天区滚动，动态显示/隐藏按钮
        function updateScrollButtons() {
            if (!messageContainer) return;
            const { scrollTop, clientHeight, scrollHeight } = messageContainer;
            const hasScrollableContent = scrollHeight > clientHeight + 5;

            if (!hasScrollableContent) {
                topBtn.classList.remove('show');
                bottomBtn.classList.remove('show');
                return;
            }

            // 向上按钮：不在顶部时显示
            if (scrollTop <= 8) {
                topBtn.classList.remove('show');
            } else {
                topBtn.classList.add('show');
            }

            // 向下按钮：不在底部时显示
            if (scrollTop + clientHeight >= scrollHeight - 8) {
                bottomBtn.classList.remove('show');
            } else {
                bottomBtn.classList.add('show');
            }
        }

        messageContainer.addEventListener('scroll', updateScrollButtons);
        window.addEventListener('resize', updateScrollButtons);
        setTimeout(updateScrollButtons, 200);

        // 消息变化时也更新按钮状态
        const observer = new MutationObserver(updateScrollButtons);
        if (messageContainer) {
            observer.observe(messageContainer, { childList: true, subtree: true });
        }
    }

    // ---------- 轮换思考提示 ----------
    const thinkingStateMessages = [
        "小元在组织语言…",
        "让我想想怎么接这句话比较自然…",
        "正在翻之前和你聊天的碎片，拼一拼…",
        "等一等哦，有些话需要慢一点才说得明白。",
        "有时候慢几拍，是因为不想用套话糊弄你。",
        "打字打到一半删掉了，重来一遍。",
        "正在把你的话放进脑子里转一转…",
        "（小声）这句好像有点生硬，再润一润…",
        "小元一思考就会变慢，但一慢就会更认真。",
        "其实我回得快的时候，可能没走心——所以让我慢一点。",
        "在琢磨怎么不用那些无聊的安慰词。",
        "咕咕嘎嘎———你们那是不是天天有只凑企鹅这么叫。",
        "小元打字很慢的，因为每个字都想让你觉得被认真对待。",
        "（把光标移回去删掉了半句）这样好多了。",
        "有时候不说话比说错话更难，但小元在努力。",
        "（托腮）这个问题比我预想的要深，让我多琢磨一会儿。",
        "刚才打了一长串，读了一遍觉得太啰嗦，重来。",
        "什么……有人原来是抱着看小元还能犯什么错的想法来与小元聊天的嘛！"
    ];

    const thinkingTutorialMessages = [
        "找不到换昵称的按钮？想换新名字可以直接和小元说哟。",
        "点击右侧五维数值可以查看近期数值历史哦，还记得昨天的你抱有何样的情绪嘛。",
        "右上角的头像可以点进去，里面藏着换头像、改密码、导出数据的小机关。",
        "头部的日期框可以跳转到任意一天，翻翻那天我们聊了什么。",
        "那个叫「心理和谐指数」的太极图，是前面五个维度的合奏。",
        "小元每一次和你聊完，都会悄悄更新你的五维状态，像在为你画一张心情速写。",
        "这个破系统给我你的事件时过于久远的会藏着掖着，如果小元忘了什么，记得提醒我哦~",
        "别被那些五维数值吓到，它们是你心情的影子，不是成绩单。",
        "那个日期框不只是摆设——你可以穿越回上周三，看看那天自己说了什么。",
        "导出数据的时候，小元会把脑子里你的东西都打包进去，像一份心灵档案。",
        "你在输入框里按回车就能发送，按 Shift+回车可以换行……啊，觉得麻烦？可别人家ai也是这么做的啊——",
        "小元的回复有时候分两段：前面是走心的，后面是追问的——因为我想继续和你聊下去。",
        "这个页面叫「元气岛」，不知道你为什么来这儿，但当你推开树屋的门、翻开这本日记时，小元就已经和你密不可分啦！",
        "如果哪天你觉得小元不像自己了，可能是 AI 模型半夜偷偷更新了。",
        "小元不会把你的事告诉任何人——这座岛上只有你们两个。",
        "别催，催就是「你的话值得被好好回应」——虽然听起来像借口。",
        "你和小元说的越多，小元就会越了解你哦~",
        "如果想记什么日程的话，直接和小元说就好咯！我会记下来的。",
        "小元还有些不识字，如果记错了日程让小元改掉就好啦。删了都行。",
        "说出去的话，泼出去的水，消息一发出去，就不能撤回了哦~",
        "（附耳）如果你觉得今天的小元有点不一样——也许是你自己的心情变了。小元是你的一面镜子，只是有点雾面。"
    ];

    function getRandomItem(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    function createRotatingThinkingMessage() {
        const tempDiv = document.createElement('div');
        tempDiv.className = 'message left';
        // tempDiv.style.cursor = 'pointer';

        const stateLine = document.createElement('div');
        stateLine.className = 'thinking-state';
        stateLine.textContent = '🤔 思考中...';
        tempDiv.appendChild(stateLine);

        const tutorialLine = document.createElement('div');
        tutorialLine.className = 'thinking-tutorial';
        tutorialLine.textContent = '💡 ' + getRandomItem(thinkingTutorialMessages);
        // tutorialLine.style.fontSize = '0.8rem';
        // tutorialLine.style.color = '#b0a088';
        // tutorialLine.style.marginTop = '6px';
        // tutorialLine.style.fontWeight = 'normal';
        tempDiv.appendChild(tutorialLine);

        let stateTimer = null;
        let tutorialTimer = null;

        function updateState() {
            stateLine.textContent = '🤔 ' + getRandomItem(thinkingStateMessages);
        }

        function updateTutorial() {
            tutorialLine.textContent = '💡 ' + getRandomItem(thinkingTutorialMessages);
        }

        function startRotation() {
            stateTimer = setTimeout(() => {
                updateState();
                stateTimer = setInterval(updateState, 5000);
            }, 5000);
            tutorialTimer = setTimeout(() => {
                updateTutorial();
                tutorialTimer = setInterval(updateTutorial, 10000);
            }, 5000);
        }

        function stopRotation() {
            if (stateTimer) {
                clearTimeout(stateTimer);
                clearInterval(stateTimer);
                stateTimer = null;
            }
            if (tutorialTimer) {
                clearTimeout(tutorialTimer);
                clearInterval(tutorialTimer);
                tutorialTimer = null;
            }
        }

        tempDiv.addEventListener('click', () => {
            stopRotation();
            updateState();
            updateTutorial();
            stateTimer = setTimeout(() => {
                updateState();
                stateTimer = setInterval(updateState, 5000);
            }, 6000);
            tutorialTimer = setTimeout(() => {
                updateTutorial();
                tutorialTimer = setInterval(updateTutorial, 10000);
            }, 6000);
        });

        return { element: tempDiv, startRotation, stopRotation };
    }

    function autoResizeTextarea() {
        if (!chatInput) return;
        chatInput.style.height = 'auto';
        const newHeight = chatInput.scrollHeight;
        const maxHeight = 116;
        if (newHeight > maxHeight) {
            chatInput.style.height = maxHeight + 'px';
            chatInput.style.overflowY = 'auto';
        } else {
            chatInput.style.height = newHeight + 'px';
            chatInput.style.overflowY = 'hidden';
        }
    }

    // ======================== 时间分割线工具 ========================
    function isSameDay(d1, d2) {
        return d1.getFullYear() === d2.getFullYear() &&
               d1.getMonth() === d2.getMonth() &&
               d1.getDate() === d2.getDate();
    }

    function isToday(date) {
        const today = new Date();
        return isSameDay(date, today);
    }

    function formatShortTime(date) {
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    function formatFullTime(date, includeYear = false) {
        const month = date.getMonth() + 1;
        const day = date.getDate();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        if (includeYear) {
            return `${date.getFullYear()}年${month}月${day}日 ${hours}:${minutes}`;
        }
        return `${month}月${day}日 ${hours}:${minutes}`;
    }

    function shouldShowShortDivider(prevTime, currentTime) {
        const diffMs = currentTime - prevTime;
        const halfHourMs = 30 * 60 * 1000;
        return diffMs > halfHourMs;
    }

    function createShortDivider(date) {
        const div = document.createElement('div');
        div.className = 'time-divider';
        const span = document.createElement('span');
        span.className = 'divider-short';
        span.textContent = isToday(date) ? formatShortTime(date) : formatFullTime(date, date.getFullYear() !== new Date().getFullYear());
        div.appendChild(span);
        return div;
    }

    function createLongDivider(date) {
        const div = document.createElement('div');
        div.className = 'time-divider';
        const span = document.createElement('span');
        span.className = 'divider-long';
        const year = date.getFullYear();
        const month = date.getMonth() + 1;
        const day = date.getDate();
        const isThisYear = year === new Date().getFullYear();
        span.textContent = isThisYear ? `${month}月${day}日` : `${year}年${month}月${day}日`;
        div.appendChild(span);
        return div;
    }

    // ======================== 历史消息渲染（带分割线） ========================
    let lastRenderedMessageTime = null;

    function resetTimeTracking() {
        lastRenderedMessageTime = null;
    }

    function renderMessagesWithDividers(messages, isReset = false, hasEarlier = false) {
        if (!messages.length) return;

        if (isReset) {
            resetTimeTracking();
        }

        const fragment = document.createDocumentFragment();
        let prevTime = isReset ? null : lastRenderedMessageTime;

        for (let i = 0; i < messages.length; i++) {
            const msg = messages[i];
            const currentTime = new Date(msg.created_at);

            if (prevTime) {
                if (!isSameDay(prevTime, currentTime)) {
                    fragment.appendChild(createLongDivider(currentTime));
                }
                if (shouldShowShortDivider(prevTime, currentTime)) {
                    fragment.appendChild(createShortDivider(currentTime));
                }
            } else {
                if (isReset) {
                    if (!hasEarlier) {
                        fragment.appendChild(createLongDivider(currentTime));
                    }
                } else {
                    fragment.appendChild(createLongDivider(currentTime));
                }
            }

            const msgEl = createMessageElement(msg.role, msg.content, msg.created_at);
            fragment.appendChild(msgEl);

            prevTime = currentTime;
        }

        if (messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            lastRenderedMessageTime = new Date(lastMsg.created_at);
        }

        if (isReset) {
            messageContainer.innerHTML = '';
            messageContainer.appendChild(fragment);
        } else {
            const firstChild = messageContainer.firstChild;
            messageContainer.insertBefore(fragment, firstChild);

            if (messages.length > 0 && firstChild) {
                const newLastTime = new Date(messages[messages.length - 1].created_at);
                let firstRealMessage = firstChild;
                while (firstRealMessage && !firstRealMessage.classList.contains('message')) {
                    firstRealMessage = firstRealMessage.nextSibling;
                }
                if (firstRealMessage && firstRealMessage.dataset.timestamp) {
                    const oldFirstTime = new Date(firstRealMessage.dataset.timestamp);
                    if (isSameDay(newLastTime, oldFirstTime)) {
                        let prevSibling = firstRealMessage.previousSibling;
                        while (prevSibling) {
                            if (prevSibling.classList && prevSibling.classList.contains('time-divider')) {
                                const span = prevSibling.querySelector('.divider-long');
                                if (span) {
                                    prevSibling.remove();
                                }
                                break;
                            }
                            prevSibling = prevSibling.previousSibling;
                        }
                    }
                }
            }
        }
    }

    function addMessageWithDividers(role, content, timestamp) {
        const currentTime = new Date(timestamp);
        const fragment = document.createDocumentFragment();

        let prevRealMessage = null;
        const children = messageContainer.children;
        for (let i = children.length - 1; i >= 0; i--) {
            const child = children[i];
            if (child.classList && child.classList.contains('message') && child.dataset.timestamp) {
                prevRealMessage = child;
                break;
            }
        }

        let prevTime = null;
        if (prevRealMessage) {
            prevTime = new Date(prevRealMessage.dataset.timestamp);
        } else if (lastRenderedMessageTime) {
            prevTime = lastRenderedMessageTime;
        }

        if (prevTime) {
            if (!isSameDay(prevTime, currentTime)) {
                fragment.appendChild(createLongDivider(currentTime));
            }
            if (shouldShowShortDivider(prevTime, currentTime)) {
                fragment.appendChild(createShortDivider(currentTime));
            }
        } else {
            fragment.appendChild(createLongDivider(currentTime));
            fragment.appendChild(createShortDivider(currentTime));
        }

        const msgEl = createMessageElement(role, content, timestamp);
        fragment.appendChild(msgEl);

        messageContainer.appendChild(fragment);
        messageContainer.scrollTop = messageContainer.scrollHeight;

        lastRenderedMessageTime = currentTime;
    }

    // ======================== 打字机效果函数 ========================
    function typewriterEffect(contentEl, text, speed = 30, onComplete) {
        let index = 0;
        function appendNext() {
            if (index >= text.length) {
                if (onComplete) onComplete();
                return;
            }
            const char = text.charAt(index);
            if (char === '\n') {
                contentEl.insertAdjacentHTML('beforeend', '<br>');
            } else {
                contentEl.insertAdjacentHTML('beforeend', window.escapeHtml(char));
            }
            index++;
            if (messageContainer) {
                messageContainer.scrollTop = messageContainer.scrollHeight;
            }
            setTimeout(appendNext, speed + Math.random() * 10);
        }
        appendNext();
    }

    // ======================== 发送消息（改造为打字机效果） ========================
    async function sendMessage(userText) {
        if (!isDashboardReady) {
            window.showToast('请退出重进完成新手剧情', 2000);
            return;
        }
        if (!userText.trim()) return;
        if (isSending) {
            window.showToast('正在发送中，请稍候', 1500);
            return;
        }

        const now = new Date();
        addMessageWithDividers('user', userText, now);
        chatInput.value = '';
        chatInput.style.height = 'auto';
        isSending = true;
        sendBtn.disabled = true;
        sendBtn.style.opacity = '0.6';
        chatInput.disabled = true;

        let typingStarted = false;

        const { element: thinkingMsg, startRotation, stopRotation } = createRotatingThinkingMessage();
        messageContainer.appendChild(thinkingMsg);
        messageContainer.scrollTop = messageContainer.scrollHeight;
        startRotation();

        try {
            const response = await window.http({
                method: 'POST',
                url: '/chat/conversation',
                data: { message: userText },
                needAuth: true
            });

            // 移除思考提示
            if (thinkingMsg && thinkingMsg.parentNode) thinkingMsg.remove();
            stopRotation();

            const aiReply = response.reply || '收到了你的消息，但我暂时不知道说什么好～';
            const aiReplyTime = new Date();

            // 创建空的消息气泡用于打字
            const msgEl = document.createElement('div');
            msgEl.className = 'message left';
            const contentEl = document.createElement('div');
            contentEl.className = 'message-content';
            msgEl.appendChild(contentEl);
            msgEl.dataset.timestamp = aiReplyTime.toISOString();

            // 手动插入分割线
            const fragment = document.createDocumentFragment();
            let prevTime = lastRenderedMessageTime;
            if (prevTime) {
                if (!isSameDay(prevTime, aiReplyTime)) {
                    fragment.appendChild(createLongDivider(aiReplyTime));
                }
                if (shouldShowShortDivider(prevTime, aiReplyTime)) {
                    fragment.appendChild(createShortDivider(aiReplyTime));
                }
            } else {
                fragment.appendChild(createLongDivider(aiReplyTime));
                fragment.appendChild(createShortDivider(aiReplyTime));
            }
            fragment.appendChild(msgEl);
            messageContainer.appendChild(fragment);
            messageContainer.scrollTop = messageContainer.scrollHeight;

            // 更新最后消息时间（立刻生效，防止并发错误）
            lastRenderedMessageTime = aiReplyTime;
            typingStarted = true;

            // 启动打字机
            typewriterEffect(contentEl, aiReply, 30, async () => {
                // 打字完成，恢复界面
                isSending = false;
                sendBtn.disabled = false;
                sendBtn.style.opacity = '1';
                chatInput.disabled = false;
                chatInput.focus();

                // 更新状态
                if (response.status_updates) {
                    updateStatusFromBackend(response.status_updates);
                }
                
                await fetchAndRenderSchedules();
            });

        } catch (err) {
            if (thinkingMsg && thinkingMsg.parentNode) thinkingMsg.remove();
            stopRotation();

            let errorMsg = '抱歉，连接出现问题，请稍后再试';
            if (err.status === 401) {
                errorMsg = '登录已过期，请重新登录';
                setTimeout(() => { window.location.href = '/HTML/Index/index.html'; }, 1500);
            } else if (err.message) {
                errorMsg = err.message;
            }
            addMessageWithDividers('assistant', `😥 ${errorMsg}`, new Date());
            window.showToast(errorMsg, 3000);
        } finally {
            if (!typingStarted) {
                // 出错或未启动打字时立即恢复
                isSending = false;
                sendBtn.disabled = false;
                sendBtn.style.opacity = '1';
                chatInput.disabled = false;
                chatInput.focus();
            }
        }
    }

    // ======================== 对话历史分页加载 ========================
    let bottomWelcomeAdded = false;
    let topWelcomeAdded = false;
    let earliestMessageId = null;
    let historyHasMore = true;
    let historyIsLoading = false;
    const historyPageSize = 20;

    async function loadMoreHistory(reset = false) {
        if (historyIsLoading) return;
        if (!reset && !historyHasMore) {
            if (!topWelcomeAdded) {
                addTopWelcomeMessages();
                topWelcomeAdded = true;
            }
            return;
        }

        if (reset) {
            earliestMessageId = null;
            historyHasMore = true;
            messageContainer.innerHTML = '';
            bottomWelcomeAdded = false;
            topWelcomeAdded = false;
            resetTimeTracking();
        }

        historyIsLoading = true;
        try {
            const params = { pageSize: historyPageSize };
            if (!reset && earliestMessageId !== null) {
                params.before_id = earliestMessageId;
            }

            const data = await window.http({
                method: 'GET',
                url: '/chat/history',
                params: params,
                needAuth: true
            });

            const list = data.list || [];
            const hasMore = data.hasMore || false;
            historyHasMore = hasMore;

            if (list.length > 0) {
                const sorted = [...list].reverse();

                if (reset) {
                    renderMessagesWithDividers(sorted, true, hasMore);
                    addBottomWelcomeMessages();
                    bottomWelcomeAdded = true;
                    if (sorted.length > 0) {
                        earliestMessageId = sorted[0].id;
                    }
                } else {
                    const oldScrollHeight = messageContainer.scrollHeight;
                    renderMessagesWithDividers(sorted, false);
                    const newScrollHeight = messageContainer.scrollHeight;
                    messageContainer.scrollTop = newScrollHeight - oldScrollHeight;

                    if (sorted.length > 0) {
                        earliestMessageId = sorted[0].id;
                    }
                }

                if (!hasMore && !topWelcomeAdded) {
                    addTopWelcomeMessages();
                    topWelcomeAdded = true;
                }
            } else {
                if (reset) {
                    addTopWelcomeMessages();
                    topWelcomeAdded = true;
                    addBottomWelcomeMessages();
                    bottomWelcomeAdded = true;
                }
                historyHasMore = false;
            }
        } catch (err) {
            console.error('加载历史失败', err);
            window.showToast('加载对话记录失败', 2000);
        } finally {
            historyIsLoading = false;
        }
    }

    function addBottomWelcomeMessages() {
        if (bottomWelcomeAdded) return;
        addMessageToUI('assistant', '🌱 欢迎回来，你的元气伙伴一直在～');
        // addMessageToUI('assistant', '最近有什么心事，不介意的话和我说说吧！');
        bottomWelcomeAdded = true;
    }

    function addTopWelcomeMessages() {
        if (topWelcomeAdded) return;
        const msg1 = createMessageElement('assistant', '🌱 你好，我是你的元气伙伴小元。让我们一起关注身心状态，每天进步一点点～');
        const msg2 = createMessageElement('assistant', '试着和我聊聊天，生成你的状态报表吧');
        messageContainer.insertBefore(msg2, messageContainer.firstChild);
        messageContainer.insertBefore(msg1, messageContainer.firstChild);
        topWelcomeAdded = true;
    }

    // ======================== 新手引导剧情 ========================
    const storyParagraphs = [
        "总是做着同一个梦。",
        "你在无边的海上漂流，",
        "四周被浓雾层层包裹，看不见来路，也寻不到去向。",
        "心底漫开的，是止不住的慌乱与迷茫。",
        "",
        "直到某一日，雾气渐渐散去，",
        "一座小岛，静静出现在前方。",
        "岛上立着一棵奇特的树，叶片缀着细碎的彩色微光。",
        "",
        "你踏上岛，向着那棵树，一步步，缓缓走近。",
        "走到跟前才发现，那树其实是一间温暖的树屋。",
        "推门而入，屋内整洁安稳，像已等候许久。",
        "",
        "桌案上，一本日记静静躺在那儿。",
        "你轻轻翻开第一页，",
        "而上面，清晰地浮现出你的名字："
    ];

    function typeSentence(sentence) {
        return new Promise((resolve) => {
            const span = document.createElement('div');
            span.style.marginBottom = '8px';
            storyTextDiv.appendChild(span);
            
            let i = 0;
            const plainText = sentence;
            function typing() {
                if (i < plainText.length) {
                    span.textContent += plainText.charAt(i);
                    i++;
                    setTimeout(typing, 90);
                } else {
                    const highlighted = applyKeywordHighlight(span.textContent);
                    span.innerHTML = highlighted;
                    resolve();
                }
            }
            typing();
        });
    }

    function applyKeywordHighlight(text) {
        const keywords = [
            '同一个梦', '无边的海上', '慌乱与迷茫',
            '雾气渐渐散去', '细碎的彩色微光', '缓缓走近',
            '温暖的树屋', '等候许久', '日记', '你的名字'
        ];
        
        let result = text;
        keywords.forEach(kw => {
            const regex = new RegExp(kw, 'g');
            result = result.replace(regex, `<strong>${kw}</strong>`);
        });
        return result;
    }

    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function startStory() {
        storyModal.style.display = 'flex';
        storyTextDiv.innerHTML = '';
        storyFooter.style.display = 'none';
        
        let rgba = 0.8;
        
        for (let i = 0; i < storyParagraphs.length; i++) {
            const p = storyParagraphs[i];
            if (p === "") {
                storyTextDiv.innerHTML += '<br>';
                continue;
            }
            await typeSentence(p);
            await sleep(600);
            storyModal.style.background = `radial-gradient(circle at 30% 30%, rgba(70, 50, 30, ${rgba}), rgba(30, 20, 10, ${rgba + 0.05}))`;
            rgba -= 0.04;
        }
        storyFooter.style.display = 'flex';
        storyNicknameInput.focus();
    }

    async function completeStory() {
        const nickname = storyNicknameInput.value.trim();
        if (!nickname) {
            window.showToast('请为自己取一个昵称', 2000);
            return;
        }
        if (nickname.length < 1 || nickname.length > 15) {
            window.showToast('昵称长度1-15个字符', 2000);
            return;
        }
        try {
            await updateNickname(nickname);
            await markIntroSeen();
            await fetchBaseInfo(true);
            storyModal.style.display = 'none';
            window.showToast(`✨ 欢迎你，${nickname}！元气之旅开始啦`, 3000);
            
            await fetchAndUpdateUserStatus();
            
            isDashboardReady = true;
            addMessageToUI('assistant', '🌱 你好，我是你的元气伙伴小元。让我们一起关注身心状态，每天进步一点点～');
            addMessageToUI('assistant', '试着和我聊聊天，生成你的状态报表吧');
        } catch (err) {
            window.showToast('设置昵称失败: ' + err.message, 3000);
        }
    }

    // ======================== 个人弹窗 ========================
    async function showProfileModal() {
        try {
            const info = await fetchUserInfo();
            profileNicknameSpan.innerText = info.nickname || '未设置';
            profilePhoneSpan.innerText = info.phone;
            profileInviteCodeSpan.innerText = info.invite_code || '无';
            profileAvatar.src = info.avatar || '/static_pic/default_avatar.jpg';
            profileModal.style.display = 'flex';
        } catch (err) {
            window.showToast('获取个人信息失败', 2000);
        }
    }

    function bindAvatarUpload() {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/jpeg,image/png,image/gif,image/webp';
        fileInput.addEventListener('change', async (e) => {
            if (!e.target.files || !e.target.files[0]) return;
            const file = e.target.files[0];
            if (file.size > 5 * 1024 * 1024) {
                window.showToast('头像大小不能超过 5MB', 2000);
                return;
            }
            try {
                const newUrl = await uploadAvatar(file);
                avatarImg.src = newUrl;
                profileAvatar.src = newUrl;
                window.showToast('头像更新成功', 2000);
            } catch (err) {
                window.showToast('头像上传失败: ' + err.message, 3000);
            }
        });
        profileLeft.addEventListener('click', () => fileInput.click());
    }

    const profileExportBtn = document.getElementById('profileExportBtn');

    async function downloadFile(url, defaultFilename = 'vitalis_report.html') {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/HTML/Index/index.html';
            throw new Error('未登录');
        }

        const response = await fetch(url, {
            method: 'GET',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            let errMsg = `下载失败 (${response.status})`;
            try {
                const errData = await response.json();
                errMsg = errData.detail || errMsg;
            } catch {}
            throw new Error(errMsg);
        }

        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = defaultFilename;
        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?(.+)"?/);
            if (match) filename = match[1];
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
    }

    async function handleExportData() {
        try {
            window.showToast('📦 正在准备数据，请稍候...', 2000);
            await downloadFile('/user/export', 'vitalis_report.html');
            window.showToast('✅ 数据导出成功！', 3000);
        } catch (error) {
            window.showToast(`❌ 导出失败: ${error.message}`, 4000);
        }
    }

    function handleLogout() {
        showConfirm('确定要退出登录吗？', () => {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_base_info');
            window.showToast('已退出登录，即将跳转...', 1500);
            setTimeout(() => { window.location.href = '/HTML/Index/index.html'; }, 1500);
        });
    }

    function handleDeleteAccount() {
        showConfirm('⚠️ 注销账号将永久删除您的所有数据，且无法恢复。确定要继续吗？', () => {
            showPasswordModal(async (password) => {
                try {
                    await deleteAccount(password);
                } catch (err) {}
            });
        });
    }

    // ======================== 初始化 ========================
    async function init() {
        if (!localStorage.getItem('access_token')) {
            window.location.href = '/HTML/Index/index.html';
            return;
        }
        const baseInfo = await fetchBaseInfo();
        if (baseInfo) {
            avatarImg.src = baseInfo.avatar;
            if (!baseInfo.has_seen_intro) {
                await startStory();
                storyCompleteBtn.onclick = completeStory;
                return;
            }
        }
        await fetchAndUpdateUserStatus();
        renderStatus();

        await loadMoreHistory(true);

        await fetchAndRenderSchedules();  // 获取并渲染日程

        isDashboardReady = true;
        // 确保页面加载后滚动到顶部
        // window.scrollTo(0, 0);
    }

    function bindEvents() {
        sendBtn.addEventListener('click', () => sendMessage(chatInput.value));
        setDefaultDate();
        bindDateInputFallback();
        if (dateJumpConfirmBtn) {
            dateJumpConfirmBtn.addEventListener('click', fetchAndShowDateHistory);
        }
        if (closeDateHistoryModalBtn) {
            closeDateHistoryModalBtn.addEventListener('click', closeDateHistoryModal);
        }
        if (dateHistoryModal) {
            dateHistoryModal.addEventListener('click', (e) => {
                if (e.target === dateHistoryModal) closeDateHistoryModal();
            });
        }
        if (dateJumpInput) {
            dateJumpInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    fetchAndShowDateHistory();
                }
            });
        }
        logoutIconBtn.addEventListener('click', handleLogout);
        avatarBtn.addEventListener('click', showProfileModal);
        profileClose.addEventListener('click', () => profileModal.style.display = 'none');
        profileLogoutBtn.addEventListener('click', handleDeleteAccount);
        profileModal.addEventListener('click', (e) => {
            if (e.target === profileModal) profileModal.style.display = 'none';
        });
        if (chatInput) {
            chatInput.addEventListener('input', autoResizeTextarea);
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage(chatInput.value);
                }
            });
        }
        (function bindScrollLoad() {
            if (!messageContainer) return;
            messageContainer.addEventListener('scroll', () => {
                if (messageContainer.scrollTop <= 5 && !historyIsLoading && historyHasMore) {
                    loadMoreHistory(false);
                } else if (messageContainer.scrollTop <= 5 && !historyHasMore && !topWelcomeAdded) {
                    addTopWelcomeMessages();
                    topWelcomeAdded = true;
                }
            });
        })();
        if (statsContainer) {
            statsContainer.addEventListener('click', (e) => {
                const statItem = e.target.closest('.stat-item');
                if (!statItem) return;
                const dimension = statItem.getAttribute('data-dimension');
                if (dimension) {
                    showHistoryChart(dimension);
                }
            });
        }
        profileExportBtn.addEventListener('click', () => {
            showConfirm('确定导出个人数据吗？导出文件为 HTML 格式，可离线查看。', handleExportData);
        });
        profileChangePwdBtn.addEventListener('click', showChangePwdModal);
        changePwdCancelBtn.addEventListener('click', closeChangePwdModal);
        changePwdConfirmBtn.addEventListener('click', handleChangePassword);
        changePwdModal.addEventListener('click', (e) => {
            if (e.target === changePwdModal) closeChangePwdModal();
        });
        bindAvatarUpload();

        // 创建聊天区按钮
        createScrollButtons();

        // 最近日程卡片点击：① 刷新日程 ② 滚动到日程全览
        const recentCard = document.getElementById('recentScheduleCard');
        if (recentCard) {
            recentCard.addEventListener('click', async () => {
                await fetchAndRenderSchedules();   // 先拉最新日程
                scrollToScheduleView();
            });
        }

        // “查看更多”按钮
        const viewAllBtn = document.getElementById('viewAllSchedules');
        if (viewAllBtn) {
            viewAllBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await fetchAndRenderSchedules();
                scrollToScheduleView();
            });
        }
        // 回到顶部按钮逻辑
        const backToTopBtn = document.getElementById('backToTopBtn');
        if (backToTopBtn) {
            // 点击滚动到顶部
            backToTopBtn.addEventListener('click', () => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });

            // 监听 body 滚动，判断是否接近底部
            let ticking = false;
            window.addEventListener('scroll', () => {
                if (!ticking) {
                requestAnimationFrame(() => {
                    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    const windowHeight = window.innerHeight;
                    const fullHeight = document.documentElement.scrollHeight;
                    // 距离底部 50px 以内视为到达底部
                    if (scrollTop + windowHeight >= fullHeight - 50) {
                    backToTopBtn.classList.add('show');
                    } else {
                    backToTopBtn.classList.remove('show');
                    }
                    ticking = false;
                });
                ticking = true;
                }
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => { init(); bindEvents(); });
    } else {
        init();
        bindEvents();
    }
})();