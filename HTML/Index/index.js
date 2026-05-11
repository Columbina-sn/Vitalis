// HTML\Index\index.js
(function() {
    // ======================== 背景渐变动画（循环取色版） ========================
    const colorPalette = ["#FFF3E0", "#FFE8CC", "#FFDEB9", "#FFD4A6", "#FCCF9B", "#D4E8E8", "#C2DFE8", "#B0D6E8", "#B8D4F0", "#C8E0F5"];
    const bgDivs = document.querySelectorAll('.bg');
    const divColors = [];

    function initBackground() {
        const layerCount = bgDivs.length;      // 25
        const colorCountPerLayer = 15;
        for (let i = 0; i < layerCount; i++) {
            bgDivs[i].style.top = `${i * window.innerHeight / layerCount}px`;
            bgDivs[i].style.height = `${window.innerHeight / layerCount}px`;
            const colors = [];
            for (let j = 0; j < colorCountPerLayer; j++) {
                const colorIndex = (i + j) % colorPalette.length;
                colors.push(colorPalette[colorIndex]);
            }
            divColors.push(colors);
            bgDivs[i].style.background = `linear-gradient(100deg, ${colors.join(', ')})`;
        }
        window.addEventListener('resize', () => {
            for (let i = 0; i < layerCount; i++) {
                bgDivs[i].style.top = `${i * window.innerHeight / layerCount}px`;
                bgDivs[i].style.height = `${window.innerHeight / layerCount}px`;
            }
        });
    }

    function rotateBackground() {
        const layerCount = bgDivs.length;
        for (let i = 0; i < layerCount; i++) {
            const colors = divColors[i];
            const firstColor = colors.shift();
            colors.push(firstColor);
            bgDivs[i].style.background = `linear-gradient(100deg, ${colors.join(', ')})`;
        }
    }
    setInterval(rotateBackground, 2000);
    initBackground();

    // ======================== Comment 模块 ========================

    // ---------- 1.1 加载评论列表 (GET /comment/list) ----------
    // [DOM 元素] 获取评论列表相关 DOM
    const commentListEl = document.getElementById('commentList');
    const wrapper = document.getElementById('commentListWrapper');
    const loadingEl = document.getElementById('commentLoading');
    const noMoreEl = document.getElementById('commentNoMore');

    // [状态变量] 分页相关
    let nextCursor = null;
    const pageSize = 10;
    let hasMore = true;
    let isLoading = false;

    // [渲染函数] 将评论数据渲染到页面
    function renderComments(comments, reset = false) {
        if (reset) commentListEl.innerHTML = '';
        if (!comments || comments.length === 0) {
            if (reset && nextCursor === null) {
                commentListEl.innerHTML = '<div class="comment-empty">🍃 还没有评论，来做第一个留言的人吧～</div>';
            }
            return;
        }
        if (commentListEl.querySelector('.comment-empty')) commentListEl.innerHTML = '';
        const fragment = document.createDocumentFragment();
        comments.forEach(comment => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'comment-item';

            const content = comment.content || '该评论内容似乎有问题哦';
            const rawTime = comment.created_at || comment.create_time || comment.createdAt || new Date().toISOString();
            const timeStr = window.formatDate(rawTime);

            let userContent = window.escapeHtml(content);
            let adminReply = '';

            // 如果已回复，尝试按 \n【管理员回复】：拆分
            if (comment.replied) {
                const splitter = '\\n\\n\\n';
                const idx = content.indexOf(splitter);
                if (idx !== -1) {
                    userContent = window.escapeHtml(content.substring(0, idx));
                    adminReply = window.escapeHtml(content.substring(idx + splitter.length));
                }
            }

            const adminReplyHtml = adminReply
                ? `<div class="admin-reply-section">
                    <div class="admin-reply-label">✅ 管理员回复：</div>
                    <div class="admin-reply-content">${adminReply}</div>
                </div>`
                : (comment.replied ? '<div class="comment-replied">✅ 管理员已回复</div>' : '');

            itemDiv.innerHTML = `
                <div class="comment-content">${userContent}</div>
                <div class="comment-meta">
                    <span class="comment-time">📅 ${timeStr}</span>
                </div>
                ${adminReplyHtml}
            `;
            fragment.appendChild(itemDiv);
        });
        commentListEl.appendChild(fragment);
    }

    // [调用接口函数] 从服务器加载评论列表
    async function loadComments(reset = false) {
        if (isLoading) return;
        if (!reset && !hasMore) {
            if (noMoreEl) noMoreEl.style.display = 'block';
            return;
        }
        if (reset) {
            nextCursor = null;
            hasMore = true;
            if (noMoreEl) noMoreEl.style.display = 'none';
            commentListEl.innerHTML = '';
        }

        isLoading = true;
        if (loadingEl) loadingEl.style.display = 'block';

        try {
            const params = { pageSize };
            if (!reset && nextCursor) {
                params.cursor_is_long = nextCursor.is_long;
                params.cursor_created_at = nextCursor.created_at;
                params.cursor_id = nextCursor.id;
            }

            const data = await window.http({
                method: 'GET',
                url: '/comment/list',
                params: params,
                needAuth: false
            });

            const commentList = data.list || [];
            nextCursor = data.nextCursor || null;
            hasMore = nextCursor !== null;

            renderComments(commentList, reset);

            if (!hasMore && commentList.length === 0) {
                if (reset) {
                    commentListEl.innerHTML = '<div class="comment-empty">🍃 还没有评论，来做第一个留言的人吧～</div>';
                }
            } else {
                if (!hasMore && noMoreEl) noMoreEl.style.display = 'block';
            }
        } catch (error) {
            console.error('加载评论失败:', error);
            let errMsg = error.message || '加载失败，请稍后重试';
            if (error.status === 429) errMsg = '请求太频繁啦，休息一下';
            window.showToast(`⚠️ ${errMsg}`, 4000);
            if (commentListEl.children.length === 0) {
                commentListEl.innerHTML = `<div class="comment-empty">🍃 加载失败，请刷新页面重试</div>`;
            }
        } finally {
            isLoading = false;
            if (loadingEl) loadingEl.style.display = 'none';
        }
    }

    // [事件绑定函数] 滚动加载更多评论
    function bindScrollListener() {
        if (!wrapper) return;
        wrapper.addEventListener('scroll', () => {
            if (isLoading || !hasMore) return;
            const { scrollTop, clientHeight, scrollHeight } = wrapper;
            if (scrollTop + clientHeight >= scrollHeight - 30) {
                loadComments(false);
            }
        });
    }

    // ---------- 1.2 提交评论 (POST /comment/new-comment) ----------
    // [DOM 元素] 提交评论相关 DOM
    const submitBtn = document.getElementById('submitCommentBtn');
    const contentTextarea = document.getElementById('commentContent');
    const charCountSpan = document.getElementById('charCount');

    // [调用接口函数] 提交评论
    async function submitComment() {
        const content = contentTextarea.value.trim();
        if (!content) {
            window.showToast('✏️ 写点内容再发送吧～', 3000);
            return;
        }
        if (content.length > 500) {
            window.showToast('📏 评论内容不能超过500字', 3000);
            return;
        }
        submitBtn.disabled = true;
        const originalText = submitBtn.textContent;
        submitBtn.textContent = '✍️ 发送中...';

        try {
            await window.http({
                method: 'POST',
                url: '/comment/new-comment',
                data: { content: content },
                needAuth: false
            });
            contentTextarea.value = '';
            updateCharCount();
            await loadComments(true);   // 重新加载列表并置顶
            if (wrapper) wrapper.scrollTop = 0;
            window.showToast('✨ 评论发布成功！', 3000);
        } catch (error) {
            let errMsg = error.message || '发布失败，请重试';
            if (error.status === 429) {
                errMsg = '⏱️ 评论过于频繁，请稍后再试 (每分钟1条，每小时5条)';
            }
            window.showToast(`❌ ${errMsg}`, 4000);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }

    // [辅助函数] 更新字数统计
    function updateCharCount() {
        if (charCountSpan) charCountSpan.textContent = contentTextarea.value.length;
    }

    // [辅助函数] 自动调整输入框高度
    function autoResize() {
        if (!contentTextarea) return;
        contentTextarea.style.height = 'auto';
        const newHeight = contentTextarea.scrollHeight;
        const maxHeight = 132;
        if (newHeight > maxHeight) {
            contentTextarea.style.height = maxHeight + 'px';
            contentTextarea.style.overflowY = 'auto';
        } else {
            contentTextarea.style.height = newHeight + 'px';
            contentTextarea.style.overflowY = 'hidden';
        }
    }

    // [事件绑定] 评论输入框及提交按钮事件
    function bindCommentEvents() {
        if (submitBtn) submitBtn.addEventListener('click', submitComment);
        if (contentTextarea) {
            contentTextarea.addEventListener('input', updateCharCount);
            updateCharCount(); // 初始字数
            contentTextarea.addEventListener('input', autoResize);
        }
    }

    // ======================== Auth 模块 ========================

    // ---------- 2.1 登录/注册选项卡切换 ----------
    // [DOM 元素]
    const loginTab = document.getElementById('loginTab');
    const registerTab = document.getElementById('registerTab');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    // [事件绑定函数] 切换选项卡
    function initAuthTabs() {
        if (!loginTab || !registerTab) return;

        function setActiveTab(active) {
            if (active === 'login') {
                loginTab.classList.add('active');
                registerTab.classList.remove('active');
                loginForm.style.display = 'block';
                registerForm.style.display = 'none';
            } else {
                registerTab.classList.add('active');
                loginTab.classList.remove('active');
                loginForm.style.display = 'none';
                registerForm.style.display = 'block';
            }
        }
        setActiveTab('login');
        loginTab.addEventListener('click', () => setActiveTab('login'));
        registerTab.addEventListener('click', () => setActiveTab('register'));
    }

    // ---------- 2.2 登录 (POST /auth/login + 二级验证) ----------
    // [DOM 元素] 登录表单相关
    const loginBtn = document.getElementById('loginBtn');
    const loginPhone = document.getElementById('loginPhone');
    const loginPassword = document.getElementById('loginPassword');
    const phoneRegex = /^1[3-9]\d{9}$/;

    // [二级验证弹窗] 显示弹窗并处理 POST /auth/admin/second-verify
    function showSecondFactorModal(adminPhone) {
        const modal = document.getElementById('secondFactorModal');
        const passwordInput = document.getElementById('secondPasswordInput');
        const submitBtn = document.getElementById('secondFactorSubmitBtn');
        const cancelBtn = document.getElementById('secondFactorCancelBtn');
        const descEl = modal?.querySelector('.modal-desc');

        if (!modal) return;

        passwordInput.value = '';
        modal.style.display = 'flex';

        let countdown = 30;
        const updateDesc = () => {
            if (descEl) {
                descEl.textContent = `请输入二级密码（${countdown}秒内有效）`;
            }
        };
        updateDesc();
        const timer = setInterval(() => {
            countdown--;
            updateDesc();
            if (countdown <= 0) {
                clearInterval(timer);
                closeModal();
                window.showToast('⏰ 二级验证已超时，请重新登录', 4000);
            }
        }, 1000);

        const closeModal = () => {
            clearInterval(timer);
            modal.style.display = 'none';
            submitBtn.removeEventListener('click', onSubmit);
            cancelBtn.removeEventListener('click', onCancel);
        };

        const onSubmit = async () => {
            const secondPwd = passwordInput.value.trim();
            if (!secondPwd) {
                window.showToast('请输入二级密码', 3000);
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = '验证中...';

            try {
                const response = await fetch('/auth/admin/second-verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        phone: adminPhone,
                        second_password: secondPwd
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.detail || '验证失败');
                }

                const token = result.data?.access_token;
                if (token) {
                    localStorage.setItem('access_token', token);
                    window.showToast('✅ 管理员验证成功，进入后台', 2000);
                    const redirectUrl = result.data?.admin_redirect_url || '/HTML/Admin/admin.html';
                    setTimeout(() => {
                        window.location.href = redirectUrl;
                    }, 2000);
                    closeModal();
                } else {
                    throw new Error('未获取到 token');
                }
            } catch (error) {
                window.showToast(`❌ ${error.message}`, 4000);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '验证';
            }
        };

        const onCancel = () => {
            closeModal();
            window.showToast('已取消二级验证', 2000);
        };

        submitBtn.addEventListener('click', onSubmit);
        cancelBtn.addEventListener('click', onCancel);

        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        passwordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitBtn.click();
            }
        });
    }

    // [调用接口函数] 处理登录
    async function handleLogin() {
        const phone = loginPhone.value.trim();
        const password = loginPassword.value.trim();

        if (!phone) { window.showToast('📱 请输入手机号', 3000); return; }
        if (!phoneRegex.test(phone)) { window.showToast('❌ 手机号格式不正确', 3000); return; }
        if (!password) { window.showToast('🔒 请输入密码', 3000); return; }

        loginBtn.disabled = true;
        const originalText = loginBtn.textContent;
        loginBtn.textContent = '登录中...';

        try {
            const data = await window.http({
                method: 'POST',
                url: '/auth/login',
                data: { phone, password },
                needAuth: false
            });

            // 检查是否需要二级验证
            if (data.require_second_factor) {
                loginBtn.disabled = false;
                loginBtn.textContent = originalText;
                showSecondFactorModal(data.phone);
                return;
            }

            const token = data?.access_token;
            const loginAlert = data?.login_alert;   // 新增：读取异地登录提醒

            if (token) {
                localStorage.setItem('access_token', token);

                if (loginAlert) {
                    // 有异地提醒时，先展示 6 秒，然后再弹出成功提示，最后延迟 2 秒跳转
                    window.showToast(loginAlert, 6000);
                    setTimeout(() => {
                        window.showToast('🎉 登录成功，即将进入元气岛', 2000);
                        setTimeout(() => {
                            window.location.href = '/HTML/Dashboard/dashboard.html';
                        }, 2000);
                    }, 6000);
                } else {
                    // 无异地提醒，正常流程
                    window.showToast('🎉 登录成功，即将进入元气岛', 2000);
                    setTimeout(() => {
                        window.location.href = '/HTML/Dashboard/dashboard.html';
                    }, 2000);
                }
            }
        } catch (error) {
            let errMsg = error.message || '登录失败，请重试';
            if (error.original?.detail) errMsg = error.original.detail;
            window.showToast(`❌ ${errMsg}`, 4000);
        } finally {
            loginBtn.disabled = false;
            loginBtn.textContent = originalText;
        }
    }

    // [事件绑定] 登录按钮
    function bindLoginEvents() {
        if (loginBtn) loginBtn.addEventListener('click', handleLogin);
    }

    // ---------- 2.3 注册 (POST /auth/register) ----------
    // [DOM 元素] 注册表单相关
    const registerBtn = document.getElementById('registerBtn');
    const registerPhone = document.getElementById('registerPhone');
    const registerPassword = document.getElementById('registerPassword');
    const registerConfirmPassword = document.getElementById('registerConfirmPassword');
    const registerInviteCode = document.getElementById('registerInviteCode');

    // [调用接口函数] 处理注册
    async function handleRegister() {
        const phone = registerPhone.value.trim();
        const password = registerPassword.value.trim();
        const confirmPwd = registerConfirmPassword.value.trim();
        const inviteCode = registerInviteCode.value.trim();

        if (!phone) { window.showToast('📱 请输入手机号', 3000); return; }
        if (!phoneRegex.test(phone)) { window.showToast('❌ 手机号格式不正确', 3000); return; }
        if (!password) { window.showToast('🔒 请输入密码', 3000); return; }
        if (password.length < 6 || password.length > 20) { window.showToast('🔐 密码长度需为 6-20 位', 3000); return; }
        if (password !== confirmPwd) { window.showToast('⚠️ 两次输入的密码不一致', 3000); return; }
        if (!inviteCode) { window.showToast('🎫 请输入邀请码', 3000); return; }
        if (inviteCode.length !== 8) { window.showToast('🎫 邀请码应为 8 位字符', 3000); return; }

        registerBtn.disabled = true;
        const originalText = registerBtn.textContent;
        registerBtn.textContent = '注册中...';

        try {
            const data = await window.http({
                method: 'POST',
                url: '/auth/register',
                data: { phone, password, invite_code: inviteCode },
                needAuth: false
            });
            const token = data?.access_token;
            if (token) {
                localStorage.setItem('access_token', token);
                window.showToast('✨ 注册成功，即将进入元气岛', 2000);
                setTimeout(() => {
                    window.location.href = '/HTML/Dashboard/dashboard.html';
                }, 1500);
            } else {
                throw new Error('注册响应缺少 token');
            }
        } catch (error) {
            let errMsg = error.message || '注册失败，请重试';
            if (error.original?.detail) errMsg = error.original.detail;
            window.showToast(`❌ ${errMsg}`, 4000);
        } finally {
            registerBtn.disabled = false;
            registerBtn.textContent = originalText;
        }
    }

    // [事件绑定] 注册按钮
    function bindRegisterEvents() {
        if (registerBtn) registerBtn.addEventListener('click', handleRegister);
    }

    // ======================== 全局初始化 ========================
    async function init() {
        // 清空可能残留的非管理员 token，确保干净登录
        localStorage.removeItem('user_base_info');
        localStorage.removeItem('access_token');

        // 应用主题：优先从 localStorage 读取，否则默认跟随系统
        window.initTheme();

        // 初始化各个模块
        initAuthTabs();
        bindCommentEvents();
        bindScrollListener();
        bindLoginEvents();
        bindRegisterEvents();

        // 首次加载评论列表
        await loadComments(true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();