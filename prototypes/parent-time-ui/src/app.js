const STORAGE_KEY = "devicelocker-parent-ui-v1";
const AUTH_STORAGE_KEY = "devicelocker-parent-auth-v1";
const AUTH_PENDING_KEY = "devicelocker-parent-auth-pending-v1";

const remoteConfig = window.DEVICELOCKER_CONFIG || {};
const isRemoteMode = Boolean(
  remoteConfig.apiBaseUrl && remoteConfig.cognitoDomain && remoteConfig.cognitoClientId
);

const defaultState = {
  childName: "yuuto",
  remainingMinutes: 42,
  dailyLimitMinutes: 120,
  status: "利用可",
  online: true,
  screen: "使用中",
  selectedRuleId: "calc-drill",
  quantity: 3,
  lastSyncedAt: "21:11",
  rules: [
    {
      id: "calc-drill",
      name: "計算ドリル",
      unitName: "ページ",
      minutesPerUnit: 5,
      allowQuantity: true,
      icon: "book-open",
    },
    {
      id: "word-problem",
      name: "文章題",
      unitName: "問",
      minutesPerUnit: 10,
      allowQuantity: true,
      icon: "file-pen-line",
    },
    {
      id: "marking",
      name: "丸つけ完了",
      unitName: "回",
      minutesPerUnit: 10,
      allowQuantity: false,
      icon: "circle-check",
    },
  ],
  history: [
    { id: "h1", time: "今日 21:10", title: "計算ドリル 3ページ", detail: "+15分を追加", minutes: 15, type: "add" },
    { id: "h2", time: "今日 20:37", title: "文章題 1問", detail: "+10分を追加", minutes: 10, type: "add" },
    { id: "h3", time: "今日 20:15", title: "一時停止", detail: "残り 42分", minutes: 0, type: "pause" },
    { id: "h4", time: "今日 19:12", title: "丸つけ完了", detail: "+10分を追加", minutes: 10, type: "add" },
  ],
  usageHistory: [
    { id: "u1", time: "今日 21:08", title: "Mac利用", detail: "1分を消化", minutes: -1, seconds: 60, type: "usage" },
    { id: "u2", time: "今日 21:07", title: "Mac利用", detail: "1分を消化", minutes: -1, seconds: 60, type: "usage" },
  ],
};

let state = loadState();
let authState = loadAuthState();
let editingRuleId = null;
let remoteError = "";
let isBusy = false;
let historyExpanded = false;

const app = document.querySelector("#app");
const ruleModal = document.querySelector("#ruleModal");
const manualModal = document.querySelector("#manualModal");
const ruleForm = document.querySelector("#ruleForm");
const manualForm = document.querySelector("#manualForm");
const deleteRuleButton = document.querySelector("#deleteRuleButton");

function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved && Array.isArray(saved.rules) && Array.isArray(saved.history)) {
      return { ...defaultState, ...saved };
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
  return structuredClone(defaultState);
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function loadAuthState() {
  try {
    return JSON.parse(sessionStorage.getItem(AUTH_STORAGE_KEY)) || {};
  } catch {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
    return {};
  }
}

function saveAuthState(nextAuth) {
  authState = nextAuth || {};
  sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authState));
}

function clearAuthState() {
  authState = {};
  sessionStorage.removeItem(AUTH_STORAGE_KEY);
  sessionStorage.removeItem(AUTH_PENDING_KEY);
}

function configUserId() {
  return remoteConfig.userId || "child-001";
}

function remoteApiBase() {
  return String(remoteConfig.apiBaseUrl || "").replace(/\/$/, "");
}

function cognitoOrigin() {
  const domain = String(remoteConfig.cognitoDomain || "").replace(/\/$/, "");
  return domain.startsWith("http") ? domain : `https://${domain}`;
}

function currentAppUrl() {
  return `${window.location.origin}${window.location.pathname}`;
}

function redirectUri() {
  return remoteConfig.redirectUri || currentAppUrl();
}

function logoutUri() {
  return remoteConfig.logoutUri || currentAppUrl();
}

function base64UrlEncode(bytes) {
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function randomToken(byteLength = 32) {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

async function sha256Base64Url(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return base64UrlEncode(new Uint8Array(digest));
}

function decodeJwtPayload(token) {
  try {
    const payload = token.split(".")[1] || "";
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return JSON.parse(atob(padded));
  } catch {
    return {};
  }
}

function authEmail() {
  return authState.email || decodeJwtPayload(authState.idToken || "").email || "";
}

function authExpired() {
  return !authState.idToken || Date.now() > Number(authState.expiresAt || 0) - 60000;
}

async function startLogin() {
  const verifier = randomToken(48);
  const stateToken = randomToken(24);
  const challenge = await sha256Base64Url(verifier);
  const callbackUrl = redirectUri();
  sessionStorage.setItem(AUTH_PENDING_KEY, JSON.stringify({ verifier, stateToken, redirectUri: callbackUrl }));

  const params = new URLSearchParams({
    response_type: "code",
    client_id: remoteConfig.cognitoClientId,
    redirect_uri: callbackUrl,
    scope: "openid email profile",
    state: stateToken,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });
  if (remoteConfig.identityProvider) {
    params.set("identity_provider", remoteConfig.identityProvider);
  }
  window.location.assign(`${cognitoOrigin()}/oauth2/authorize?${params.toString()}`);
}

async function exchangeToken(params) {
  const response = await fetch(`${cognitoOrigin()}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error_description || body.error || "ログインに失敗しました");
  }
  const payload = decodeJwtPayload(body.id_token || authState.idToken || "");
  saveAuthState({
    idToken: body.id_token || authState.idToken,
    accessToken: body.access_token || authState.accessToken,
    refreshToken: body.refresh_token || authState.refreshToken,
    expiresAt: Date.now() + Number(body.expires_in || 3600) * 1000,
    email: payload.email || authState.email || "",
  });
}

async function completeLoginIfNeeded() {
  if (!isRemoteMode) return;
  const params = new URLSearchParams(window.location.search);
  if (params.has("error")) {
    remoteError = params.get("error_description") || params.get("error") || "ログインに失敗しました";
    window.history.replaceState({}, document.title, currentAppUrl());
    return;
  }
  if (!params.has("code")) return;

  const pending = JSON.parse(sessionStorage.getItem(AUTH_PENDING_KEY) || "{}");
  if (!pending.verifier || pending.stateToken !== params.get("state")) {
    remoteError = "ログイン状態を確認できませんでした";
    clearAuthState();
    window.history.replaceState({}, document.title, currentAppUrl());
    return;
  }

  await exchangeToken(new URLSearchParams({
    grant_type: "authorization_code",
    client_id: remoteConfig.cognitoClientId,
    code: params.get("code"),
    redirect_uri: pending.redirectUri,
    code_verifier: pending.verifier,
  }));
  sessionStorage.removeItem(AUTH_PENDING_KEY);
  window.history.replaceState({}, document.title, currentAppUrl());
}

async function refreshAuthIfNeeded() {
  if (!isRemoteMode || !authExpired()) return Boolean(authState.idToken);
  if (!authState.refreshToken) {
    clearAuthState();
    return false;
  }
  try {
    await exchangeToken(new URLSearchParams({
      grant_type: "refresh_token",
      client_id: remoteConfig.cognitoClientId,
      refresh_token: authState.refreshToken,
    }));
    return true;
  } catch {
    clearAuthState();
    return false;
  }
}

function signOut() {
  clearAuthState();
  if (isRemoteMode) {
    const params = new URLSearchParams({
      client_id: remoteConfig.cognitoClientId,
      logout_uri: logoutUri(),
    });
    window.location.assign(`${cognitoOrigin()}/logout?${params.toString()}`);
  } else {
    render();
  }
}

async function apiRequest(path, options = {}) {
  const ok = await refreshAuthIfNeeded();
  if (!ok) {
    render();
    throw new Error("ログインが必要です");
  }
  const response = await fetch(`${remoteApiBase()}${path}`, {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${authState.idToken}`,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) clearAuthState();
    throw new Error(body.message || body.error || "APIの更新に失敗しました");
  }
  return body;
}

function formatHistoryTime(at) {
  if (!at) return nowLabel();
  const date = new Date(Number(at) * 1000);
  const today = new Date();
  const time = new Intl.DateTimeFormat("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
  if (
    date.getFullYear() === today.getFullYear()
    && date.getMonth() === today.getMonth()
    && date.getDate() === today.getDate()
  ) {
    return `今日 ${time}`;
  }
  return `${date.getMonth() + 1}/${date.getDate()} ${time}`;
}

function normalizeHistory(items = []) {
  return items.map((item) => ({
    id: item.id || crypto.randomUUID(),
    at: Number(item.at || 0),
    time: item.time || formatHistoryTime(item.at),
    title: item.title || "操作",
    detail: item.detail || "",
    minutes: Number(item.minutes || 0),
    seconds: Number(item.seconds || 0),
    type: item.type || "add",
  }));
}

function applyRemoteStatus(data) {
  state = {
    ...state,
    childName: data.childName || state.childName,
    remainingMinutes: Number(data.remainingMinutes || 0),
    status: data.status || (data.isApproved ? "利用可" : "停止中"),
    online: Boolean(data.online),
    screen: data.screen || state.screen,
    lastSyncedAt: syncTime(),
    rules: Array.isArray(data.rewardRules) && data.rewardRules.length ? data.rewardRules : state.rules,
    history: normalizeHistory(data.history || state.history),
    usageHistory: normalizeHistory(data.usageHistory || []),
  };
  if (!state.rules.some((rule) => rule.id === state.selectedRuleId)) {
    state.selectedRuleId = state.rules[0]?.id;
  }
  saveState();
}

async function syncFromApi() {
  const data = await apiRequest(`/v1/parent/status?userId=${encodeURIComponent(configUserId())}`);
  applyRemoteStatus(data);
}

async function withRemoteSync(operation, options = {}) {
  isBusy = true;
  remoteError = "";
  render();
  try {
    await operation();
    if (options.refresh !== false) {
      await syncFromApi();
    }
  } catch (error) {
    remoteError = error.message || "更新に失敗しました";
  } finally {
    isBusy = false;
    render();
  }
}

function selectedRule() {
  return state.rules.find((rule) => rule.id === state.selectedRuleId) || state.rules[0];
}

function currentQuantity(rule = selectedRule()) {
  return rule?.allowQuantity ? Math.max(1, Number(state.quantity) || 1) : 1;
}

function rewardMinutes(rule = selectedRule()) {
  return (Number(rule?.minutesPerUnit) || 0) * currentQuantity(rule);
}

function nowLabel() {
  return `今日 ${new Intl.DateTimeFormat("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date())}`;
}

function syncTime() {
  return new Intl.DateTimeFormat("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
}

function describeRule(rule, quantity = currentQuantity(rule)) {
  if (!rule.allowQuantity) return rule.name;
  return `${rule.name} ${quantity}${rule.unitName}`;
}

function addHistory(entry) {
  state.history = [{ id: crypto.randomUUID(), ...entry }, ...state.history].slice(0, 12);
}

function formatDuration(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  const remainder = value % 60;
  if (minutes && remainder) return `${minutes}分${remainder}秒`;
  if (minutes) return `${minutes}分`;
  return `${remainder}秒`;
}

function icon(name) {
  return `<i data-lucide="${name}"></i>`;
}

function renderLogin() {
  app.innerHTML = `
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">${icon("shield-check")}</span>
        <span>DeviceLocker</span>
      </div>
    </header>
    ${remoteError ? `<div class="notice error">${remoteError}</div>` : ""}
    <section class="login-panel">
      <div class="login-mark">${icon("lock-keyhole")}</div>
      <h1>保護者ログイン</h1>
      <p>登録済みのGoogleアカウントで時間を追加できます。</p>
      <button class="primary" type="button" data-action="login" ${isBusy ? "disabled" : ""}>
        ${icon("log-in")}
        Googleでログイン
      </button>
    </section>
  `;

  if (window.lucide) {
    window.lucide.createIcons({ attrs: { "stroke-width": 2.2 } });
  }
}

function render() {
  if (isRemoteMode && !authState.idToken) {
    renderLogin();
    return;
  }

  const rule = selectedRule();
  const quantity = currentQuantity(rule);
  const minutes = rewardMinutes(rule);
  const limitProgress = Math.min(100, Math.round((state.remainingMinutes / state.dailyLimitMinutes) * 100));
  const isPaused = state.status === "停止中";
  const parentHistory = Array.isArray(state.history) ? state.history : [];
  const usageHistory = Array.isArray(state.usageHistory) ? state.usageHistory : [];

  app.innerHTML = `
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">${icon("shield-check")}</span>
        <span>DeviceLocker</span>
      </div>
      <div class="top-actions">
        ${isRemoteMode ? `
          <button class="icon-button top-icon" type="button" data-action="logout" aria-label="${authEmail() || "ログアウト"}">
            ${icon("log-out")}
          </button>
        ` : ""}
        <button class="sync-button" type="button" data-action="sync" ${isBusy ? "disabled" : ""}>
          <span>最終同期 ${state.lastSyncedAt}</span>
          ${icon("refresh-cw")}
        </button>
      </div>
    </header>

    ${remoteError ? `<div class="notice error">${remoteError}</div>` : ""}

    <section class="summary-band" aria-label="現在の状態">
      <div class="child">
        <div class="avatar">y</div>
        <div>
          <h1>${state.childName}</h1>
          <div class="status-line">
            <span class="dot ${isPaused ? "muted" : ""}"></span>
            <span>${state.status} / ${state.online ? "オンライン" : "オフライン"}</span>
          </div>
        </div>
      </div>
      <div class="remaining">
        <div class="remaining-number"><span>残り</span> ${state.remainingMinutes}<small>分</small></div>
        <div class="meter" aria-hidden="true"><span style="width:${limitProgress}%"></span></div>
        <p>今日の上限 ${state.dailyLimitMinutes}分</p>
      </div>
    </section>

    <section class="section reward-section">
      <div class="section-title">
        <div>
          ${icon("clipboard-list")}
          <h2>今日のドリル</h2>
        </div>
        <button class="text-button" type="button" data-action="add-rule">
          ${icon("plus")}
          項目を追加
        </button>
      </div>

      <div class="rule-list">
        ${state.rules.map((item) => renderRuleRow(item)).join("")}
      </div>
    </section>

    <section class="section confirmation">
      <button class="primary" type="button" data-action="add-time" ${isBusy ? "disabled" : ""}>
        ${icon("clock-plus")}
        ${rule.allowQuantity ? `${quantity}${rule.unitName}分を追加` : `${rule.name}で追加`}（+${minutes}分）
      </button>
      <button class="secondary full" type="button" data-action="manual" ${isBusy ? "disabled" : ""}>
        ${icon("calendar-plus")}
        手動で時間を指定
      </button>
    </section>

    <section class="section guardrails">
      <div class="section-title compact-title">
        <div>
          ${icon("shield")}
          <h2>緊急操作</h2>
        </div>
      </div>
      <div class="guardrail-buttons">
        <button class="secondary" type="button" data-action="pause" ${isPaused || isBusy ? "disabled" : ""}>
          ${icon("pause")}
          一時停止
        </button>
        <button class="secondary" type="button" data-action="resume" ${!isPaused || isBusy ? "disabled" : ""}>
          ${icon("play")}
          再開
        </button>
      </div>
      <p>一時停止中は、yuuto のMac利用を止めます。</p>
    </section>

    <section class="section history">
      <button class="section-title history-toggle" type="button" data-action="toggle-history" aria-expanded="${historyExpanded ? "true" : "false"}">
        <span>
          ${icon("history")}
          <h2>最近の履歴</h2>
        </span>
        <span class="text-button history-toggle-label">
          ${historyExpanded ? "閉じる" : "開く"} ${icon(historyExpanded ? "chevron-up" : "chevron-down")}
        </span>
      </button>
      ${historyExpanded ? `
        <div class="history-groups">
          <div class="history-group">
            <h3 class="history-group-title">追加・操作</h3>
            <div class="history-list">
              ${parentHistory.length ? parentHistory.slice(0, 5).map(renderHistoryRow).join("") : renderHistoryEmpty("追加履歴はまだありません")}
            </div>
          </div>
          <div class="history-group">
            <h3 class="history-group-title">時間消化</h3>
            <div class="history-list">
              ${usageHistory.length ? usageHistory.slice(0, 8).map(renderHistoryRow).join("") : renderHistoryEmpty("消化履歴はまだありません")}
            </div>
          </div>
        </div>
        <p class="timezone-note">すべての時刻は端末のタイムゾーンで表示されています。</p>
      ` : ""}
    </section>
  `;

  if (window.lucide) {
    window.lucide.createIcons({ attrs: { "stroke-width": 2.2 } });
  }
}

function renderRuleRow(rule) {
  const isSelected = rule.id === state.selectedRuleId;
  const quantity = currentQuantity(rule);
  const unitText = rule.allowQuantity
    ? `1${rule.unitName} = +${rule.minutesPerUnit}分`
    : `+${rule.minutesPerUnit}分`;

  return `
    <article class="rule-row ${isSelected ? "selected" : ""}" data-rule-id="${rule.id}">
      <button class="rule-main" type="button" data-action="select-rule" data-rule-id="${rule.id}">
        <span class="radio-dot" aria-hidden="true"></span>
        <span class="rule-copy">
          <strong>${rule.name}</strong>
          <small>${unitText}</small>
        </span>
      </button>
      <button class="icon-button edit" type="button" data-action="edit-rule" data-rule-id="${rule.id}" aria-label="${rule.name}を編集">
        ${icon("pencil")}
      </button>
      ${isSelected && rule.allowQuantity ? renderQuantity(rule, quantity) : ""}
    </article>
  `;
}

function renderQuantity(rule, quantity) {
  return `
    <div class="quantity-panel">
      <div class="stepper-line">
        <span>${rule.unitName}数</span>
        <div class="stepper" aria-label="${rule.unitName}数を変更">
          <button type="button" data-action="quantity-minus" aria-label="減らす">${icon("minus")}</button>
          <strong>${quantity}${rule.unitName}</strong>
          <button type="button" data-action="quantity-plus" aria-label="増やす">${icon("plus")}</button>
        </div>
      </div>
    </div>
  `;
}

function renderHistoryRow(item) {
  const iconName = item.type === "pause" ? "pause" : item.type === "resume" ? "play" : item.type === "usage" ? "timer" : "plus";
  const amount = item.type === "usage" && item.seconds > 0
    ? `-${formatDuration(item.seconds)}`
    : item.minutes > 0
      ? `+${item.minutes}分`
      : item.minutes < 0
        ? `${item.minutes}分`
        : "";
  return `
    <div class="history-row">
      <span class="history-icon ${item.type}">${icon(iconName)}</span>
      <div>
        <strong>${item.time}</strong>
        <span>${item.title}</span>
        <small>${item.detail}</small>
      </div>
      <span class="history-minutes ${item.type === "usage" ? "negative" : ""}">${amount}</span>
    </div>
  `;
}

function renderHistoryEmpty(text) {
  return `<p class="history-empty">${text}</p>`;
}

function persistAndRender() {
  saveState();
  render();
}

async function handleAction(event) {
  const control = event.target.closest("[data-action]");
  if (!control) return;
  if (control.disabled) return;
  const action = control.dataset.action;
  const rule = selectedRule();

  if (action === "login") {
    isBusy = true;
    render();
    await startLogin();
    return;
  }

  if (action === "logout") {
    signOut();
    return;
  }

  if (action === "select-rule") {
    const nextRule = state.rules.find((item) => item.id === control.dataset.ruleId);
    if (!nextRule) return;
    state.selectedRuleId = nextRule.id;
    state.quantity = nextRule.allowQuantity ? Math.max(1, state.quantity || 1) : 1;
    persistAndRender();
  }

  if (action === "quantity-minus") {
    state.quantity = Math.max(1, currentQuantity(rule) - 1);
    persistAndRender();
  }

  if (action === "quantity-plus") {
    state.quantity = Math.min(99, currentQuantity(rule) + 1);
    persistAndRender();
  }

  if (action === "add-time") {
    const minutes = rewardMinutes(rule);
    const quantity = currentQuantity(rule);
    if (isRemoteMode) {
      await withRemoteSync(() => apiRequest("/v1/parent/add-time", {
        method: "POST",
        body: {
          userId: configUserId(),
          minutes,
          reason: describeRule(rule, quantity),
          ruleId: rule.id,
          quantity,
        },
      }));
      return;
    }
    state.remainingMinutes += minutes;
    state.lastSyncedAt = syncTime();
    addHistory({
      time: nowLabel(),
      title: describeRule(rule, quantity),
      detail: `+${minutes}分を追加`,
      minutes,
      type: "add",
    });
    persistAndRender();
  }

  if (action === "pause") {
    if (isRemoteMode) {
      await withRemoteSync(() => apiRequest("/v1/parent/stop", {
        method: "POST",
        body: { userId: configUserId() },
      }));
      return;
    }
    state.status = "停止中";
    state.screen = "ロック中";
    addHistory({ time: nowLabel(), title: "一時停止", detail: `残り ${state.remainingMinutes}分`, minutes: 0, type: "pause" });
    persistAndRender();
  }

  if (action === "resume") {
    if (isRemoteMode) {
      await withRemoteSync(() => apiRequest("/v1/parent/start", {
        method: "POST",
        body: { userId: configUserId() },
      }));
      return;
    }
    state.status = "利用可";
    state.screen = "使用中";
    addHistory({ time: nowLabel(), title: "再開", detail: `残り ${state.remainingMinutes}分`, minutes: 0, type: "resume" });
    persistAndRender();
  }

  if (action === "sync") {
    if (isRemoteMode) {
      await withRemoteSync(() => syncFromApi(), { refresh: false });
      return;
    }
    state.lastSyncedAt = syncTime();
    persistAndRender();
  }

  if (action === "toggle-history") {
    historyExpanded = !historyExpanded;
    render();
  }

  if (action === "edit-rule") {
    openRuleModal(control.dataset.ruleId);
  }

  if (action === "add-rule") {
    openRuleModal(null);
  }

  if (action === "manual") {
    openManualModal();
  }
}

function openRuleModal(ruleId) {
  editingRuleId = ruleId;
  const rule = state.rules.find((item) => item.id === ruleId) || {
    name: "新しい項目",
    unitName: "回",
    minutesPerUnit: 5,
    allowQuantity: true,
  };
  document.querySelector("#ruleModalTitle").textContent = ruleId ? "項目を編集" : "項目を追加";
  document.querySelector("#ruleName").value = rule.name;
  document.querySelector("#ruleUnit").value = rule.unitName;
  document.querySelector("#ruleMinutes").value = rule.minutesPerUnit;
  document.querySelector("#ruleAllowQuantity").checked = Boolean(rule.allowQuantity);
  deleteRuleButton.hidden = !ruleId || state.rules.length <= 1;
  ruleModal.hidden = false;
  document.querySelector("#ruleName").focus();
  window.lucide?.createIcons({ attrs: { "stroke-width": 2.2 } });
}

function openManualModal() {
  manualModal.hidden = false;
  document.querySelector("#manualMinutes").focus();
  window.lucide?.createIcons({ attrs: { "stroke-width": 2.2 } });
}

function closeModals() {
  ruleModal.hidden = true;
  manualModal.hidden = true;
  editingRuleId = null;
}

async function handleRuleSubmit(event) {
  event.preventDefault();
  const formData = new FormData(ruleForm);
  const minutes = Math.max(1, Math.min(180, Number(formData.get("minutesPerUnit")) || 5));
  const previous = state.rules.find((item) => item.id === editingRuleId);
  const nextRule = {
    id: editingRuleId || crypto.randomUUID(),
    name: String(formData.get("name") || "新しい項目").trim(),
    unitName: String(formData.get("unitName") || "回").trim(),
    minutesPerUnit: minutes,
    allowQuantity: formData.get("allowQuantity") === "on",
    icon: previous?.icon || "book-open",
  };

  if (editingRuleId) {
    state.rules = state.rules.map((item) => item.id === editingRuleId ? { ...item, ...nextRule } : item);
  } else {
    state.rules = [...state.rules, nextRule];
    state.selectedRuleId = nextRule.id;
  }
  state.quantity = nextRule.allowQuantity ? Math.max(1, state.quantity || 1) : 1;
  closeModals();
  if (isRemoteMode) {
    await withRemoteSync(() => apiRequest("/v1/parent/reward-rules", {
      method: "PUT",
      body: { userId: configUserId(), rules: state.rules },
    }));
    return;
  }
  persistAndRender();
}

async function handleManualSubmit(event) {
  event.preventDefault();
  const reason = document.querySelector("#manualReason").value.trim() || "手動追加";
  const minutes = Math.max(1, Math.min(180, Number(document.querySelector("#manualMinutes").value) || 10));
  closeModals();
  if (isRemoteMode) {
    await withRemoteSync(() => apiRequest("/v1/parent/add-time", {
      method: "POST",
      body: { userId: configUserId(), minutes, reason },
    }));
    return;
  }
  state.remainingMinutes += minutes;
  state.lastSyncedAt = syncTime();
  addHistory({ time: nowLabel(), title: reason, detail: `+${minutes}分を追加`, minutes, type: "add" });
  persistAndRender();
}

async function deleteCurrentRule() {
  if (!editingRuleId || state.rules.length <= 1) return;
  state.rules = state.rules.filter((item) => item.id !== editingRuleId);
  state.selectedRuleId = state.rules[0].id;
  state.quantity = 1;
  closeModals();
  if (isRemoteMode) {
    await withRemoteSync(() => apiRequest("/v1/parent/reward-rules", {
      method: "PUT",
      body: { userId: configUserId(), rules: state.rules },
    }));
    return;
  }
  persistAndRender();
}

app.addEventListener("click", handleAction);
ruleForm.addEventListener("submit", handleRuleSubmit);
manualForm.addEventListener("submit", handleManualSubmit);
deleteRuleButton.addEventListener("click", deleteCurrentRule);
document.querySelectorAll("[data-close-modal]").forEach((button) => {
  button.addEventListener("click", closeModals);
});
document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) closeModals();
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModals();
});

async function init() {
  try {
    await completeLoginIfNeeded();
    if (isRemoteMode && authState.idToken) {
      await syncFromApi();
    }
  } catch (error) {
    remoteError = error.message || "同期に失敗しました";
  }
  render();
}

init();
