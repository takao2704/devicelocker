const STORAGE_KEY = "devicelocker-parent-ui-v1";

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
      quickQuantities: [1, 2, 3, 5],
      icon: "book-open",
    },
    {
      id: "word-problem",
      name: "文章題",
      unitName: "問",
      minutesPerUnit: 10,
      allowQuantity: true,
      quickQuantities: [1, 2, 3],
      icon: "file-pen-line",
    },
    {
      id: "marking",
      name: "丸つけ完了",
      unitName: "回",
      minutesPerUnit: 10,
      allowQuantity: false,
      quickQuantities: [1],
      icon: "circle-check",
    },
  ],
  history: [
    { id: "h1", time: "今日 21:10", title: "計算ドリル 3ページ", detail: "+15分を追加", minutes: 15, type: "add" },
    { id: "h2", time: "今日 20:37", title: "文章題 1問", detail: "+10分を追加", minutes: 10, type: "add" },
    { id: "h3", time: "今日 20:15", title: "一時停止", detail: "残り 42分", minutes: 0, type: "pause" },
    { id: "h4", time: "今日 19:12", title: "丸つけ完了", detail: "+10分を追加", minutes: 10, type: "add" },
  ],
};

let state = loadState();
let editingRuleId = null;

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

function icon(name) {
  return `<i data-lucide="${name}"></i>`;
}

function render() {
  const rule = selectedRule();
  const quantity = currentQuantity(rule);
  const minutes = rewardMinutes(rule);
  const projected = state.remainingMinutes + minutes;
  const limitProgress = Math.min(100, Math.round((state.remainingMinutes / state.dailyLimitMinutes) * 100));
  const isPaused = state.status === "停止中";

  app.innerHTML = `
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">${icon("shield-check")}</span>
        <span>DeviceLocker</span>
      </div>
      <button class="sync-button" type="button" data-action="sync">
        <span>最終同期 ${state.lastSyncedAt}</span>
        ${icon("refresh-cw")}
      </button>
    </header>

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
      <div class="section-title compact-title">
        <div>
          ${icon("bar-chart-3")}
          <h2>追加内容の確認</h2>
        </div>
      </div>
      <div class="summary-grid">
        <div>
          <span>内訳</span>
          <strong>${rule.allowQuantity ? `${quantity}${rule.unitName} × ${rule.minutesPerUnit}分` : `${rule.name}`}</strong>
        </div>
        <div>
          <span>追加する時間</span>
          <strong>+${minutes}分</strong>
        </div>
        <div>
          <span>追加後</span>
          <strong>${projected}分</strong>
        </div>
      </div>
      <button class="primary" type="button" data-action="add-time">
        ${icon("clock-plus")}
        ${rule.allowQuantity ? `${quantity}${rule.unitName}分を追加` : `${rule.name}で追加`}（+${minutes}分）
      </button>
      <button class="secondary full" type="button" data-action="manual">
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
        <button class="secondary" type="button" data-action="pause" ${isPaused ? "disabled" : ""}>
          ${icon("pause")}
          一時停止
        </button>
        <button class="secondary" type="button" data-action="resume" ${isPaused ? "" : "disabled"}>
          ${icon("play")}
          再開
        </button>
      </div>
      <p>一時停止中は、yuuto のMac利用を止めます。</p>
    </section>

    <section class="section history">
      <div class="section-title">
        <div>
          ${icon("history")}
          <h2>最近の履歴</h2>
        </div>
        <button class="text-button" type="button">すべて見る ${icon("chevron-right")}</button>
      </div>
      <div class="history-list">
        ${state.history.slice(0, 5).map(renderHistoryRow).join("")}
      </div>
      <p class="timezone-note">すべての時刻は端末のタイムゾーンで表示されています。</p>
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
  const quicks = Array.from(new Set([...(rule.quickQuantities || []), quantity])).sort((a, b) => a - b);
  return `
    <div class="quantity-panel">
      <div class="stepper-line">
        <span>ページ数</span>
        <div class="stepper" aria-label="ページ数を変更">
          <button type="button" data-action="quantity-minus" aria-label="減らす">${icon("minus")}</button>
          <strong>${quantity}${rule.unitName}</strong>
          <button type="button" data-action="quantity-plus" aria-label="増やす">${icon("plus")}</button>
        </div>
      </div>
      <div class="quick-quantities" aria-label="よく使う数">
        ${quicks.map((value) => `
          <button type="button" class="${value === quantity ? "active" : ""}" data-action="quantity-set" data-quantity="${value}">
            ${value}${rule.unitName}
          </button>
        `).join("")}
      </div>
    </div>
  `;
}

function renderHistoryRow(item) {
  const iconName = item.type === "pause" ? "pause" : item.type === "resume" ? "play" : "plus";
  return `
    <div class="history-row">
      <span class="history-icon ${item.type}">${icon(iconName)}</span>
      <div>
        <strong>${item.time}</strong>
        <span>${item.title}</span>
        <small>${item.detail}</small>
      </div>
      <span class="history-minutes">${item.minutes > 0 ? `+${item.minutes}分` : ""}</span>
    </div>
  `;
}

function persistAndRender() {
  saveState();
  render();
}

function handleAction(event) {
  const control = event.target.closest("[data-action]");
  if (!control) return;
  const action = control.dataset.action;
  const rule = selectedRule();

  if (action === "select-rule") {
    const nextRule = state.rules.find((item) => item.id === control.dataset.ruleId);
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

  if (action === "quantity-set") {
    state.quantity = Number(control.dataset.quantity);
    persistAndRender();
  }

  if (action === "add-time") {
    const minutes = rewardMinutes(rule);
    const quantity = currentQuantity(rule);
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
    state.status = "停止中";
    state.screen = "ロック中";
    addHistory({ time: nowLabel(), title: "一時停止", detail: `残り ${state.remainingMinutes}分`, minutes: 0, type: "pause" });
    persistAndRender();
  }

  if (action === "resume") {
    state.status = "利用可";
    state.screen = "使用中";
    addHistory({ time: nowLabel(), title: "再開", detail: `残り ${state.remainingMinutes}分`, minutes: 0, type: "resume" });
    persistAndRender();
  }

  if (action === "sync") {
    state.lastSyncedAt = syncTime();
    persistAndRender();
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

function handleRuleSubmit(event) {
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
    quickQuantities: previous?.quickQuantities || [1, 2, 3, 5],
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
  persistAndRender();
}

function handleManualSubmit(event) {
  event.preventDefault();
  const reason = document.querySelector("#manualReason").value.trim() || "手動追加";
  const minutes = Math.max(1, Math.min(180, Number(document.querySelector("#manualMinutes").value) || 10));
  state.remainingMinutes += minutes;
  state.lastSyncedAt = syncTime();
  addHistory({ time: nowLabel(), title: reason, detail: `+${minutes}分を追加`, minutes, type: "add" });
  closeModals();
  persistAndRender();
}

function deleteCurrentRule() {
  if (!editingRuleId || state.rules.length <= 1) return;
  state.rules = state.rules.filter((item) => item.id !== editingRuleId);
  state.selectedRuleId = state.rules[0].id;
  state.quantity = 1;
  closeModals();
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

render();
