/* Leo Todo 前端逻辑（pywebview js_api 桥接） */
"use strict";

/* ---------------- 桥接 ---------------- */
const Bridge = {
  hasApi() {
    return !!(window.pywebview && window.pywebview.api);
  },
  async call(method, ...args) {
    if (!this.hasApi()) {
      throw new Error("未检测到 pywebview API，请通过 `python main.py` 启动应用");
    }
    return window.pywebview.api[method](...args);
  },
};

/* ---------------- 全局状态 ---------------- */
const State = {
  filters: { status: "", project: "", priority: "", tag: "", search: "" },
  selectedId: null,
  tasks: [],
  projects: [],
  tags: [],
  appInfo: { name: "Leo Todo", auto_sync_on_start: true },
  msLoggedIn: false,
  deviceWaiting: false,
  deviceUri: "",
  deviceCode: "",
};

/* ---------------- DOM 工具 ---------------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toast(msg, type = "ok", ms = 3000) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${type}`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => el.classList.add("hidden"), ms);
}

function fmtDue(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  if (isNaN(dt)) return iso;
  const p = (n) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())} ` +
    `${p(dt.getHours())}:${p(dt.getMinutes())}`;
}

function fmtDueForInput(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  if (isNaN(dt)) return "";
  const p = (n) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}T${p(dt.getHours())}:${p(dt.getMinutes())}`;
}

function inputToIso(value) {
  if (!value) return "";
  const dt = new Date(value);
  if (isNaN(dt)) return "";
  return dt.toISOString();
}

/* ---------------- 启动 ---------------- */
let _bootStarted = false;
async function boot() {
  if (_bootStarted) return;
  _bootStarted = true;
  if (!Bridge.hasApi()) {
    toast("未检测到 pywebview API，请通过 python main.py 启动", "err", 6000);
    return;
  }
  try {
    State.appInfo = await Bridge.call("app_info");
    $("#app-name").textContent = State.appInfo.name;
    const ms = await Bridge.call("ms_status");
    State.msLoggedIn = !!(ms && ms.enabled && ms.logged_in);
    updateLoginBtn();
    await refreshStats();
    await refreshFilters();
    await refreshList();
    if (State.appInfo.auto_sync_on_start && State.msLoggedIn) {
      await doSync();
    }
    startAutoSync();
    startUiRefresh();
  } catch (err) {
    toast("初始化失败：" + err.message, "err", 6000);
  }
}

function updateLoginBtn() {
  const btn = $("#login-btn");
  if (State.msLoggedIn) {
    btn.textContent = "● 已登录";
    btn.classList.add("btn-primary");
  } else {
    btn.textContent = "○ Microsoft 登录";
    btn.classList.remove("btn-primary");
  }
}

/* ---------------- 数据刷新 ---------------- */
async function refreshStats() {
  try {
    const s = await Bridge.call("stats");
    $("#stats").innerHTML = `
      <div class="stat-card"><div class="stat-num">${s.active ?? 0}</div><div class="stat-label">待办中</div></div>
      <div class="stat-card stat-overdue"><div class="stat-num">${s.overdue ?? 0}</div><div class="stat-label">已逾期</div></div>
      <div class="stat-card"><div class="stat-num">${s.completed ?? 0}</div><div class="stat-label">已完成</div></div>
      <div class="stat-card"><div class="stat-num">${s.total ?? 0}</div><div class="stat-label">全部</div></div>`;
  } catch (err) {
    toast("加载统计失败：" + err.message, "err");
  }
}

async function refreshFilters() {
  try {
    State.projects = await Bridge.call("projects");
    State.tags = await Bridge.call("tags");
  } catch (err) {
    toast("加载过滤器失败：" + err.message, "err");
    return;
  }
  const pf = $("#project-filters");
  pf.innerHTML = State.projects.length
    ? State.projects.map((p) =>
        `<button class="filter-item small-filter ${State.filters.project === p ? "active" : ""}" data-project="${esc(p)}">${esc(p)}</button>`)
        .join("")
    : '<span class="filter-item small-filter" style="color:#aaa">无项目</span>';
  const tf = $("#tag-filters");
  tf.innerHTML = State.tags.length
    ? State.tags.map((t) =>
        `<button class="filter-item small-filter ${State.filters.tag === t ? "active" : ""}" data-tag="${esc(t)}"># ${esc(t)}</button>`)
        .join("")
    : '<span class="filter-item small-filter" style="color:#aaa">无标签</span>';

  // 项目 datalist
  $("#project-list").innerHTML = State.projects.map((p) => `<option value="${esc(p)}">`).join("");
  pf.querySelectorAll("[data-project]").forEach((el) =>
    el.addEventListener("click", () => toggleProjectFilter(el.dataset.project)));
  tf.querySelectorAll("[data-tag]").forEach((el) =>
    el.addEventListener("click", () => toggleTagFilter(el.dataset.tag)));
}

async function refreshList() {
  const f = State.filters;
  try {
    const tasks = await Bridge.call("list_tasks", f.status, f.status === "deleted", f.project, f.priority, f.tag, f.search);
    State.tasks = tasks;
    renderTasks(tasks);
  } catch (err) {
    toast("加载任务失败：" + err.message, "err");
  }
}

function renderTasks(tasks) {
  const list = $("#task-list");
  const count = $("#list-count");
  count.textContent = `${tasks.length} 项`;
  $("#task-empty").style.display = tasks.length ? "none" : "block";

  list.innerHTML = tasks
    .map((t) => {
      const priClass = `p-${t.priority}`;
      const syncBadge = t.sync_status === "pending_push" || t.sync_status === "pending_delete"
        ? `<span class="badge sync-pending">待同步</span>` : "";
      const syncErr = t.sync_status === "error" ? `<span class="badge sync-error">同步失败</span>` : "";
      const due = t.due_date ? `<span class="badge ${isOverdue(t)}">${fmtDue(t.due_date)}</span>` : "";
      const tags = (t.tags || []).slice(0, 3).map((g) => `<span class="tag-chip">${esc(g)}</span>`).join("");
      return `
        <div class="task-item ${t.status === "completed" ? "completed" : ""} ${State.selectedId === t.id ? "selected" : ""}"
             data-id="${esc(t.id)}">
          <button class="task-check" data-action="toggle" title="${t.status === "completed" ? "标记未完成" : "标记完成"}">
            ${t.status === "completed" ? "✓" : ""}
          </button>
          <div class="task-main">
            <div class="task-title">${esc(t.title)}</div>
            <div class="task-sub">
              ${t.project ? `<span class="badge">${esc(t.project)}</span>` : ""}
              <span class="badge ${priClass}">${t.priority}</span>
              ${due}${syncBadge}${syncErr} ${tags}
            </div>
          </div>
          <div class="task-right">
            <button class="icon-btn task-delete-btn" data-action="delete" title="删除">🗑</button>
          </div>
        </div>`;
    })
    .join("");

  list.querySelectorAll(".task-item").forEach((item) => {
    item.addEventListener("click", (e) => {
      if (e.target.closest("[data-action]")) return;
      selectTask(item.dataset.id);
    });
  });
  list.querySelectorAll("[data-action=toggle]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleTask(btn.closest(".task-item").dataset.id);
    });
  });
  list.querySelectorAll("[data-action=delete]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteTask(btn.closest(".task-item").dataset.id);
    });
  });
}

function isOverdue(t) {
  if (t.status === "completed" || t.status === "deleted" || !t.due_date) return "due";
  return new Date(t.due_date) < new Date() ? "due-overdue" : "due";
}

/* ---------------- 筛选 ---------------- */
function setStatusFilter(status) {
  State.filters.status = status;
  $$("#sidebar .filter-item[data-status]").forEach((el) =>
    el.classList.toggle("active", el.dataset.status === status));
  refreshList();
}
function toggleProjectFilter(project) {
  State.filters.project = State.filters.project === project ? "" : project;
  refreshFilters();
  refreshList();
}
function toggleTagFilter(tag) {
  State.filters.tag = State.filters.tag === tag ? "" : tag;
  refreshFilters();
  refreshList();
}

/* ---------------- 详情 ---------------- */
async function selectTask(id) {
  State.selectedId = id;
  $$("#task-list .task-item").forEach((el) =>
    el.classList.toggle("selected", el.dataset.id === id));
  try {
    const task = await Bridge.call("get_task", id);
    renderDetail(task);
    $("#detail-panel").classList.remove("hidden");
  } catch (err) {
    toast("打开任务失败：" + err.message, "err");
  }
}

function renderDetail(task) {
  if (!task) return;
  $("#detail-title").value = task.title || "";
  $("#detail-project").value = task.project || "";
  $("#detail-priority").value = task.priority || "medium";
  $("#detail-due").value = fmtDueForInput(task.due_date);
  $("#detail-tags").value = (task.tags || []).join(", ");
  $("#detail-description").value = task.description || "";
  $("#detail-source").textContent = task.source;
  $("#detail-source").className = `badge source-badge ${task.source === "microsoft" ? "source-ms" : ""}`;
  const syncLabel = { local: "本地", synced: "已同步", pending_push: "待推送", pending_delete: "待删除", error: "同步失败" };
  const syncEl = $("#detail-sync");
  syncEl.textContent = syncLabel[task.sync_status] || task.sync_status;
  syncEl.className = `badge sync-badge ${task.sync_status === "pending_push" || task.sync_status === "pending_delete" ? "sync-pending" : ""} ${task.sync_status === "error" ? "sync-error" : ""}`;
  const check = $("#detail-check");
  const done = task.status === "completed";
  check.textContent = done ? "✓" : "○";
  check.classList.toggle("done", done);
  renderAttachments(task.attachments || []);
}

function renderAttachments(attachments) {
  const list = $("#attachment-list");
  if (!attachments.length) {
    list.innerHTML = '<span class="att-name" style="color:#aaa">暂无附件</span>';
    return;
  }
  list.innerHTML = attachments.map((a) => {
    if (a.is_image) {
      return `
        <div class="att-item" data-id="${esc(a.id)}">
          <img class="att-thumb" src="${a.preview_url}" alt="${esc(a.file_name)}">
          <button class="att-remove" data-action="remove-att" title="删除附件">✕</button>
          <div class="att-name">${esc(a.file_name)}</div>
        </div>`;
    }
    return `
      <div class="att-item" data-id="${esc(a.id)}">
        <div class="att-file">📄 ${esc(a.file_name)}</div>
        <button class="att-remove" data-action="remove-att" title="删除附件">✕</button>
        <div class="att-name">${esc(a.file_name)}</div>
      </div>`;
  }).join("");
  list.querySelectorAll(".att-thumb").forEach((img) => {
    img.addEventListener("click", () => showLightbox(img.src));
  });
  list.querySelectorAll("[data-action=remove-att]").forEach((btn) => {
    btn.addEventListener("click", () => removeAttachment(btn.closest(".att-item").dataset.id));
  });
}

async function saveDetail() {
  const id = State.selectedId;
  if (!id) return;
  const fields = {
    title: $("#detail-title").value.trim() || "（无标题）",
    project: $("#detail-project").value.trim(),
    priority: $("#detail-priority").value,
    due_date: inputToIso($("#detail-due").value),
    tags: $("#detail-tags").value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
    description: $("#detail-description").value,
  };
  try {
    const task = await Bridge.call("update_task", id, fields);
    if (task) {
      toast("已保存");
      refreshStats();
      refreshFilters();
      refreshList();
      renderDetail(task);
    }
  } catch (err) {
    toast("保存失败：" + err.message, "err");
  }
}

async function toggleTask(id) {
  try {
    const task = State.tasks.find((t) => t.id === id);
    const done = !(task && task.status === "completed");
    await Bridge.call("complete_task", id, done);
    toast(done ? "已完成 ✓" : "已恢复为待办");
    refreshStats();
    refreshList();
    if (State.selectedId === id) selectTask(id);
  } catch (err) {
    toast("操作失败：" + err.message, "err");
  }
}

async function deleteTask(id) {
  if (!confirm("删除任务？该操作会同步到 Microsoft To Do（软删除）。")) return;
  try {
    await Bridge.call("delete_task", id);
    toast("已删除（软删除）");
    if (State.selectedId === id) {
      State.selectedId = null;
      $("#detail-panel").classList.add("hidden");
    }
    refreshStats();
    refreshFilters();
    refreshList();
  } catch (err) {
    toast("删除失败：" + err.message, "err");
  }
}

/* ---------------- 附件 ---------------- */
async function addAttachmentFromFile(file) {
  if (!State.selectedId) return;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      await Bridge.call("add_attachment_data", State.selectedId, file.name, reader.result);
      toast("附件已添加");
      selectTask(State.selectedId);
    } catch (err) {
      toast("添加附件失败：" + err.message, "err");
    }
  };
  reader.readAsDataURL(file);
}

async function removeAttachment(attId) {
  if (!confirm("删除附件？")) return;
  try {
    await Bridge.call("remove_attachment", attId);
    toast("附件已删除");
    selectTask(State.selectedId);
  } catch (err) {
    toast("删除附件失败：" + err.message, "err");
  }
}

/* ---------------- 新建任务 ---------------- */
function openModal() {
  $("#modal-overlay").classList.remove("hidden");
  $("#new-title").value = "";
  $("#new-project").value = State.filters.project || "";
  $("#new-priority").value = "medium";
  $("#new-tags").value = "";
  $("#new-description").value = "";
  $("#new-title").focus();
}
function closeModal() {
  $("#modal-overlay").classList.add("hidden");
}
async function createTask() {
  const title = $("#new-title").value.trim();
  if (!title) {
    toast("请输入任务标题", "err");
    return;
  }
  const data = {
    title,
    project: $("#new-project").value.trim(),
    priority: $("#new-priority").value,
    tags: $("#new-tags").value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
    description: $("#new-description").value,
  };
  try {
    const task = await Bridge.call("create_task", data);
    toast("任务已创建（待同步）");
    closeModal();
    State.selectedId = task.id;
    refreshStats();
    refreshFilters();
    refreshList();
    selectTask(task.id);
    $("#detail-panel").classList.remove("hidden");
  } catch (err) {
    toast("创建失败：" + err.message, "err");
  }
}

/* ---------------- 同步 ---------------- */
async function autoSync() {
  // 静默自动同步（定时触发）：不操作按钮动画、不 toast
  if (!State.msLoggedIn) return;
  try {
    const result = await Bridge.call("sync");
    if (result.ok) {
      refreshStats();
      refreshFilters();
      refreshList();
      if (State.selectedId) selectTask(State.selectedId);
    }
  } catch (e) {
    // 静默失败，等下次周期
  }
}

function startAutoSync() {
  // 每 2 分钟自动双向同步一次（已登录才执行）
  setInterval(autoSync, 120000);
}

function startUiRefresh() {
  // 每 30 秒刷新统计与列表，保证数字/任务实时反映最新状态（不触发同步）
  setInterval(async () => {
    try {
      await refreshStats();
      await refreshFilters();
      await refreshList();
      if (State.selectedId) selectTask(State.selectedId);
    } catch (e) { /* 静默 */ }
  }, 30000);
}

async function doSync() {
  const btn = $("#sync-btn");
  const spinner = $("#sync-spinner");
  btn.disabled = true;
  spinner.classList.add("spinning");
  $("#sync-dot").className = "sync-dot sync";
  try {
    const result = await Bridge.call("sync");
    if (result.ok) {
      const r = result.reports[0] || {};
      $("#sync-dot").className = "sync-dot ok";
      toast(`同步完成：拉取 ${r.pulled}，新增 ${r.created}，更新 ${r.updated}，删除 ${r.deleted_local + r.pushed_delete}${r.errors.length ? "（部分失败）" : ""}`);
    } else {
      $("#sync-dot").className = "sync-dot err";
      toast("同步失败：" + result.error, "err");
    }
  } catch (err) {
    $("#sync-dot").className = "sync-dot err";
    toast("同步失败：" + err.message, "err");
  } finally {
    btn.disabled = false;
    spinner.classList.remove("spinning");
    refreshStats();
    refreshFilters();
    refreshList();
    if (State.selectedId) selectTask(State.selectedId);
  }
}

/* ---------------- 登录 ---------------- */
async function handleLogin() {
  if (State.msLoggedIn) {
    if (!confirm("退出 Microsoft 登录？")) return;
    try {
      await Bridge.call("ms_logout");
      State.msLoggedIn = false;
      updateLoginBtn();
      toast("已退出登录");
    } catch (err) {
      toast("退出失败：" + err.message, "err");
    }
    return;
  }
  // 直接走设备码流：不依赖 Azure 注册的 redirect_uri（交互式 ms_login
  // 要求 redirect_uri=http://localhost，与 https://localhost/todo 不匹配时必败）
  openDeviceModal();
}

async function openDeviceModal() {
  $("#device-overlay").classList.remove("hidden");
  State.deviceUri = "";
  State.deviceCode = "";
  try {
    const flow = await Bridge.call("ms_device_start");
    if (flow.ok) {
      State.deviceUri = flow.verification_uri;
      State.deviceCode = flow.user_code;
      $("#device-uri").textContent = flow.verification_uri;
      $("#device-code").textContent = flow.user_code;
    } else {
      $("#device-uri").textContent = flow.message;
      $("#device-code").textContent = "--";
    }
  } catch (err) {
    toast("设备码初始化失败：" + err.message, "err");
  }
}

async function openDeviceUri() {
  if (!State.deviceUri) return;
  try {
    const result = await Bridge.call("open_device_uri", State.deviceUri);
    if (result.ok && result.browser === "chrome") {
      toast("已用谷歌浏览器打开登录网址");
    } else if (result.ok) {
      toast("已用默认浏览器打开登录网址");
    } else {
      toast("打开浏览器失败：" + (result.message || ""), "err");
    }
  } catch (err) {
    toast("打开浏览器失败：" + err.message, "err");
  }
}

async function copyDeviceCode() {
  if (!State.deviceCode || State.deviceCode === "--") return;
  // 先尝试 Python 侧 Win32 剪贴板 API
  try {
    const result = await Bridge.call("copy_text", State.deviceCode);
    if (result.ok) {
      toast("验证码已复制");
      return;
    }
  } catch (e) { /* 回退到 JS 方案 */ }
  // 回退方案：使用 WebView 内的 Clipboard API
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(State.deviceCode);
      toast("验证码已复制");
    } else {
      // 最后回退：创建临时 textarea 触发复制
      const ta = document.createElement("textarea");
      ta.value = State.deviceCode;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      toast("验证码已复制");
    }
  } catch (err) {
    toast("复制失败：" + (err.message || err), "err");
  }
}

function closeDeviceModal() {
  $("#device-overlay").classList.add("hidden");
}
async function waitDevice() {
  if (State.deviceWaiting) return;
  State.deviceWaiting = true;
  try {
    const result = await Bridge.call("ms_device_wait");
    if (result.ok) {
      State.msLoggedIn = true;
      updateLoginBtn();
      closeDeviceModal();
      toast("登录成功，开始同步…");
      doSync();
    } else {
      toast("设备码授权失败：" + result.message, "err");
    }
  } catch (err) {
    toast("设备码授权失败：" + err.message, "err");
  } finally {
    State.deviceWaiting = false;
  }
}

/* ---------------- 图片放大 ---------------- */
function showLightbox(src) {
  $("#img-lightbox").style.display = "flex";
  $("#img-lightbox").innerHTML = `<img src="${src}">`;
}

/* ---------------- 事件绑定 ---------------- */
function bindEvents() {
  // 状态筛选
  $$("#sidebar .filter-item[data-status]").forEach((el) => {
    el.addEventListener("click", () => setStatusFilter(el.dataset.status));
  });

  // 搜索
  let searchTimer = null;
  $("#search-input").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      State.filters.search = e.target.value.trim();
      refreshList();
    }, 250);
  });
  $("#search-clear").addEventListener("click", () => {
    $("#search-input").value = "";
    State.filters.search = "";
    refreshList();
  });

  // 顶部按钮
  $("#sync-btn").addEventListener("click", doSync);
  $("#login-btn").addEventListener("click", handleLogin);
  $("#add-task-btn").addEventListener("click", openModal);

  // 详情
  $("#detail-close").addEventListener("click", () => {
    State.selectedId = null;
    $("#detail-panel").classList.add("hidden");
  });
  $("#detail-save").addEventListener("click", saveDetail);
  $("#detail-check").addEventListener("click", () => State.selectedId && toggleTask(State.selectedId));
  $("#detail-delete").addEventListener("click", () => State.selectedId && deleteTask(State.selectedId));
  $("#add-attachment-btn").addEventListener("click", () => $("#attachment-file").click());
  $("#attachment-file").addEventListener("change", (e) => {
    Array.from(e.target.files).forEach(addAttachmentFromFile);
    e.target.value = "";
  });

  // 回车保存详情
  $("#detail-title").addEventListener("keydown", (e) => {
    if (e.key === "Enter") saveDetail();
  });

  // 新建弹窗
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal-cancel").addEventListener("click", closeModal);
  $("#modal-create").addEventListener("click", createTask);
  $("#new-title").addEventListener("keydown", (e) => {
    if (e.key === "Enter") createTask();
  });
  $("#modal-overlay").addEventListener("click", (e) => {
    if (e.target === $("#modal-overlay")) closeModal();
  });

  // 设备码弹窗
  $("#device-close").addEventListener("click", closeDeviceModal);
  $("#device-wait").addEventListener("click", waitDevice);
  $("#device-open").addEventListener("click", openDeviceUri);
  $("#device-copy").addEventListener("click", copyDeviceCode);
  $("#device-overlay").addEventListener("click", (e) => {
    if (e.target === $("#device-overlay")) closeDeviceModal();
  });

  // 图片放大
  $("#img-lightbox").addEventListener("click", () => {
    $("#img-lightbox").style.display = "none";
  });

  // 键盘快捷键
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      $("#img-lightbox").style.display = "none";
      closeModal();
    }
  });
}

/* ---------------- 初始化 ---------------- */
bindEvents();

// 等待 pywebview API 就绪后启动
function waitForApi(callback) {
    const maxRetries = 100;
    const interval = 100;
    let retries = 0;

    const tryCall = () => {
        if (window.pywebview && window.pywebview.api) {
            callback();
            return;
        }
        retries++;
        if (retries >= maxRetries) {
            toast("初始化超时，请重新启动", "err", 6000);
            return;
        }
        setTimeout(tryCall, interval);
    };

    tryCall();
}

// 同时监听 pywebviewready 事件
window.addEventListener("pywebviewready", () => waitForApi(boot));

// 立即开始轮询
waitForApi(boot);
