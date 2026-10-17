/* 咒语工坊 · SpellForge — 应用脚本
   交互约定对齐 docs/前端设计规范.md：堆叠 toast、统一确认弹窗、按钮 busy 态。 */

(() => {
  // 桌面模式：从启动 URL 取一次性令牌并立即从地址栏剥离；
  // 之后所有写请求自动携带 X-SF-Token（令牌只留在内存，不落 localStorage）。
  const token = new URLSearchParams(location.search).get("sf_token") || "";
  if (token) {
    history.replaceState(null, "", location.pathname);
    const origFetch = window.fetch.bind(window);
    window.fetch = function (input, init = {}) {
      if (typeof input === "string" && input.startsWith("/api/")) {
        init.headers = Object.assign({}, init.headers, { "X-SF-Token": token });
      }
      return origFetch(input, init);
    };
  }

  /* ---------------- 共享 UI 工具 ---------------- */
  const esc = (s) => (s ?? "").toString().replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (id) => document.getElementById(id);

  // 时间统一转浏览器本地时区展示；兼容 ISO（Z 结尾 / 无时区按 UTC）与
  // SQLite「YYYY-MM-DD HH:MM:SS（UTC）」两种历史格式。
  function fmtTime(t) {
    if (t == null || t === "") return "";
    let s = String(t).trim();
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(s)) s = s.replace(" ", "T") + "Z";
    else if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(s)) s += "Z";
    const d = new Date(s);
    if (isNaN(d.getTime())) return String(t);
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
      `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }

  const toastRoot = document.createElement("div");
  toastRoot.className = "toast-root";
  toastRoot.setAttribute("aria-live", "polite");
  document.body.appendChild(toastRoot);

  function toast(message, ok = true, timeout = 3400) {
    const item = document.createElement("div");
    item.className = `toast ${ok === "run" ? "run" : ok ? "ok" : "err"}`;
    item.setAttribute("role", "status");
    item.textContent = message || "";
    toastRoot.appendChild(item);
    requestAnimationFrame(() => item.classList.add("show"));
    setTimeout(() => {
      item.classList.remove("show");
      setTimeout(() => item.remove(), 250);
    }, timeout);
  }

  // 统一确认弹窗（替代原生 confirm，Esc=取消 / Enter=确认）
  function confirmDialog({ title = "请确认操作", message = "",
    confirmText = "确认", cancelText = "取消", danger = false } = {}) {
    return new Promise(resolve => {
      const host = document.createElement("div");
      host.className = "modal-mask";
      host.innerHTML = `
        <div class="modal modal-sm" role="dialog" aria-modal="true" aria-labelledby="ui-confirm-title">
          <div class="modal-head"><h3 id="ui-confirm-title">${esc(title)}</h3></div>
          <p class="meta">${esc(message)}</p>
          <div class="modal-foot">
            <button type="button" class="btn" data-ui-cancel>${esc(cancelText)}</button>
            <button type="button" class="btn ${danger ? "danger" : "primary"}" data-ui-confirm>${esc(confirmText)}</button>
          </div>
        </div>`;
      document.body.appendChild(host);
      const finish = (v) => { host.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
      const onKey = (e) => {
        if (e.key === "Escape") finish(false);
        if (e.key === "Enter") { e.preventDefault(); finish(true); }
      };
      host.addEventListener("click", e => {
        if (e.target === host || e.target.closest("[data-ui-cancel]")) finish(false);
      });
      host.querySelector("[data-ui-confirm]").addEventListener("click", () => finish(true));
      document.addEventListener("keydown", onKey);
      host.querySelector("[data-ui-confirm]").focus();
    });
  }

  // 按钮 busy 态：置灰 + 换文案，结束后还原
  function busy(btn, text) {
    const original = btn ? btn.textContent : "";
    if (btn) { btn.disabled = true; btn.setAttribute("aria-busy", "true"); if (text) btn.textContent = text; }
    return () => {
      if (btn) {
        btn.disabled = false;
        btn.removeAttribute("aria-busy");
        if (original) btn.textContent = original;
      }
    };
  }

  /* ---------------- 状态条 ---------------- */
  const sb = {
    el: $("statusbar"),
    show(text, progress) {
      this.el.hidden = false;
      this.el.innerHTML = "";
      const t = document.createElement("span");
      t.textContent = text;
      this.el.appendChild(t);
      if (typeof progress === "number" && isFinite(progress)) {
        const bar = document.createElement("div");
        bar.className = "progress";
        bar.innerHTML = `<div style="width:${Math.min(100, Math.max(0, progress * 100))}%"></div>`;
        this.el.appendChild(bar);
      }
    },
    clearSoon(delay = 3200) {
      setTimeout(() => { this.el.hidden = true; }, delay);
    },
    hide() { this.el.hidden = true; },
  };

  /* ---------------- 数据与应用状态 ---------------- */
  const RATIOS = ["1:1", "2:3", "3:2", "4:5", "5:4", "3:4", "4:3", "9:16", "16:9"];
  const TYPE_KEYS = { "人物": "person", "产品": "product", "景物": "scene", "品牌": "brand" };
  const state = {
    data: null, activeId: null, q: "", view: "browse",
    subjects: [], editingSubjectId: null,
    llm: { profiles: [], editingId: null },
  };
  const typeKey = (t) => TYPE_KEYS[t] || "person";

  async function loadAppVersion() {
    try {
      const info = await (await fetch("/api/version")).json();
      $("app-version").textContent = info.display_version;
      $("app-version").title = `咒语工坊 SpellForge ${info.display_version}`;
    } catch {
      $("app-version").textContent = "v?";
    }
  }

  async function init() {
    const r = await fetch("/api/styles");
    state.data = await r.json();
    if (!state.data.styles.length) {
      $("cards").innerHTML = '<div class="empty">暂无数据，点击「更新数据」抓取</div>';
      return;
    }
    state.activeId = state.data.styles[0].id;
    renderStyleSelect();
    renderStyle();
    await loadSubjects();
    initGen();
    loadHistory();
    loadLlmProfiles();
  }

  /* ---------------- 视图切换 ---------------- */
  function setView(v, pushHash = true) {
    if (!v || v === state.view) {
      if (pushHash) history.replaceState(null, "", `#${state.view}`);
      return;
    }
    state.view = v;
    document.querySelectorAll("[data-nav]").forEach(a =>
      a.classList.toggle("active", a.dataset.nav === v));
    $("view-browse").hidden = v !== "browse";
    $("view-subj").hidden = v !== "subj";
    $("view-gen").hidden = v !== "gen";
    if (v === "subj") loadSubjects();
    if (pushHash) history.replaceState(null, "", `#${v}`);
  }

  // 手动改地址栏 hash / 前进后退时同步视图
  window.addEventListener("hashchange", () => {
    const v = ({ subj: "subj", gen: "gen", browse: "browse" })[location.hash.replace("#", "")];
    if (v) setView(v, false);
  });

  document.querySelectorAll("[data-nav]").forEach(a => {
    a.addEventListener("click", e => { e.preventDefault(); setView(a.dataset.nav); });
  });
  $("nav-settings").addEventListener("click", e => { e.preventDefault(); openSettings(); });

  /* ---------------- 场景库 ---------------- */
  function renderStyleSelect() {
    const sel = $("style-select");
    const groups = {};
    state.data.styles.forEach(s => { (groups[s.group] ||= []).push(s); });
    sel.innerHTML = Object.entries(groups).map(([g, styles]) => `
      <optgroup label="${esc(g)}">
        ${styles.map(s =>
          `<option value="${esc(s.id)}" ${s.id === state.activeId ? "selected" : ""}>${esc(s.name)}（${s.scenarios.length}）</option>`).join("")}
      </optgroup>`).join("");
    sel.value = state.activeId;
  }

  function renderStyle() {
    const s = state.data.styles.find(x => x.id === state.activeId);
    if (!s) return;
    $("style-count").textContent = `${s.scenarios.length} 场景`;
    $("style-why").textContent = s.why_chosen ? `选此风格的原因：${s.why_chosen}` : "";
    const q = state.q.trim().toLowerCase();
    const cards = $("cards");
    cards.innerHTML = "";
    s.scenarios
      .filter(sc => !q || (sc.prompt + " " + sc.label).toLowerCase().includes(q))
      .forEach(sc => cards.appendChild(cardEl(s, sc)));
    if (!cards.children.length) cards.innerHTML = '<div class="empty">无匹配场景</div>';
  }

  function cardEl(style, sc) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-head">
        <h3>${esc(sc.label)}</h3>
        <span class="spacer"></span>
        ${sc.aspect_ratio
          ? `<span class="chip ok">AR ${esc(sc.aspect_ratio)}</span>`
          : '<span class="chip">比例未定</span>'}
        ${sc.creative_copy ? `<span class="chip violet">创意文案 ${sc.creative_copy.length}</span>` : ""}
      </div>
      <div class="prompt">${esc(sc.prompt)}</div>
      <div class="cc-item">
        <input type="text" placeholder="比例 2:3" aria-label="画幅比例" value="${esc(sc.aspect_ratio || "")}" data-ar>
        <button class="btn small" data-save-ar>保存比例</button>
        <span class="spacer"></span>
        <a href="${esc(sc.url)}" target="_blank" rel="noopener">原页面 ↗</a>
      </div>
      <details class="cc" ${sc.creative_copy ? "open" : ""}>
        <summary>创意文案（LLM 生成 / 手动编辑）</summary>
        <div data-cc-list style="margin-top:8px"></div>
        <div class="cc-actions">
          <button class="btn small" data-add-cc>＋ 加一条</button>
          <button class="btn small primary" data-save-cc>保存文案</button>
        </div>
      </details>`;

    card.querySelector("[data-save-ar]").onclick = async function () {
      const val = card.querySelector("[data-ar]").value.trim();
      if (val && !/^\d+:\d+$/.test(val)) return toast("比例格式应为 2:3 这类", false);
      const reset = busy(this, "保存中…");
      try {
        await patch(style.id, sc.id, { aspect_ratio: val || null, aspect_ratio_source: "manual" });
      } finally { reset(); }
    };

    const list = card.querySelector("[data-cc-list]");
    const ccItems = (sc.creative_copy || []).map(c => ({ ...c }));
    function renderCC() {
      list.innerHTML = "";
      if (!ccItems.length) {
        list.innerHTML = '<div class="empty" style="padding:12px">暂无，点击下方「加一条」</div>';
        return;
      }
      ccItems.forEach((item, i) => {
        const row = document.createElement("div");
        row.className = "cc-item";
        row.innerHTML = `
          <input class="cc-label" placeholder="标签" aria-label="标签" value="${esc(item.label)}">
          <textarea placeholder="文案内容" aria-label="文案内容">${esc(item.value)}</textarea>`;
        row.querySelector("input").oninput = e => { ccItems[i].label = e.target.value; };
        row.querySelector("textarea").oninput = e => { ccItems[i].value = e.target.value; };
        list.appendChild(row);
      });
    }
    renderCC();
    card.querySelector("[data-add-cc]").onclick = () => {
      ccItems.push({ label: "", value: "" });
      list.innerHTML = "";
      renderCC();
      list.querySelector("input")?.focus();
    };
    card.querySelector("[data-save-cc]").onclick = async () => {
      const clean = ccItems.filter(c => c.label.trim() && c.value.trim());
      if (!clean.length) return toast("至少需要一条完整文案", false);
      const reset = busy(card.querySelector("[data-save-cc]"), "保存中…");
      try {
        await patch(style.id, sc.id, { creative_copy: clean });
      } finally { reset(); }
    };
    return card;
  }

  async function patch(styleId, scId, body) {
    const r = await fetch(`/api/scenarios/${styleId}/${scId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.ok) { toast("已保存并同步 styles.json"); await refresh(false); }
    else toast(`保存失败：${(await r.text()).slice(0, 160)}`, false);
  }

  async function refresh(reNav = true) {
    const r = await fetch("/api/styles");
    state.data = await r.json();
    if (!state.data.styles.find(x => x.id === state.activeId))
      state.activeId = state.data.styles[0]?.id || null;
    renderStyleSelect();
    renderStyle();
  }

  $("style-select").addEventListener("change", e => {
    state.activeId = e.target.value;
    renderStyle();
  });
  $("search").addEventListener("input", e => { state.q = e.target.value; renderStyle(); });

  /* ---------------- 主体库 ---------------- */
  async function loadSubjects() {
    state.subjects = await (await fetch("/api/subjects")).json();
    renderSubjects();
    populateGenSubjects();
  }

  function renderSubjects() {
    $("subj-count").textContent = `${state.subjects.length} 个主体`;
    const box = $("subj-list");
    box.innerHTML = "";
    if (!state.subjects.length) {
      box.innerHTML = '<div class="empty">还没有主体，从上方添加；在生成器里可随时选「自定义」手动输入</div>';
      return;
    }
    state.subjects.forEach(s => box.appendChild(subjectCard(s)));
  }

  function subjectCard(s) {
    if (state.editingSubjectId === s.id) {
      const hint = document.createElement("div");
      hint.className = "card";
      hint.innerHTML = `
        <div class="card-head">
          <span class="chip run">编辑中</span><h3>${esc(s.name)}</h3>
        </div>
        <div class="meta">修改上方表单内容后点「保存修改」</div>`;
      return hint;
    }
    const d = document.createElement("div");
    d.className = "card interactive";
    d.innerHTML = `
      <div class="card-head">
        <span class="chip type-${typeKey(s.type)}">${esc(s.type)}</span>
        <h3>${esc(s.name)}</h3>
        <span class="spacer"></span>
        <button class="btn small" data-edit>编辑</button>
        <button class="btn small ghost danger" data-del>删除</button>
      </div>
      <div class="prompt prompt-sm">${esc(s.description)}</div>`;
    d.querySelector("[data-edit]").onclick = () => {
      state.editingSubjectId = s.id;
      $("subj-name").value = s.name;
      $("subj-desc").value = s.description;
      $("subj-type").value = s.type;
      $("subj-save").textContent = "保存修改";
      $("subj-cancel").hidden = false;
      renderSubjects();
      $("subject-form").scrollIntoView({ behavior: "smooth", block: "start" });
    };
    d.querySelector("[data-del]").onclick = async () => {
      const go = await confirmDialog({
        title: "删除主体",
        message: `删除主体「${s.name}」？生成历史中的记录会保留名称快照。`,
        confirmText: "删除", danger: true,
      });
      if (!go) return;
      const reset = busy(d.querySelector("[data-del]"), "删除中…");
      const r = await fetch(`/api/subjects/${s.id}`, { method: "DELETE" });
      reset();
      if (r.ok) { toast("已删除"); loadSubjects(); } else toast("删除失败", false);
    };
    return d;
  }

  async function saveSubject() {
    const body = {
      type: $("subj-type").value,
      name: $("subj-name").value.trim(),
      description: $("subj-desc").value.trim(),
    };
    if (!body.name) return toast("请填写主体名称", false);
    if (!body.description) return toast("请填写主体描述", false);
    const editing = state.editingSubjectId;
    const reset = busy($("subj-save"), "保存中…");
    const r = await fetch(editing ? `/api/subjects/${editing}` : "/api/subjects", {
      method: editing ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    reset();
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return toast(d.detail || "保存失败", false);
    toast(editing ? "已保存修改" : "已添加");
    resetSubjectForm();
    await loadSubjects();
  }

  function resetSubjectForm() {
    state.editingSubjectId = null;
    $("subj-name").value = "";
    $("subj-desc").value = "";
    $("subj-save").textContent = "添加主体";
    $("subj-cancel").hidden = true;
  }

  $("subj-save").onclick = saveSubject;
  $("subj-cancel").onclick = () => {
    const wasEditing = state.editingSubjectId != null;
    resetSubjectForm();
    renderSubjects();
    if (wasEditing) toast("已取消编辑");
  };

  /* ---------------- 生成器 ---------------- */
  function currentGenStyle() { return state.data?.styles.find(x => x.id === $("gen-style").value); }
  function currentGenScenario() {
    const style = currentGenStyle();
    return style?.scenarios.find(x => x.id === $("gen-scenario").value);
  }
  function currentTemplate() {
    const sc = currentGenScenario();
    if (!sc) return null;
    const lbl = $("gen-template").value;
    return (sc.creative_copy || []).find(t => t.label === lbl) || null;
  }

  function initGen() {
    if (!state.data?.styles.length) return;
    const sel = $("gen-style");
    const prev = sel.value;
    sel.innerHTML = state.data.styles.map(s =>
      `<option value="${esc(s.id)}">${esc(s.group)} · ${esc(s.name)}</option>`).join("");
    if (prev) sel.value = prev;
    if (!sel.value) sel.value = state.data.styles[0].id;
    $("gen-ratio").innerHTML = '<option value="">自动</option>' +
      RATIOS.map(r => `<option>${r}</option>`).join("");
    onGenStyleChange();
    sel.onchange = onGenStyleChange;
    $("gen-scenario").onchange = onGenScenarioChange;
    $("gen-template").onchange = onGenTemplateChange;
    $("gen-subject-sel").onchange = onGenSubjectSelChange;
    $("gen-go").onclick = runGenerate;
    $("btn-refresh-hist").onclick = () => {
      loadHistory().then(() => toast("历史已刷新"));
    };
  }

  function populateGenSubjects() {
    const sel = $("gen-subject-sel");
    const prev = parseInt(sel.value) || null;
    sel.innerHTML = '<option value="">自定义（手动输入）</option>' +
      state.subjects.map(s =>
        `<option value="${s.id}">[${esc(s.type)}] ${esc(s.name)}</option>`).join("");
    if (prev && state.subjects.some(s => s.id === prev)) sel.value = String(prev);
    onGenSubjectSelChange();
  }

  let prevSubjectId = null;
  function onGenSubjectSelChange() {
    const id = parseInt($("gen-subject-sel").value) || null;
    const keepCustom = prevSubjectId == null && id == null;
    prevSubjectId = id;
    if (id) {
      const s = state.subjects.find(x => x.id === id);
      if (s) $("gen-subject").value = s.description;
    } else if (!keepCustom) {
      $("gen-subject").value = "";
    }
  }

  function onGenStyleChange() {
    const style = currentGenStyle();
    if (!style) return;
    $("gen-scenario").innerHTML = style.scenarios.map(sc =>
      `<option value="${esc(sc.id)}">${esc(sc.label)}</option>`).join("");
    onGenScenarioChange();
  }

  function onGenScenarioChange() {
    const sc = currentGenScenario();
    if (!sc) {
      $("gen-template").innerHTML = '<option value="">该场景暂无创意模板</option>';
      $("gen-tpl-preview").textContent = "该场景暂无创意模板";
      return;
    }
    const tpls = sc.creative_copy || [];
    $("gen-template").innerHTML = tpls.length
      ? tpls.map(t => `<option value="${esc(t.label)}">${esc(t.label)}</option>`).join("")
      : '<option value="">该场景暂无创意模板</option>';
    onGenTemplateChange();
  }

  function onGenTemplateChange() {
    const tpl = currentTemplate();
    if (!tpl) { $("gen-tpl-preview").textContent = "该场景暂无创意模板"; return; }
    $("gen-tpl-preview").textContent = tpl.value;
    const sc = currentGenScenario();
    if (sc?.aspect_ratio) $("gen-ratio").value = sc.aspect_ratio;
  }

  async function runGenerate() {
    const body = {
      style_id: $("gen-style").value,
      scenario_id: $("gen-scenario").value,
      template_label: $("gen-template").value,
      subject: $("gen-subject").value.trim(),
      aspect_ratio: $("gen-ratio").value || null,
      subject_id: parseInt($("gen-subject-sel").value) || null,
    };
    if (!body.template_label || currentTemplate() == null) {
      return toast("该场景暂无创意模板", false);
    }
    if (!body.subject && !body.subject_id) {
      return toast("请选择主体或填写主体描述", false);
    }
    const reset = busy($("gen-go"), "生成中…");
    const scenario = currentGenScenario();
    sb.show(`LLM 按规范生成中：${scenario?.label || ""}`);
    try {
      const r = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { toast(d.detail || "生成失败", false); return; }
      const box = $("gen-result");
      box.innerHTML = "";
      box.appendChild(resultCard(d));
      box.hidden = false;
      sb.hide();
      $("gen-result").scrollIntoView({ behavior: "smooth", block: "start" });
      toast("生成完成");
      loadHistory();
    } catch (e) {
      toast(`生成失败：${e.message}`, false);
    } finally {
      reset();
    }
  }

  function resultCard(g) {
    const d = document.createElement("div");
    d.className = "card";
    d.innerHTML = `
      <div class="card-head">
        <span class="chip run">生成结果</span>
        ${g.subject_name ? `<span class="chip type-${typeKey(g.subject_type)}">${esc(g.subject_name)}</span>` : ""}
        <span class="chip ok">AR ${esc(g.aspect_ratio || "—")}</span>
        ${g.model ? `<span class="chip">${esc(g.model)}</span>` : ""}
      </div>
      <div class="field"><label>你的主体</label><div class="prompt prompt-sm">${esc(g.subject)}</div></div>
      <div class="field"><label>中文提示词</label><div class="prompt">${esc(g.prompt_zh)}</div></div>
      <div class="field"><label>英文提示词</label><div class="prompt">${esc(g.prompt_en)}</div></div>
      ${g.notes ? `<div class="field"><label>思路</label><div class="prompt prompt-sm">${esc(g.notes)}</div></div>` : ""}
      <div class="cc-actions">
        <button class="btn small" data-copy-zh>复制中文</button>
        <button class="btn small" data-copy-en>复制英文</button>
        <button class="btn small primary" data-copy-both>复制双语</button>
      </div>`;
    d.querySelector("[data-copy-zh]").onclick = () => copyText(g.prompt_zh);
    d.querySelector("[data-copy-en]").onclick = () => copyText(g.prompt_en);
    d.querySelector("[data-copy-both]").onclick = () => copyText(
      `【中文】\n${g.prompt_zh}\n\n【English】\n${g.prompt_en}`);
    return d;
  }

  function copyText(text) {
    navigator.clipboard.writeText(text).then(() => toast("已复制"),
      () => toast("复制失败", false));
  }

  async function loadHistory() {
    const r = await fetch("/api/generations?limit=30");
    state.genHistory = await r.json();
    const box = $("gen-history");
    box.innerHTML = "";
    if (!state.genHistory.length) {
      box.innerHTML = '<div class="meta" style="padding:14px">还没有生成记录</div>';
      return;
    }
    state.genHistory.forEach(g => {
      const item = document.createElement("div");
      item.className = "hist-row";
      item.setAttribute("role", "button");
      item.setAttribute("tabindex", "0");
      const subject = (g.subject || "");
      const subjShort = esc(subject.slice(0, 60)) + (subject.length > 60 ? "…" : "");
      item.innerHTML = `
        <div class="hist-time">${esc(fmtTime(g.created_at))}</div>
        <div class="hist-main">
          <div class="hist-line">
            ${g.subject_name ? `<span class="chip type-${typeKey(g.subject_type)}">${esc(g.subject_name)}</span>` : ""}
            <span>${subjShort}</span>
          </div>
          <div class="hist-meta">${esc(g.style_id)} / ${esc(g.scenario_id)} · ${esc(g.template_label)} · AR ${esc(g.aspect_ratio || "—")}${g.model ? ` · ${esc(g.model)}` : ""}</div>
        </div>`;
      item.onclick = () => {
        const box = $("gen-result");
        box.innerHTML = "";
        box.appendChild(resultCard(g));
        box.hidden = false;
        box.scrollIntoView({ behavior: "smooth", block: "start" });
      };
      item.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); item.onclick(); } };
      box.appendChild(item);
    });
  }

  /* ---------------- LLM 设置 ---------------- */
  const settingsModal = $("settings-modal");

  function openSettings() {
    settingsModal.hidden = false;
    resetLlmForm();
    loadLlmProfiles();
    settingsModal.querySelector("input")?.focus();
  }
  function closeSettings() { settingsModal.hidden = true; }

  async function loadLlmProfiles() {
    state.llm.profiles = await (await fetch("/api/llm/profiles")).json();
    const cur = await (await fetch("/api/llm/current")).json();
    state.llm.current = cur;
    renderLlmProfiles();
    $("llm-current").textContent = cur.source === "settings"
      ? `当前生效：配置「${cur.profile_name}」 · ${cur.model} · key ${cur.api_key_masked}`
      : `当前生效：.env / 环境变量 · ${cur.model} · key ${cur.api_key_masked}`;
    const gm = $("gen-current-model");
    if (gm) gm.textContent = `模型 ${cur.model || "—"}`;
  }

  function renderLlmProfiles() {
    const box = $("llm-profile-list");
    box.innerHTML = "";
    if (!state.llm.profiles.length) {
      box.innerHTML = '<div class="empty" style="padding:12px">暂无配置，使用 .env / 环境变量；在下方添加</div>';
      return;
    }
    state.llm.profiles.forEach(p => {
      const d = document.createElement("div");
      d.className = "llm-item" + (p.is_active ? " active" : "");
      d.innerHTML = `
        <div class="card-head">
          <span class="${p.is_active ? "chip ok" : "chip"}">${p.is_active ? "使用中" : "备用"}</span>
          <h3 style="font-size:14px">${esc(p.name)}</h3>
          <span class="spacer"></span>
          ${p.is_active ? "" : '<button class="btn small" data-act>设为使用</button>'}
          <button class="btn small" data-edit>编辑</button>
          <button class="btn small ghost danger" data-del>删除</button>
        </div>
        <div class="llm-meta">${esc(p.model)} · ${esc(p.base_url)} · key ${esc(p.api_key_masked)}</div>`;
      d.querySelector("[data-act]")?.addEventListener("click", async () => {
        const r = await fetch(`/api/llm/profiles/${p.id}/activate`, { method: "POST" });
        if (r.ok) { toast(`已切换为「${p.name}」`); loadLlmProfiles(); } else toast("切换失败", false);
      });
      d.querySelector("[data-edit]").addEventListener("click", () => {
        state.llm.editingId = p.id;
        $("llm-form-title").textContent = `编辑配置：${p.name}`;
        $("llm-name").value = p.name;
        $("llm-model").value = p.model;
        $("llm-base-url").value = p.base_url;
        $("llm-api-key").value = "";
        $("llm-save").textContent = "保存修改";
        $("llm-cancel-edit").hidden = false;
      });
      d.querySelector("[data-del]").addEventListener("click", async () => {
        const go = await confirmDialog({
          title: "删除配置", message: `删除配置「${p.name}」？`,
          confirmText: "删除", danger: true,
        });
        if (!go) return;
        const r = await fetch(`/api/llm/profiles/${p.id}`, { method: "DELETE" });
        if (r.ok) { toast("已删除"); loadLlmProfiles(); } else toast("删除失败", false);
      });
      box.appendChild(d);
    });
  }

  async function saveLlmProfile() {
    const body = {
      name: $("llm-name").value.trim(),
      base_url: $("llm-base-url").value.trim(),
      model: $("llm-model").value.trim(),
      api_key: $("llm-api-key").value.trim() || null,
    };
    const editing = state.llm.editingId;
    const reset = busy($("llm-save"), "保存中…");
    const r = await fetch(editing ? `/api/llm/profiles/${editing}` : "/api/llm/profiles", {
      method: editing ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    reset();
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return toast(d.detail || "保存失败", false);
    toast(editing ? "已保存" : "已添加并启用");
    resetLlmForm();
    loadLlmProfiles();
  }

  function resetLlmForm() {
    state.llm.editingId = null;
    $("llm-name").value = "";
    $("llm-model").value = "";
    $("llm-base-url").value = "";
    $("llm-api-key").value = "";
    $("llm-form-title").textContent = "添加配置";
    $("llm-save").textContent = "保存配置";
    $("llm-cancel-edit").hidden = true;
  }

  $("llm-save").onclick = saveLlmProfile;
  $("llm-cancel-edit").onclick = () => { resetLlmForm(); renderLlmProfiles(); };
  settingsModal.querySelector("[data-close]").onclick = closeSettings;
  settingsModal.addEventListener("click", e => { if (e.target === settingsModal) closeSettings(); });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !settingsModal.hidden) closeSettings();
  });

  /* ---------------- 抓取 / 补全 ---------------- */
  $("btn-scrape").onclick = async function () {
    const reset = busy(this, "抓取中…");
    try {
      const r = await fetch("/api/scrape", { method: "POST" });
      const d = await r.json().catch(() => ({}));
      if (r.ok) { toast(`已更新：${d.styles} styles / ${d.scenarios} 场景`); await refresh(); }
      else toast(`抓取失败：${d.detail || r.status}`, false);
    } catch (e) { toast(`抓取失败：${e.message}`, false); }
    finally { reset(); }
  };

  $("btn-enrich").onclick = async function () {
    const st = await (await fetch("/api/enrich/status")).json();
    if (st.running) { toast(`补全进行中 ${st.done}/${st.total}`, "run"); return watchEnrich(this); }
    const reset = busy(this, "启动中…");
    const r = await fetch("/api/enrich", { method: "POST" });
    const d = await r.json().catch(() => ({}));
    reset();
    if (!r.ok || d.ok === false) { toast(d.detail || "启动失败", false); return; }
    toast("LLM 补全已启动", "run");
    watchEnrich(this);
  };

  let enrichTimer = null;
  function watchEnrich(btn) {
    if (enrichTimer) return;
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "补全中…";
    enrichTimer = setInterval(async () => {
      let st;
      try { st = await (await fetch("/api/enrich/status")).json(); } catch { return; }
      const pct = st.total ? st.done / st.total : 0;
      const label = st.total ? `补全中 ${st.done}/${st.total}` : "补全中…";
      btn.textContent = label;
      sb.show(`LLM 补全：${label}`, pct);
      if (!st.running) {
        clearInterval(enrichTimer);
        enrichTimer = null;
        btn.disabled = false;
        btn.textContent = original;
        if (st.error) { toast(`补全失败：${st.error}`, false); sb.hide(); }
        else if (st.total) { toast(`补全完成 ${st.total - st.failed}/${st.total}`); sb.show(`补全完成 ${st.total - st.failed}/${st.total}`, 1); sb.clearSoon(); }
        else { toast("没有需要补全的数据"); sb.hide(); }
        await refresh();
      }
    }, 3000);
  }

  loadAppVersion();
  const initialView = ({ subj: "subj", gen: "gen" })[location.hash.replace("#", "")] || "browse";
  setView(initialView, false);
  init();
})();
