// HTML\Admin\admin.js
// 管理后台核心脚本（传统分页版，乐观更新 + 手动刷新）
// 重构版：按接口/功能模块拆分，保持全部原始逻辑不变
(function(){
  "use strict";

  // ======================== 1. 背景动画 ========================
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

  // ======================== 2. DOM 元素 ========================
  const table = document.getElementById('adminDataTable');
  const prevBtn = document.getElementById('prevPageBtn');
  const nextBtn = document.getElementById('nextPageBtn');
  const pageInfoSpan = document.getElementById('pageInfo');
  const pageCountInfo = document.getElementById('pageCountInfo');
  const pageJumpInput = document.getElementById('pageJumpInput');
  const pageJumpBtn = document.getElementById('pageJumpBtn');
  const tabBtns = document.querySelectorAll('.tab-btn');
  const refreshBtn = document.getElementById('refreshDataBtn');

  // 右侧统计卡片
  const statTotalUsers = document.getElementById('statTotalUsers');
  const statTodayConv = document.getElementById('statTodayConversations');
  const statTotalComments = document.getElementById('statTotalComments');
  const statValidInvites = document.getElementById('statValidInvites');

  // 操作区
  const inviteCountInput = document.getElementById('inviteCount');
  const inviteExpiryDaysInput = document.getElementById('inviteExpiryDays');
  const generateInvitesBtn = document.getElementById('generateInvitesBtn');
  const toggleAdminLoginBtn = document.getElementById('toggleAdminLoginBtn');
  const queryLogsBtn = document.getElementById('queryLogsBtn');
  const logStartDate = document.getElementById('logStartDate');
  const logEndDate = document.getElementById('logEndDate');
  const inviteResultList = document.getElementById('inviteResultList');
  const triggerDailySummaryBtn = document.getElementById('triggerDailySummaryBtn');
  const triggerCleanupBtn = document.getElementById('triggerCleanupBtn');

  // 模态框
  const adminLogsModal = document.getElementById('adminLogsModal');
  const editModal = document.getElementById('editModal');
  const closeAdminLogsModalBtn = document.getElementById('closeAdminLogsModalBtn');
  const adminLogsMessageList = document.getElementById('adminLogsMessageList');
  const adminLogsLoadingMsg = document.getElementById('adminLogsLoadingMsg');
  const adminLogsNoDataMsg = document.getElementById('adminLogsNoDataMsg');
  const adminLogsDateRangeText = document.getElementById('adminLogsDateRangeText');
  const customConfirm = document.getElementById('customConfirm');
  const confirmMessage = document.getElementById('confirmMessage');
  const confirmYesBtn = document.getElementById('confirmYesBtn');
  const confirmNoBtn = document.getElementById('confirmNoBtn');
  const dailySummaryStatusText = document.getElementById('dailySummaryStatusText');

  // 退出
  const adminLogoutBtn = document.getElementById('adminLogoutBtn');

  // ======================== 3. 全局状态 ========================
  let currentTab = 'users';
  let currentPage = 1;
  let totalPages = 1;
  const PAGE_SIZE = 20;
  let currentDataList = [];          // 当前页全部数据
  let currentTotal = 0;             // 当前标签页总记录数（供乐观更新使用）
  let loadDataSeq = 0;              // 防止异步竞态

  // 日志弹窗游标状态
  let logsCursor = null;
  let logsHasMore = true;
  let logsIsLoading = false;
  let logsStartDate = null;
  let logsEndDate = null;

  // 防抖标志
  let isDeleting = false;
  let isSaving = false;

  // ======================== 4. 工具函数 ========================
  function formatDateTime(isoString) {
    if (!isoString) return '-';
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    const year = d.getFullYear();
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const hours = String(d.getHours()).padStart(2,'0');
    const mins = String(d.getMinutes()).padStart(2,'0');
    const secs = String(d.getSeconds()).padStart(2,'0');
    const now = new Date();
    if (year === now.getFullYear()) {
        return `${month}月${day}日 ${hours}:${mins}:${secs}`;
    } else {
        return `${year}年${month}月${day}日 ${hours}:${mins}:${secs}`;
    }
  }

  function maskPhone(phone) {
    if (phone && phone.length === 11) {
      return phone.substring(0,3) + '****' + phone.substring(7);
    }
    return phone || '';
  }

  function actionButtonsHtml() {
    return `<span class="action-icons">
      <i class="fas fa-pen action-icon" title="编辑"></i>
      <i class="fas fa-trash-alt action-icon" title="删除"></i>
    </span>`;
  }

  function updatePaginationInfo() {
    totalPages = Math.ceil(currentTotal / PAGE_SIZE) || 1;
    pageInfoSpan.textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页`;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
    pageJumpInput.value = '';
    pageJumpInput.max = totalPages;
  }

  // ======================== 5. 统计数据模块 ========================
  // ---------- 5.1 获取统计数据 (GET /admin/stats) ----------
  async function fetchStats() {
    try {
      const stats = await http({ method: 'GET', url: '/admin/stats', needAuth: true });
      statTotalUsers.textContent = stats.total_users ?? '-';
      statTodayConv.textContent = stats.today_conversations ?? '-';
      statTotalComments.textContent = stats.total_comments ?? '-';
      statValidInvites.textContent = stats.active_invite_codes ?? '-';
    } catch (error) {
      statTotalUsers.textContent = '错误';
      statTodayConv.textContent = '错误';
      statTotalComments.textContent = '错误';
      statValidInvites.textContent = '错误';
      showToast('获取统计数据失败');
    }
  }

  // ======================== 6. 用户管理模块 ========================
  // ---------- 6.1 获取用户列表 (GET /admin/users) ----------
  async function loadUsers() {
    return loadDataForTab('users');
  }

  // ---------- 6.2 编辑用户 (PUT /admin/users/:id) ----------
  async function updateUser(id, data) {
    await http({ method: 'PUT', url: `/admin/users/${id}`, data, needAuth: true });
  }

  // ---------- 6.3 删除用户 (DELETE /admin/users/:id) ----------
  async function deleteUser(id) {
    await http({ method: 'DELETE', url: `/admin/users/${id}`, needAuth: true });
  }

  // ======================== 7. 评论管理模块 ========================
  // ---------- 7.1 获取评论列表 (GET /admin/comments) ----------
  async function loadComments() {
    return loadDataForTab('comments');
  }

  // ---------- 7.2 编辑评论 (PUT /admin/comments/:id) ----------
  async function updateComment(id, data) {
    await http({ method: 'PUT', url: `/admin/comments/${id}`, data, needAuth: true });
  }

  // ---------- 7.3 删除评论 (DELETE /admin/comments/:id) ----------
  async function deleteComment(id) {
    await http({ method: 'DELETE', url: `/admin/comments/${id}`, needAuth: true });
  }

  // ======================== 8. 邀请码管理模块 ========================
  // ---------- 8.1 获取邀请码列表 (GET /admin/invite-codes) ----------
  async function loadInvites() {
    return loadDataForTab('invites');
  }

  // ---------- 8.2 编辑邀请码 (PUT /admin/invite-codes/:id) ----------
  async function updateInviteCode(id, data) {
    await http({ method: 'PUT', url: `/admin/invite-codes/${id}`, data, needAuth: true });
  }

  // ---------- 8.3 删除邀请码 (DELETE /admin/invite-codes/:id) ----------
  async function deleteInviteCode(id) {
    await http({ method: 'DELETE', url: `/admin/invite-codes/${id}`, needAuth: true });
  }

  // ---------- 8.4 批量生成邀请码 (POST /admin/invite-codes/batch) ----------
  async function generateInvites() {
    const countInput = inviteCountInput;
    const daysInput = inviteExpiryDaysInput;
    let count = parseInt(countInput.value, 10);
    let days = parseInt(daysInput.value, 10);
    if (isNaN(count) || count < 1) count = 1;
    if (count > 100) count = 100;
    countInput.value = count;
    if (isNaN(days) || days < 1) days = 1;
    if (days > 7) days = 7;
    daysInput.value = days;
    try {
      const response = await http({
        method: 'POST',
        url: '/admin/invite-codes/batch',
        data: { count, expiry_days: days },
        needAuth: true
      });
      renderInviteCodes(response.codes, response.expiry_time);
      showToast(`成功生成 ${response.codes.length} 个邀请码`);
      // 生成后重新拉取统计数据，保证数字准确
      await fetchStats();
    } catch (error) {
      showToast(error.message || '生成邀请码失败');
    }
  }

  function renderInviteCodes(codes, expiryTime) {
    if (!inviteResultList) return;
    inviteResultList.innerHTML = '';
    if (!codes || codes.length === 0) {
      inviteResultList.innerHTML = '<div style="color:#a5835e;text-align:center;">暂无生成的邀请码</div>';
      return;
    }
    codes.forEach(code => {
      const itemDiv = document.createElement('div');
      itemDiv.className = 'invite-code-item';
      const codeSpan = document.createElement('span');
      codeSpan.textContent = code;
      codeSpan.style.fontFamily = 'monospace';
      codeSpan.style.fontWeight = '600';
      const copyIcon = document.createElement('i');
      copyIcon.className = 'fas fa-copy copy-invite';
      copyIcon.title = '点击复制';
      copyIcon.addEventListener('click', () => copyInviteCode(code));
      itemDiv.appendChild(codeSpan);
      itemDiv.appendChild(copyIcon);
      inviteResultList.appendChild(itemDiv);
    });
    const expiryNote = document.createElement('div');
    expiryNote.style.cssText = 'font-size:0.75rem;color:#a5835e;margin-top:8px;text-align:right;';
    expiryNote.textContent = `过期时间：${formatDate(expiryTime)}`;
    inviteResultList.appendChild(expiryNote);
  }

  async function copyInviteCode(code) {
    try {
      await navigator.clipboard.writeText(code);
      showToast(`邀请码 ${code} 已复制`, 2000);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = code;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast(`邀请码 ${code} 已复制`, 2000);
    }
  }

  // ======================== 9. 操作日志模块 ========================
  // ---------- 9.1 获取操作日志列表 (GET /admin/logs-all) ----------
  async function loadLogs() {
    return loadDataForTab('logs');
  }

  // ---------- 9.2 删除单条操作日志 (DELETE /admin/logs/:id) ----------
  async function deleteLog(id) {
    await http({ method: 'DELETE', url: `/admin/logs/${id}`, needAuth: true });
  }

  // ---------- 9.3 右侧操作日志查询弹窗 (GET /admin/logs) ----------
  function closeAdminLogsModal() {
    adminLogsModal.style.display = 'none';
    adminLogsMessageList.innerHTML = '';
    adminLogsNoDataMsg.style.display = 'none';
    adminLogsLoadingMsg.style.display = 'none';
    logsCursor = null;
    logsHasMore = true;
    logsIsLoading = false;
  }

  async function queryAdminLogs() {
    if (logStartDate.value > logEndDate.value) {
      showToast('开始日期不能大于结束日期');
      return;
    }
    logsStartDate = logStartDate.value;
    logsEndDate = logEndDate.value;
    if (!logsStartDate || !logsEndDate) {
      showToast('请选择日期范围');
      return;
    }
    adminLogsDateRangeText.textContent = `${logsStartDate} ~ ${logsEndDate}`;
    adminLogsModal.style.display = 'flex';
    adminLogsMessageList.innerHTML = '';
    adminLogsNoDataMsg.style.display = 'none';
    adminLogsLoadingMsg.style.display = 'flex';
    logsCursor = null;
    logsHasMore = true;
    await loadAdminLogs(true);
  }

  async function loadAdminLogs(reset = false) {
    if (logsIsLoading) return;
    if (!reset && !logsHasMore) return;
    logsIsLoading = true;
    adminLogsLoadingMsg.style.display = 'flex';
    adminLogsNoDataMsg.style.display = 'none';
    try {
      const params = { start_date: logsStartDate, end_date: logsEndDate, page_size: 20 };
      if (!reset && logsCursor) {
        params.cursor_created_at = logsCursor.created_at;
        params.cursor_id = logsCursor.id;
      }
      const data = await http({ method: 'GET', url: '/admin/logs', params, needAuth: true });
      const list = data.list || [];
      const nextCursor = data.next_cursor || null;
      logsHasMore = !!nextCursor;
      logsCursor = nextCursor;
      renderAdminLogs(list, !reset);
      if (list.length === 0 && reset) adminLogsNoDataMsg.style.display = 'block';
    } catch (err) {
      showToast('加载日志失败: ' + err.message);
      if (reset) adminLogsNoDataMsg.style.display = 'block';
    } finally {
      logsIsLoading = false;
      adminLogsLoadingMsg.style.display = 'none';
    }
  }

  function renderAdminLogs(logs, append = false) {
    if (!append) adminLogsMessageList.innerHTML = '';
    if (!logs || logs.length === 0) return;
    const fragment = document.createDocumentFragment();
    logs.forEach(log => {
      const item = document.createElement('div');
      item.className = 'admin-log-item';
      const headerDiv = document.createElement('div');
      headerDiv.style.display = 'flex';
      headerDiv.style.justifyContent = 'space-between';
      headerDiv.style.marginBottom = '8px';
      const phone = log.admin_phone || '未知';
      const maskedPhone = phone.length === 11 ? phone.substring(0,3) + '****' + phone.substring(7) : '***';
      headerDiv.innerHTML = `<span style="font-weight:600;color:#7a4e2e;"><i class="fas fa-user-shield" style="margin-right:4px;color:#b87a48;"></i>${maskedPhone}</span><span style="background:#f0dfbc;padding:2px 12px;border-radius:30px;font-size:0.75rem;font-weight:600;color:#7a4e2e;">${log.action_type}</span>`;
      const timeDiv = document.createElement('div');
      timeDiv.className = 'admin-log-time';
      timeDiv.innerHTML = `<i class="far fa-clock"></i> ${formatDateTime(log.created_at)}`;
      const remarkDiv = document.createElement('div');
      remarkDiv.className = 'admin-log-remark';
      remarkDiv.textContent = log.remark || '无备注';
      item.appendChild(headerDiv);
      item.appendChild(timeDiv);
      item.appendChild(remarkDiv);
      fragment.appendChild(item);
    });
    adminLogsMessageList.appendChild(fragment);
  }

  function bindAdminLogsScroll() {
    adminLogsMessageList.addEventListener('scroll', () => {
      const container = adminLogsMessageList;
      const scrollBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      if (scrollBottom < 30 && !logsIsLoading && logsHasMore) {
        loadAdminLogs(false);
      }
    });
  }

  // ======================== 10. 安全控制模块 ========================
  // ---------- 10.1 关闭管理员登录入口 (POST /admin/system-config/disable) ----------
  async function toggleAdminLogin() {
    const btn = toggleAdminLoginBtn;
    if (!btn || btn.disabled) return;
    showConfirm('⚠️ 确定要关闭管理员登录入口吗？', async () => {
      try {
        await http({
          method: 'POST',
          url: '/admin/system-config/disable',
          needAuth: true
        });
        showToast('管理员登录入口已关闭，即将退出...', 2500);
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-lock"></i> 已关闭';
        btn.style.opacity = '0.6';
        btn.style.cursor = 'not-allowed';
        setTimeout(() => {
          localStorage.removeItem('access_token');
          window.location.href = '/HTML/Index/index.html';
        }, 2500);
      } catch (error) {
        showToast('操作失败：' + error.message, 3000);
      }
    });
  }

  // ======================== 11a. 每日摘要模块 ========================
  // ---------- 11.1 查询今日是否已触发 (GET /admin/daily-summary/status) ----------
  async function checkDailySummaryStatus() {
      try {
          const data = await window.http({ method: 'GET', url: '/admin/daily-summary/status', needAuth: true });
          if (data.alreadyTriggered) {
              triggerDailySummaryBtn.disabled = true;
              triggerDailySummaryBtn.style.opacity = '0.6';
              dailySummaryStatusText.textContent = '📅 今日已执行';
          } else {
              triggerDailySummaryBtn.disabled = false;
              triggerDailySummaryBtn.style.opacity = '1';
              dailySummaryStatusText.textContent = '';
          }
      } catch (e) {
          // 读取失败不影响，按钮保持可用
      }
  }

  // ---------- 11.2 手动触发每日摘要生成 (POST /admin/daily-summary/trigger) ----------
  async function triggerDailySummary() {
    if (triggerDailySummaryBtn.disabled) return;
    try {
        await window.http({ method: 'POST', url: '/admin/daily-summary/trigger', needAuth: true });
        window.showToast('每日摘要生成已启动');
        triggerDailySummaryBtn.disabled = true;
        triggerDailySummaryBtn.style.opacity = '0.6';
        dailySummaryStatusText.textContent = '📅 今日已执行';
    } catch (err) {
        if (err.message.includes('已经手动触发过')) {
            triggerDailySummaryBtn.disabled = true;
            triggerDailySummaryBtn.style.opacity = '0.6';
            dailySummaryStatusText.textContent = '📅 今日已执行';
        } else {
            window.showToast('触发失败：' + err.message);
        }
    }
  }

  // ======================== 11b. 数据清理模块 ========================
  // ---------- 查询今日是否已触发清理 (GET /admin/cleanup/status) ----------
  async function checkCleanupStatus() {
      try {
          const data = await window.http({ method: 'GET', url: '/admin/cleanup/status', needAuth: true });
          if (data.alreadyTriggered) {
              triggerCleanupBtn.disabled = true;
              triggerCleanupBtn.style.opacity = '0.6';
              cleanupStatusText.textContent = '🧹 今日已执行';
          } else {
              triggerCleanupBtn.disabled = false;
              triggerCleanupBtn.style.opacity = '1';
              cleanupStatusText.textContent = '';
          }
      } catch (e) {
          // 忽略
      }
  }

  // ---------- 手动触发清理 (POST /admin/cleanup/trigger) ----------
  async function triggerCleanup() {
      if (triggerCleanupBtn.disabled) return;
      showConfirm('确定要执行数据清理吗？这将永久删除已过冷却期的用户和评论。', async () => {
          try {
              await window.http({ method: 'POST', url: '/admin/cleanup/trigger', needAuth: true });
              window.showToast('数据清理已启动');
              triggerCleanupBtn.disabled = true;
              triggerCleanupBtn.style.opacity = '0.6';
              cleanupStatusText.textContent = '🧹 今日已执行';
              // 清理后刷新统计数据
              await fetchStats();
          } catch (err) {
              if (err.message.includes('已经触发过')) {
                  triggerCleanupBtn.disabled = true;
                  triggerCleanupBtn.style.opacity = '0.6';
                  cleanupStatusText.textContent = '🧹 今日已执行';
              } else {
                  window.showToast('清理失败：' + err.message);
              }
          }
      });
  }

  // ======================== 12. 通用数据加载与表格渲染 ========================
  // ---------- 12.1 标签页切换与分页 ----------
  async function switchTab(tab) {
    currentTab = tab;
    currentPage = 1;
    tabBtns.forEach(b => b.classList.remove('active'));
    document.querySelector(`.tab-btn[data-tab="${tab}"]`)?.classList.add('active');
    await loadData();
  }

  async function loadDataForTab(tab) {
    let url = '';
    switch (tab) {
      case 'users': url = '/admin/users'; break;
      case 'comments': url = '/admin/comments'; break;
      case 'invites': url = '/admin/invite-codes'; break;
      case 'logs': url = '/admin/logs-all'; break;
      case 'deleted_users': url = '/admin/users/deleted'; break;
      case 'deleted_comments': url = '/admin/comments/deleted'; break;
      default: return;
    }
    return await http({
      method: 'GET',
      url,
      params: { page: currentPage, page_size: PAGE_SIZE },
      needAuth: true
    });
  }

  async function loadData() {
    const seq = ++loadDataSeq;
    try {
      const data = await loadDataForTab(currentTab);
      if (seq !== loadDataSeq) return;

      const list = data.list || [];
      currentTotal = data.total || 0;
      currentDataList = list;
      
      if (list.length === 0 && currentPage > 1) {
        currentPage--;
        return loadData();
      }
      
      renderTable(list, currentTotal);
      updatePaginationInfo();
    } catch (err) {
      if (seq !== loadDataSeq) return;
      showToast(`加载失败: ${err.message}`);
      currentDataList = [];
      currentTotal = 0;
      renderTable([], 0);
      updatePaginationInfo();
    }
  }

  function goToPage(page) {
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    loadData();
  }

  // ---------- 12.2 表格渲染 ----------
  function renderTable(dataList, total) {
    currentDataList = dataList;
    table.innerHTML = '';

    const configs = {
      users: {
          headers: ['手机号', '昵称', '邀请码', '注册时间', '心理和谐', '对话数', '登录状态', '操作'],
          widths: ['15%', '15%', '12%', '17%', '9%', '8%', '9%', '8%'],
          hasActions: true,
          renderRow: (item) => [
              `<span class="phone-toggle" data-full="${escapeHtml(item.phone)}">${maskPhone(item.phone)}</span>`,
              escapeHtml(item.nickname || ''),
              item.invite_code || '',
              formatDate(item.created_at),
              item.psychological_harmony_index,
              item.conversation_count,
              item.can_login 
                  ? '<span class="status-allowed">允许</span>' 
                  : '<span class="status-banned">禁止</span>',
              actionButtonsHtml()
          ]
      },
      comments: {
        headers: ['ID', '内容', 'IP', '时间', '已回复', '操作'],
        widths: ['12%', '42%', '15%', '15%', '8%', '8%'],
        hasActions: true,
        renderRow: (item) => [
          item.id,
          escapeHtml(item.content),
          item.ip_address,
          formatDateTime(item.created_at),
          item.replied ? '是' : '否',
          actionButtonsHtml()
        ]
      },
      invites: {
          headers: ['ID', '邀请码', '过期时间', '操作'],
          widths: ['10%', '36%', '46%', '8%'],
          hasActions: true,
          renderRow: (item) => {
              const expired = new Date(item.expiry_time) < new Date();
              const timeDisplay = expired
                  ? '<span style="color: #e88; font-weight: 500;">已过期</span>'
                  : formatDateTime(item.expiry_time);
              return [
                  item.id,
                  escapeHtml(item.code),
                  timeDisplay,
                  `<span class="action-icons"><i class="fas fa-pen action-icon" title="编辑"></i><i class="fas fa-trash-alt action-icon" title="删除"></i></span>`
              ];
          }
      },
      logs: {
          headers: ['手机号', '操作类型', '备注', '时间', '操作'],
          widths: ['12%', '22%', '43%', '15%', '8%'],
          hasActions: true,
          renderRow: (item) => [
              `<span class="phone-toggle" data-full="${escapeHtml(item.admin_phone)}">${maskPhone(item.admin_phone)}</span>`,
              item.action_type,
              escapeHtml(item.remark || ''),
              formatDateTime(item.created_at),
              `<span class="action-icons"><i class="fas fa-trash-alt action-icon" title="删除"></i></span>`
          ]
      },
      deleted_users: {
          headers: ['手机号', '昵称', '邀请码', '注册时间', '心理和谐', '对话数', '登录状态', '操作'],
          widths: ['15%', '15%', '12%', '17%', '9%', '8%', '9%', '8%'],
          hasActions: true,
          renderRow: (item) => [
              `<span class="phone-toggle" data-full="${escapeHtml(item.phone)}">${maskPhone(item.phone)}</span>`,
              escapeHtml(item.nickname || ''),
              item.invite_code || '',
              formatDate(item.created_at),
              item.psychological_harmony_index,
              item.conversation_count,
              item.can_login 
                  ? '<span class="status-allowed">允许</span>' 
                  : '<span class="status-banned">禁止</span>',
              `<span class="action-icons"><i class="fas fa-undo action-icon" title="还原"></i></span>` // 仅还原
          ]
      },
      deleted_comments: {
          headers: ['ID', '内容', 'IP', '时间', '已回复', '操作'],
          widths: ['12%', '42%', '15%', '15%', '8%', '8%'],
          hasActions: true,
          renderRow: (item) => [
              item.id,
              escapeHtml(item.content),
              item.ip_address,
              formatDateTime(item.created_at),
              item.replied ? '是' : '否',
              `<span class="action-icons"><i class="fas fa-undo action-icon" title="还原"></i></span>` // 仅还原
          ]
      }
    };

    const config = configs[currentTab];
    if (!config) return;

    const colgroup = document.createElement('colgroup');
    config.widths.forEach(w => {
      const col = document.createElement('col');
      col.style.width = w;
      colgroup.appendChild(col);
    });
    table.appendChild(colgroup);

    const thead = document.createElement('thead');
    const tr = document.createElement('tr');
    config.headers.forEach(h => {
      const th = document.createElement('th');
      th.textContent = h;
      tr.appendChild(th);
    });
    thead.appendChild(tr);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    if (!dataList || dataList.length === 0) {
      const colspan = config.headers.length;
      const emptyTr = document.createElement('tr');
      const emptyTd = document.createElement('td');
      emptyTd.colSpan = colspan;
      emptyTd.style.textAlign = 'center';
      emptyTd.style.padding = '30px';
      emptyTd.style.color = '#a5835e';
      emptyTd.textContent = '暂无数据';
      emptyTr.appendChild(emptyTd);
      tbody.appendChild(emptyTr);
    } else {
      dataList.forEach(item => {
        const row = tbody.insertRow();
        row.dataset.recordId = item.id;
        const values = config.renderRow(item);
        values.forEach((v, idx) => {
          const td = row.insertCell();
          td.innerHTML = v;
        });
      });
    }
    table.appendChild(tbody);
    pageCountInfo.textContent = total < 0 ? '共 … 条' : `共 ${total} 条`;
  }

  // ======================== 13. 编辑与删除通用逻辑 ========================
  // ---------- 13.1 打开编辑模态框 ----------
  function openEditModal(item) {
      document.getElementById('editUserFields').style.display = 'none';
      document.getElementById('editCommentFields').style.display = 'none';
      document.getElementById('editInviteFields').style.display = 'none';
      delete editModal.dataset.editId;

      if (currentTab === 'users') {
          document.getElementById('editUserFields').style.display = 'block';
          document.getElementById('editUserPhone').value = item.phone || '';
          document.getElementById('editUserNickname').value = item.nickname || '';
          document.getElementById('editUserCanLogin').checked = !!item.can_login;
          editModal.dataset.editType = 'users';
          editModal.dataset.editId = item.id;
      } else if (currentTab === 'comments') {
          document.getElementById('editCommentFields').style.display = 'block';
          document.getElementById('editCommentContent').value = item.content || '';
          document.getElementById('editCommentReplied').checked = !!item.replied;
          editModal.dataset.editType = 'comments';
          editModal.dataset.editId = item.id;
      } else if (currentTab === 'invites') {
          document.getElementById('editInviteFields').style.display = 'block';
          document.getElementById('editInviteCode').value = item.code || '';
          const d = new Date(item.expiry_time);
          document.getElementById('editInviteExpiry').value = d.toISOString().slice(0,16);
          editModal.dataset.editType = 'invites';
          editModal.dataset.editId = item.id;
      }

      document.getElementById('editModal').style.display = 'flex';
  }

  // ---------- 13.2 删除操作 ----------
  function handleDelete(item) {
      if (isDeleting) {
          showToast('删除操作正在进行中，请稍后', 1500);
          return;
      }
      let message, url;
      switch (currentTab) {
          case 'users':
              message = `确定要删除用户 ${maskPhone(item.phone)} 吗？此操作将永久删除该用户及其所有数据！`;
              url = `/admin/users/${item.id}`;
              break;
          case 'comments':
              message = `确定要删除评论 (ID: ${item.id}) 吗？`;
              url = `/admin/comments/${item.id}`;
              break;
          case 'invites':
              message = `确定要删除邀请码 ${item.code} 吗？`;
              url = `/admin/invite-codes/${item.id}`;
              break;
          case 'logs':
              message = `确定要删除该条操作日志 (ID: ${item.id}) 吗？`;
              url = `/admin/logs/${item.id}`;
              break;
          default:
              return;
      }

      showConfirm(message, async () => {
          if (isDeleting) return;
          isDeleting = true;

          try {
              await http({ method: 'DELETE', url, needAuth: true });
              showToast('删除成功');

              // 乐观更新本地列表数据
              const idx = currentDataList.findIndex(d => d.id == item.id);
              if (idx !== -1) {
                  currentDataList.splice(idx, 1);
                  currentTotal = Math.max(0, currentTotal - 1);
              }

              if (currentDataList.length === 0 && currentPage > 1) {
                  currentPage--;
                  await loadData();
              } else {
                  renderTable(currentDataList, currentTotal);
                  updatePaginationInfo();
              }

              // 删除后重新获取统计数据
              await fetchStats();
          } catch (err) {
              showToast('删除失败: ' + err.message);
          } finally {
              isDeleting = false;
          }
      });
  }

  // ---------- 13.3 编辑保存处理 ----------
  async function handleEditSave() {
    if (isSaving) return;
    const type = editModal.dataset.editType;
    const id = editModal.dataset.editId;
    if (!type || !id) return;

    let data, updatedItem = null;

    if (type === 'users') {
        data = {
            phone: document.getElementById('editUserPhone').value,
            nickname: document.getElementById('editUserNickname').value,
            can_login: document.getElementById('editUserCanLogin').checked
        };
        const item = currentDataList.find(d => d.id == id);
        if (item) updatedItem = { ...item, ...data };
    } else if (type === 'comments') {
        data = {
            content: document.getElementById('editCommentContent').value,
            replied: document.getElementById('editCommentReplied').checked
        };
        const item = currentDataList.find(d => d.id == id);
        if (item) updatedItem = { ...item, ...data };
    } else if (type === 'invites') {
        data = {
            code: document.getElementById('editInviteCode').value,
            expiry_time: new Date(document.getElementById('editInviteExpiry').value).toISOString()
        };
        const item = currentDataList.find(d => d.id == id);
        if (item) updatedItem = { ...item, ...data };
    } else {
        return;
    }

    isSaving = true;
    try {
        if (type === 'users') {
            await updateUser(id, data);
        } else if (type === 'comments') {
            await updateComment(id, data);
        } else if (type === 'invites') {
            await updateInviteCode(id, data);
        }
        showToast('保存成功');
        document.getElementById('editModal').style.display = 'none';

        if (updatedItem) {
            const index = currentDataList.findIndex(d => d.id == id);
            if (index !== -1) {
                currentDataList[index] = updatedItem;
                renderTable(currentDataList, currentTotal);
                updatePaginationInfo();
            }
        }

        // 编辑后重新获取统计数据
        await fetchStats();
    } catch (err) {
        showToast('保存失败: ' + err.message);
    } finally {
        isSaving = false;
    }
  }

  // ---------- 13.4 还原冷却期数据处理 ----------
  async function handleRestore(item) {
      let message, url;
      if (currentTab === 'deleted_users') {
          message = `确定要还原用户 ${maskPhone(item.phone)} 吗？`;
          url = `/admin/users/${item.id}/restore`;
      } else if (currentTab === 'deleted_comments') {
          message = `确定要还原评论 (ID: ${item.id}) 吗？`;
          url = `/admin/comments/${item.id}/restore`;
      } else return;

      showConfirm(message, async () => {
          try {
              await http({ method: 'PUT', url, needAuth: true });
              showToast('还原成功');

              // 乐观更新：从当前列表中移除该项
              const idx = currentDataList.findIndex(d => d.id == item.id);
              if (idx !== -1) {
                  currentDataList.splice(idx, 1);
                  currentTotal = Math.max(0, currentTotal - 1);
              }

              if (currentDataList.length === 0 && currentPage > 1) {
                  currentPage--;
                  await loadData();
              } else {
                  renderTable(currentDataList, currentTotal);
                  updatePaginationInfo();
              }

              await fetchStats();
          } catch (err) {
              showToast('还原失败: ' + err.message);
          }
      });
  }

  // ======================== 14. 二次确认弹窗 ========================
  function showConfirm(msg, onYes) {
    confirmMessage.textContent = msg;
    customConfirm.style.display = 'flex';

    const yesBtn = document.getElementById('confirmYesBtn');
    if (!yesBtn) {
      console.error('confirmYesBtn not found');
      return;
    }
    const newYes = yesBtn.cloneNode(true);
    if (yesBtn.parentNode) {
      yesBtn.parentNode.replaceChild(newYes, yesBtn);
    } else {
      yesBtn.replaceWith(newYes);
    }
    newYes.addEventListener('click', () => {
      closeConfirm();
      if (onYes) onYes();
    });
  }

  function closeConfirm() {
    customConfirm.style.display = 'none';
  }

  // ======================== 15. 事件绑定 ========================
  function bindEvents() {
    // 标签页切换
    tabBtns.forEach(btn => {
      btn.addEventListener('click', async () => {
        const tab = btn.dataset.tab;
        if (!tab || tab === currentTab) return;
        await switchTab(tab);
      });
    });

    // 刷新按钮
    refreshBtn.addEventListener('click', async () => {
      await loadData();
      await fetchStats();
    });

    // 分页按钮
    prevBtn.addEventListener('click', () => goToPage(currentPage - 1));
    nextBtn.addEventListener('click', () => goToPage(currentPage + 1));
    pageJumpBtn.addEventListener('click', () => {
      const page = parseInt(pageJumpInput.value, 10);
      if (isNaN(page) || page < 1 || page > totalPages) {
        showToast(`页码必须在 1 ~ ${totalPages} 之间`);
        return;
      }
      goToPage(page);
    });

    // 退出登录
    adminLogoutBtn.addEventListener('click', () => {
      showConfirm('确定退出管理后台？', () => {
        showToast('已退出登录，即将跳转...', 1500);
        localStorage.removeItem('access_token');
        setTimeout(() => {
          window.location.href = '/HTML/Index/index.html';
        }, 1500);
      });
    });

    // 邀请码生成
    generateInvitesBtn.addEventListener('click', generateInvites);

    // 安全控制
    toggleAdminLoginBtn.addEventListener('click', toggleAdminLogin);

    // 操作日志查询弹窗相关
    queryLogsBtn.addEventListener('click', queryAdminLogs);
    closeAdminLogsModalBtn.addEventListener('click', closeAdminLogsModal);
    adminLogsModal.addEventListener('click', (e) => {
      if (e.target === adminLogsModal) closeAdminLogsModal();
    });
    bindAdminLogsScroll();

    // 每日摘要按钮
    triggerDailySummaryBtn.addEventListener('click', triggerDailySummary);

    // 手动清理冷却期数据按钮
    triggerCleanupBtn.addEventListener('click', triggerCleanup);

    // 日期联动
    logStartDate.addEventListener('change', function () {
      if (logStartDate.value) {
        logEndDate.min = logStartDate.value;
        if (logEndDate.value && logEndDate.value < logStartDate.value) {
          logEndDate.value = logStartDate.value;
        }
      } else {
        logEndDate.min = '';
      }
    });
    logEndDate.addEventListener('change', function () {
      if (logEndDate.value) {
        logStartDate.max = logEndDate.value;
        if (logStartDate.value && logStartDate.value > logEndDate.value) {
          logStartDate.value = logEndDate.value;
        }
      } else {
        logStartDate.max = '';
      }
    });

    // 输入限制
    inviteCountInput.addEventListener('input', function() {
      let val = parseInt(this.value, 10);
      if (isNaN(val)) { this.value = ''; return; }
      if (val < 1) this.value = 1;
      if (val > 100) this.value = 100;
    });
    inviteExpiryDaysInput.addEventListener('input', function() {
      let val = parseInt(this.value, 10);
      if (isNaN(val)) { this.value = ''; return; }
      if (val < 1) this.value = 1;
      if (val > 7) this.value = 7;
    });

    // 关闭确认框
    confirmNoBtn.addEventListener('click', closeConfirm);

    // 表格委托事件
    document.getElementById('adminTableWrapper').addEventListener('click', (e) => {
      const phoneToggle = e.target.closest('.phone-toggle');
      if (phoneToggle) {
        const full = phoneToggle.dataset.full;
        if (phoneToggle.textContent === full) {
          phoneToggle.textContent = maskPhone(full);
        } else {
          phoneToggle.textContent = full;
        }
      }

      const editBtn = e.target.closest('.fa-pen');
      const delBtn = e.target.closest('.fa-trash-alt');
      const restoreBtn = e.target.closest('.fa-undo');
      
      if (editBtn) {
          const row = e.target.closest('tr');
          const id = row?.dataset.recordId;
          if (id) {
              const item = currentDataList.find(d => d.id == id);
              if (item) openEditModal(item);
          }
      }
      
      if (delBtn) {
          const row = e.target.closest('tr');
          const id = row?.dataset.recordId;
          if (id) {
              const item = currentDataList.find(d => d.id == id);
              if (item) handleDelete(item);
          }
      }

      if (restoreBtn) {
          const row = e.target.closest('tr');
          const id = row?.dataset.recordId;
          if (id) {
              const item = currentDataList.find(d => d.id == id);
              if (item) handleRestore(item);
          }
      }
    });

    // 编辑保存按钮
    document.getElementById('saveEditBtn').addEventListener('click', handleEditSave);

    // 取消编辑按钮
    document.getElementById('cancelEditBtn').addEventListener('click', () => {
        document.getElementById('editModal').style.display = 'none';
    });
    document.getElementById('closeEditModal').addEventListener('click', () => {
        document.getElementById('editModal').style.display = 'none';
    });
  }

  // ======================== 16. 初始化与启动 ========================
  function setDefaultDates() {
    const today = new Date().toISOString().split('T')[0];
    if (logStartDate) logStartDate.value = today;
    if (logEndDate) logEndDate.value = today;
  }

  async function init() {
    const token = localStorage.getItem('access_token');
    if (!token) {
      window.location.href = '/HTML/Index/index.html';
      return;
    }

    // 应用主题（管理员页面不需要 token 获取 theme_mode，使用 localStorage 缓存）
    window.initTheme();
    
    setDefaultDates();
    await checkDailySummaryStatus();
    await checkCleanupStatus();
    await switchTab('users');
    await fetchStats();
    bindEvents();
  }

  init();
})();