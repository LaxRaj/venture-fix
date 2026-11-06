(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const pct = new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: 1,
  });
  const dateTime = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZoneName: "short",
  });

  const state = {
    board: null,
    field: null,
    latest: null,
    filter: "all",
    view: "board",
    job: null,
    pollTimer: null,
  };

  /* DOM helpers ---------------------------------------------------------- */

  function h(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === null || value === undefined) continue;
      if (key === "class") node.className = value;
      else if (key === "dataset") Object.assign(node.dataset, value);
      else if (key === "style") node.setAttribute("style", value);
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else {
        node.setAttribute(key, value);
      }
    }
    append(node, children);
    return node;
  }

  function append(node, children) {
    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function show(node, visible) {
    if (node) node.hidden = !visible;
  }

  function text(value) {
    return document.createTextNode(value === null || value === undefined ? "—" : String(value));
  }

  function setChildren(node, children) {
    clear(node);
    append(node, children);
  }

  function metric(label, value) {
    return h(
      "div",
      { class: "metric" },
      h("span", { class: "metric-label" }, label),
      h("span", { class: "metric-value" }, value)
    );
  }

  function fmtP(value) {
    if (value === null || value === undefined) return "—";
    if (value < 0.001) return "<0.001";
    return Number(value).toFixed(3);
  }

  function fmtAuc(value) {
    return Number(value).toFixed(3);
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    const parsed = new Date(iso);
    return Number.isNaN(parsed.getTime()) ? "—" : dateTime.format(parsed);
  }

  function verdictClass(verdict) {
    if (verdict === "REACHABLE") return "reachable";
    if (verdict === "BURNS THE MARKET") return "burns";
    if (verdict === "DEAD ON ARITHMETIC") return "dead";
    return "";
  }

  function verdictBadge(verdict) {
    return h("span", { class: `verdict ${verdictClass(verdict)}` }, verdict);
  }

  function resultLabel(result) {
    if (result.survives) return "KEEP";
    if (result.raw_pass && !result.perm_pass) return "drop: chance";
    if (result.raw_pass && !result.bh_pass) return "drop: BH";
    if (result.raw_pass && !result.holdout_pass) return "drop: holdout";
    if (result.raw_pass) return "drop: gate";
    return "below raw AUC";
  }

  function resultClass(result) {
    if (result.survives) return "keep";
    if (result.raw_pass) return "drop";
    return "";
  }

  function provenanceChips(provenance) {
    return h(
      "div",
      { class: "provenance-chips" },
      h("span", { class: "provenance-chip" }, `price: ${provenance.price}`),
      h("span", { class: "provenance-chip" }, `hours: ${provenance.service_hours}`),
      h("span", { class: "provenance-chip" }, `buyers: ${provenance.buyers}`)
    );
  }

  async function getJSON(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (response.status === 204) return null;
    if (!response.ok) {
      let detail = "";
      try {
        const body = await response.json();
        detail = body.error || JSON.stringify(body);
      } catch (error) {
        detail = response.statusText;
      }
      throw new Error(`${response.status} ${detail}`.trim());
    }
    return response.json();
  }

  /* Tabs ----------------------------------------------------------------- */

  function activateView(name, updateHash = true) {
    if (!["board", "brief", "field", "calibration"].includes(name)) return;
    state.view = name;
    $$(".tab").forEach((tab) => {
      const active = tab.dataset.view === name;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    $$(".view").forEach((view) => {
      view.hidden = view.id !== `view-${name}`;
    });
    if (updateHash) {
      history.replaceState(null, "", `#${name}`);
    }
  }

  function initTabs() {
    const tabs = $$(".tab");
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => activateView(tab.dataset.view));
      tab.addEventListener("keydown", (event) => {
        const index = tabs.indexOf(tab);
        let next = null;
        if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
        if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = tabs.length - 1;
        if (next === null) return;
        event.preventDefault();
        tabs[next].focus();
        activateView(tabs[next].dataset.view);
      });
    });

    const hash = location.hash.replace("#", "");
    if (tabs.some((tab) => tab.dataset.view === hash)) {
      activateView(hash, false);
    }

    window.addEventListener("hashchange", () => {
      const next = location.hash.replace("#", "");
      if (next !== state.view) activateView(next, false);
    });
  }

  /* Board and brief ------------------------------------------------------ */

  async function loadBoard() {
    show($("#board-loading"), true);
    show($("#board-error"), false);
    show($("#board-content"), false);
    show($("#brief-loading"), true);
    show($("#brief-error"), false);
    show($("#brief-grid"), false);

    try {
      const data = await getJSON("/api/board");
      state.board = data;
      renderBoard(data);
      renderBrief(data);
      show($("#board-loading"), false);
      show($("#board-content"), true);
      show($("#brief-loading"), false);
      show($("#brief-grid"), true);
      $("#updated-line").textContent = `Updated ${fmtDate(data.generated_at)}`;
      $("#footer-updated").textContent = `Board generated ${fmtDate(data.generated_at)}`;
    } catch (error) {
      show($("#board-loading"), false);
      show($("#board-error"), true);
      show($("#brief-loading"), false);
      show($("#brief-error"), true);
      $("#board-error-text").textContent = error.message;
      $("#brief-error-text").textContent = error.message;
    }
  }

  function renderBoard(data) {
    setChildren($("#kpi-total"), [text(data.counts.total)]);
    setChildren($("#kpi-reachable"), [text(data.counts.REACHABLE)]);
    setChildren($("#kpi-burns"), [text(data.counts["BURNS THE MARKET"])]);
    setChildren($("#kpi-dead"), [text(data.counts["DEAD ON ARITHMETIC"])]);

    setChildren($("#count-all"), [text(data.counts.total)]);
    setChildren($("#count-reachable"), [text(data.counts.REACHABLE)]);
    setChildren($("#count-burns"), [text(data.counts["BURNS THE MARKET"])]);
    setChildren($("#count-dead"), [text(data.counts["DEAD ON ARITHMETIC"])]);

    renderBreakEvens(data.break_even);
    renderBoardRows();
  }

  function filteredRows() {
    if (!state.board) return [];
    if (state.filter === "all") return state.board.rows;
    return state.board.rows.filter((row) => row.verdict === state.filter);
  }

  function renderBoardRows() {
    const rows = filteredRows();
    const body = $("#board-body");
    const cards = $("#board-cards");
    clear(body);
    clear(cards);

    if (!rows.length) {
      const empty = h(
        "tr",
        {},
        h(
          "td",
          { colspan: "11" },
          h("div", { class: "state" }, h("p", {}, "No rows match this filter."))
        )
      );
      body.append(empty);
      cards.append(h("div", { class: "state" }, h("p", {}, "No rows match this filter.")));
      return;
    }

    for (const row of rows) {
      body.append(boardRow(row));
      cards.append(boardCard(row));
    }
  }

  function boardRow(row) {
    const provenanceTitle = [
      `price: ${row.provenance.price}`,
      `hours: ${row.provenance.service_hours}`,
      `buyers: ${row.provenance.buyers}`,
    ].join(" · ");

    return h(
      "tr",
      {},
      h(
        "td",
        { class: "venture-cell" },
        h("span", { class: "venture-name" }, row.name),
        h("span", { class: "venture-sub" }, `pool ${row.buyers_display}`)
      ),
      h("td", { class: "num" }, row.price_display),
      h(
        "td",
        {},
        h("abbr", { class: "prov", title: provenanceTitle }, row.provenance_code)
      ),
      h("td", { class: "num" }, `${row.hours_display}`),
      h("td", { class: "num" }, nf1.format(row.accounts_needed)),
      h("td", { class: "num" }, nf1.format(row.capacity)),
      h("td", { class: "num" }, nf0.format(row.contacts_needed)),
      h("td", { class: "num" }, row.buyers_display),
      h("td", {}, verdictBadge(row.verdict)),
      h("td", { class: "num" }, row.flip_display.service_hours),
      h("td", { class: "num" }, row.flip_display.price)
    );
  }

  function boardCard(row) {
    return h(
      "article",
      { class: "board-card" },
      h(
        "div",
        { class: "board-card-head" },
        h(
          "div",
          {},
          h("h3", {}, row.name),
          h("p", { class: "venture-sub" }, `pool ${row.buyers_display} buyers`)
        ),
        verdictBadge(row.verdict)
      ),
      h(
        "div",
        { class: "board-card-metrics" },
        metric("Price", row.price_display),
        metric("Service hours", `${row.hours_display} /acct/mo`),
        metric("Accounts needed", nf1.format(row.accounts_needed)),
        metric("Capacity", nf1.format(row.capacity)),
        metric("Contacts", nf0.format(row.contacts_needed)),
        metric("Market share", pct.format(row.market_share))
      ),
      h("p", { class: "board-card-cause" }, row.cause),
      h(
        "div",
        { class: "board-card-flips" },
        h("span", {}, `hrs flip `, h("strong", {}, row.flip_display.service_hours)),
        h("span", {}, `price flip `, h("strong", {}, row.flip_display.price))
      )
    );
  }

  function renderBreakEvens(items) {
    const grid = $("#break-even-grid");
    clear(grid);
    for (const item of items.slice(0, 4)) {
      grid.append(
        h(
          "div",
          { class: "break-even-card" },
          h("h4", {}, item.name),
          h(
            "div",
            { class: "break-even-row" },
            h("span", {}, "service hrs now → flips at"),
            h("strong", {}, item.hours)
          ),
          h(
            "div",
            { class: "break-even-row" },
            h("span", {}, "price now → flips at"),
            h("strong", {}, item.price)
          )
        )
      );
    }
  }

  function renderBrief(data) {
    const grid = $("#brief-grid");
    clear(grid);
    const rows = [...data.rows].sort((a, b) => a.closest.margin - b.closest.margin);

    for (const row of rows) {
      const margin = row.closest.margin;
      const fillClass = margin < 0.2 ? "is-critical" : margin < 0.35 ? "is-close" : "";
      grid.append(
        h(
          "article",
          { class: "venture-card" },
          h(
            "div",
            { class: "venture-card-head" },
            h(
              "div",
              {},
              h("h3", {}, row.name),
              h("p", { class: "venture-sub" }, `pool ${row.buyers_display} buyers`)
            ),
            verdictBadge(row.verdict)
          ),
          h("p", { class: "cause" }, row.cause),
          h(
            "ul",
            { class: "flip-list" },
            h(
              "li",
              {},
              h("span", {}, "Service hours"),
              h("span", {}, `${row.hours_display} → ${row.flip_display.service_hours}`)
            ),
            h(
              "li",
              {},
              h("span", {}, "Price"),
              h("span", {}, `${row.price_display} → ${row.flip_display.price}`)
            ),
            h(
              "li",
              {},
              h("span", {}, "Buyer pool"),
              h("span", {}, `${row.buyers_display} → ${row.flip_display.buyers}`)
            )
          ),
          h(
            "div",
            { class: "nearest" },
            h(
              "div",
              { class: "nearest-line" },
              h("span", {}, `Nearest: ${row.closest.label}`),
              h("strong", {}, `${pct.format(margin)} from flip`)
            ),
            h(
              "div",
              { class: "fragility-track" },
              h("div", {
                class: `fragility-fill ${fillClass}`,
                style: `width: ${Math.min(100, Math.max(4, margin * 100))}%`,
              })
            ),
            h(
              "div",
              { class: "nearest-line" },
              h("span", {}, `${row.closest.calls} field calls`),
              h("span", {}, "declared heuristic")
            )
          ),
          provenanceChips(row.provenance)
        )
      );
    }
  }

  /* Field ---------------------------------------------------------------- */

  async function loadField() {
    show($("#field-loading"), true);
    show($("#field-error"), false);
    show($("#field-list"), false);
    try {
      const data = await getJSON("/api/field");
      state.field = data;
      renderField(data);
      show($("#field-loading"), false);
      show($("#field-list"), true);
    } catch (error) {
      show($("#field-loading"), false);
      show($("#field-error"), true);
      $("#field-error-text").textContent = error.message;
    }
  }

  function renderField(data) {
    const list = $("#field-list");
    clear(list);
    for (const item of data.items) {
      const details = h(
        "details",
        { class: "call-script" },
        h("summary", {}, "Six questions, none of them a pitch"),
        h(
          "ol",
          {},
          item.questions.map((question) =>
            h(
              "li",
              {},
              question.question,
              h("small", {}, `→ ${question.note}`)
            )
          )
        )
      );

      list.append(
        h(
          "article",
          { class: `field-item ${item.rank === 1 ? "is-top" : ""}` },
          h("span", { class: "rank" }, `#${item.rank}`),
          h(
            "div",
            { class: "field-body" },
            h(
              "div",
              { class: "field-head" },
              h(
                "div",
                {},
                h("h3", {}, item.name),
                item.rank === 1
                  ? h("span", { class: "field-top-tag" }, "Most fragile number")
                  : null
              ),
              verdictBadge(item.verdict)
            ),
            h("div", { class: "measure-label" }, item.input_label),
            h(
              "div",
              { class: "value-pair" },
              h("span", { class: "now" }, item.current_display),
              h("span", { class: "arrow" }, "→"),
              h("span", { class: "flip" }, item.flip_display)
            ),
            h(
              "div",
              { class: "field-meta" },
              h("span", {}, "margin ", h("strong", {}, pct.format(item.margin))),
              h("span", {}, "calls ", h("strong", {}, String(item.calls))),
              h("span", {}, `price ${item.provenance.price}`),
              h("span", {}, `hours ${item.provenance.service_hours}`),
              h("span", {}, `buyers ${item.provenance.buyers}`)
            ),
            details
          )
        )
      );
    }
  }

  /* Calibration ---------------------------------------------------------- */

  function setStatus(kind, message, progress = null) {
    const dot = $("#status-dot");
    dot.className = "status-dot";
    if (kind) dot.classList.add(`is-${kind}`);
    $("#status-text").textContent = message;
    const bar = $("#progress-bar");
    if (progress === null) {
      bar.style.width = kind === "done" ? "100%" : "0%";
    } else {
      bar.style.width = `${Math.round(Math.max(0, Math.min(1, progress)) * 100)}%`;
    }
  }

  function setBusy(busy) {
    const button = $("#run-button");
    button.disabled = busy;
    $("#provider-select").disabled = busy;
    $("#permutations").disabled = busy;
    button.textContent = busy ? "Running…" : "Run calibration";
  }

  function statusRunning(job) {
    const progress = job.progress || { current: 0, total: 1, venture: "" };
    const current = Number(progress.current || 0);
    const total = Number(progress.total || 1);
    const label = job.provider === "jev" ? "Jev" : job.provider === "stub" ? "Stub" : "Model";
    const suffix = progress.venture ? ` · ${progress.venture}` : "";
    setStatus(
      "running",
      `Running ${label} · venture ${current} of ${total}${suffix}`,
      total ? current / total : 0
    );
  }

  function statusDone(result) {
    const label = result.provider === "jev" ? "Jev" : result.provider === "stub" ? "Stub" : "Model";
    setStatus(
      "done",
      `Last run: ${label} · ${fmtDate(result.generated_at)} · ${result.labels.total} ventures`,
      1
    );
  }

  function statusError(message) {
    setStatus("error", `Run failed · ${message}`, 0);
  }

  function updateKeptKpi(result) {
    const total = result.results.length;
    $("#kpi-kept").textContent = `${result.summary.kept} / ${total}`;
    const provider = result.provider === "jev" ? "Jev" : result.provider;
    $("#kpi-kept-note").textContent =
      result.summary.kept > 0
        ? `${provider} · trusted on the fixture`
        : `${provider} · nothing trusted yet`;
  }

  async function loadLatest() {
    try {
      const latest = await getJSON("/api/calibration/latest");
      if (!latest) {
        show($("#calibration-empty"), true);
        show($("#calibration-content"), false);
        show($("#calibration-error"), false);
        setStatus("", "No run yet · choose a provider and run", 0);
        return;
      }
      state.latest = latest;
      renderCalibration(latest);
      statusDone(latest);
      updateKeptKpi(latest);
    } catch (error) {
      show($("#calibration-empty"), false);
      show($("#calibration-content"), false);
      show($("#calibration-error"), true);
      $("#calibration-error-text").textContent = error.message;
      statusError(error.message);
    }
  }

  function renderCalibration(result) {
    show($("#calibration-empty"), false);
    show($("#calibration-error"), false);
    show($("#calibration-content"), true);

    renderFunnel(result);
    renderCalibrationMeta(result);
    renderCalibrationRows(result);
    renderSweep(result);
    renderCoverage(result);
    $("#report-text").textContent = result.report_text || "No report text was returned.";
    $("#footer-updated").textContent = `Calibration ${result.provider} · ${fmtDate(result.generated_at)}`;
  }

  function renderFunnel(result) {
    const gates = result.gates;
    const stages = [
      {
        value: result.summary.raw,
        label: "Raw AUC",
        sub: `≥ ${Number(gates.raw_cutoff).toFixed(2)}`,
      },
      {
        value: result.summary.permutation,
        label: "Permutation",
        sub: `p ≤ ${gates.permutation_cutoff}`,
      },
      {
        value: result.summary.bh,
        label: "BH control",
        sub: `q = ${gates.bh_q}`,
      },
      {
        value: result.summary.kept,
        label: "Trusted",
        sub: `holdout ≥ ${Number(gates.holdout_cutoff).toFixed(2)}`,
      },
    ];

    const funnel = $("#gate-funnel");
    clear(funnel);
    for (const stage of stages) {
      funnel.append(
        h(
          "div",
          { class: "funnel-stage" },
          h("span", { class: "funnel-value" }, String(stage.value)),
          h("span", { class: "funnel-label" }, stage.label),
          h("span", { class: "funnel-sub" }, stage.sub)
        )
      );
    }
  }

  function metaItem(label, value, mono = false) {
    return h(
      "div",
      { class: "meta-item" },
      h("dt", {}, label),
      h("dd", { class: mono ? "mono" : "" }, value)
    );
  }

  function renderCalibrationMeta(result) {
    const meta = $("#calib-meta");
    clear(meta);
    const bank = result.bank || {};
    const labels = result.labels || {};
    meta.append(
      metaItem("Provider", `${result.provider} · ${result.provider_stamp || "no stamp"}`),
      metaItem("Labels", `${labels.total} ventures · ${labels.alive} alive / ${labels.dead} dead`),
      metaItem("Split seed", String(result.split_seed), true),
      metaItem("Question bank", `${bank.admitted} admitted · ${bank.rejected_examples} rejected at import`),
      metaItem("Leakage check", result.leakage_check || "PASS"),
      metaItem("Permutations", String(result.permutations), true)
    );
    if (result.stub_verdict) {
      meta.append(metaItem("Stub verdict", result.stub_verdict));
    }
  }

  function renderCalibrationRows(result) {
    const body = $("#calib-body");
    clear(body);
    const cutoff = Number(result.gates.raw_cutoff);

    for (const row of result.results) {
      const auc = Number(row.discovery_auc);
      const fill = h("span", {
        class: `auc-fill ${auc >= cutoff ? "pass" : ""}`,
        style: `width: ${Math.max(0, Math.min(1, auc)) * 100}%`,
      });

      body.append(
        h(
          "tr",
          { class: row.survives ? "is-keep" : "" },
          h("td", {}, h("span", { class: "venture-name" }, row.id)),
          h("td", {}, row.family),
          h("td", {}, row.maps_to || "diagnostic"),
          h(
            "td",
            { class: "num" },
            h(
              "div",
              { class: "auc-cell" },
              h("span", { class: "auc-track" }, fill),
              h("span", {}, fmtAuc(auc))
            )
          ),
          h("td", { class: "num" }, fmtP(row.p_value)),
          h("td", { class: "num" }, fmtP(row.bh_adjusted)),
          h("td", { class: "num" }, fmtAuc(row.holdout_auc)),
          h(
            "td",
            {},
            h(
              "span",
              { class: `result-badge ${resultClass(row)}` },
              resultLabel(row)
            )
          )
        )
      );
    }
  }

  function renderSweep(result) {
    const body = $("#sweep-body");
    clear(body);
    const cutoff = Number(result.gates.raw_cutoff);
    for (const item of result.threshold_sweep) {
      const isCutoff = Math.abs(Number(item.cutoff) - cutoff) < 1e-9;
      body.append(
        h(
          "tr",
          { class: isCutoff ? "is-cutoff" : "" },
          h("td", {}, Number(item.cutoff).toFixed(2)),
          h("td", { class: "num" }, String(item.raw)),
          h("td", { class: "num" }, String(item.final))
        )
      );
    }
  }

  function renderCoverage(result) {
    const list = $("#coverage-list");
    clear(list);
    const order = [
      "buyer",
      "pain",
      "supply",
      "workflow",
      "access",
      "data or workflow moat",
    ];
    const labels = {
      buyer: "Buyer",
      pain: "Pain",
      supply: "Supply",
      workflow: "Workflow",
      access: "Access",
      "data or workflow moat": "Data or workflow moat",
    };

    for (const family of order) {
      const count = Number(result.coverage[family] || 0);
      const uncovered = family === "data or workflow moat";
      list.append(
        h(
          "li",
          { class: `coverage-item ${uncovered ? "is-uncovered" : ""}` },
          h("span", {}, labels[family]),
          h("span", {}, uncovered ? "UNCOVERED" : `${count} questions`)
        )
      );
    }
  }

  async function startRun() {
    const provider = $("#provider-select").value;
    const permutations = Number($("#permutations").value);

    if (!Number.isInteger(permutations) || permutations < 99 || permutations > 9999) {
      showCalibrationError("Permutations must be a whole number between 99 and 9999.");
      return;
    }

    setBusy(true);
    show($("#calibration-error"), false);
    setStatus("running", `Starting ${provider} calibration…`, 0);

    try {
      const response = await fetch("/api/calibrate", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ provider, permutations }),
      });
      if (!response.ok) {
        let message = `HTTP ${response.status}`;
        try {
          const body = await response.json();
          if (body.error) message = body.error;
        } catch (error) {
          message = response.statusText || message;
        }
        throw new Error(message);
      }
      const job = await response.json();
      state.job = job;
      statusRunning(job);
      pollJob(job.id);
    } catch (error) {
      setBusy(false);
      showCalibrationError(error.message);
    }
  }

  function pollJob(jobId) {
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }

    const tick = async () => {
      try {
        const job = await getJSON(`/api/calibration/jobs/${jobId}`);
        state.job = job;
        if (job.status === "queued" || job.status === "running") {
          statusRunning(job);
          state.pollTimer = setTimeout(tick, 900);
          return;
        }
        if (job.status === "done") {
          setBusy(false);
          state.latest = job.result;
          renderCalibration(job.result);
          statusDone(job.result);
          updateKeptKpi(job.result);
          return;
        }
        setBusy(false);
        showCalibrationError(job.error || "The calibration run failed.");
      } catch (error) {
        setBusy(false);
        showCalibrationError(error.message);
      }
    };

    tick();
  }

  function showCalibrationError(message) {
    show($("#calibration-error"), true);
    $("#calibration-error-text").textContent = message;
    if (!state.latest) {
      show($("#calibration-empty"), false);
      show($("#calibration-content"), false);
    }
    statusError(message);
    setBusy(false);
  }

  /* Wiring --------------------------------------------------------------- */

  function bindFilters() {
    $$("#board-filters .chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        state.filter = chip.dataset.filter;
        $$("#board-filters .chip").forEach((other) => {
          other.setAttribute("aria-pressed", String(other === chip));
        });
        renderBoardRows();
      });
    });
  }

  function bindRetries() {
    $("#board-retry").addEventListener("click", loadBoard);
    $("#brief-retry").addEventListener("click", loadBoard);
    $("#field-retry").addEventListener("click", loadField);
    $("#calibration-retry").addEventListener("click", startRun);
  }

  function bindRunForm() {
    $("#run-form").addEventListener("submit", (event) => {
      event.preventDefault();
      startRun();
    });
  }

  function init() {
    initTabs();
    bindFilters();
    bindRetries();
    bindRunForm();
    loadBoard();
    loadField();
    loadLatest();
  }

  init();
})();
