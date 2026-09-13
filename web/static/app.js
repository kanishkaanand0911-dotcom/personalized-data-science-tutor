/* AutoTriage-Clean - single-page frontend.
   The agent's decisions come from the backend. This file collects a guess,
   sends it, and shows what the agent actually did. A guess never changes the
   pipeline result. */

(() => {
  "use strict";

  const app = document.getElementById("app");
  const MASCOT = "/assets/mascot.svg";
  // Placeholder name. Swap this one line when the real product name is decided.
  const APP_NAME = "Data Agent";

  const store = {
    get sid() {
      return sessionStorage.getItem("atc_sid") || "";
    },
    set sid(v) {
      sessionStorage.setItem("atc_sid", v);
    },
    clear() {
      sessionStorage.removeItem("atc_sid");
    },
  };

  const state = {
    profile: { role: null, experience: null },
    dataset: null,
    roadmap: null,
    levels: null,
    guesses: {}, // id -> { choice_id, correct, points_awarded, attempts, agent_choice, resolved }
    verify: null,
    model: null,
    results: null,
  };

  // ---------------------------------------------------------------- api

  async function api(path, opts = {}) {
    const headers = Object.assign({}, opts.headers || {});
    if (store.sid) headers["X-Session-Id"] = store.sid;
    if (opts.json !== undefined) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
    }
    const res = await fetch(path, { ...opts, headers });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      /* non-json */
    }
    if (!res.ok) {
      const msg = (data && data.error) || `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  // ---------------------------------------------------------------- helpers

  const h = (tag, attrs = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "html") el.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (k.startsWith("aria-")) el.setAttribute(k, String(v));
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
  };

  const mount = (node) => {
    app.replaceChildren(node);
    window.scrollTo(0, 0);
  };

  const icon = {
    arrow: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    back: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M11 18l-6-6 6-6"/></svg>',
    up: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V7M6 13l6-6 6 6M5 21h14"/></svg>',
    star: '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 17l-5.3 2.6 1-5.8L3.5 9.7l5.9-.9z"/></svg>',
    check: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12l5 5L20 6"/></svg>',
    cross: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  };

  const loading = (msg) =>
    mount(h("div", { class: "loading" }, h("div", { class: "spinner" }), h("p", {}, msg)));

  const errorScreen = (err, retryHash) =>
    mount(
      h(
        "div",
        { class: "screen" },
        h("h2", {}, "Something went wrong"),
        h("div", { class: "error-box" }, err.message || String(err)),
        h(
          "div",
          { style: "margin-top:20px;display:flex;gap:12px" },
          h("button", { class: "btn btn-ghost", onclick: () => (location.hash = retryHash || "#/") }, "Go back"),
        ),
      ),
    );

  const go = (hash) => {
    if (location.hash === hash) render();
    else location.hash = hash;
  };

  // ---------------------------------------------------------------- onboarding

  function screenOnboarding() {
    const roles = ["Sales", "Operations", "HR", "Student"];
    const exp = ["New to this", "Know the basics", "Pretty confident"];
    let custom = "";

    const rerender = () => mount(view());

    const pickRole = (r) => {
      state.profile.role = r;
      custom = "";
      rerender();
    };
    const pickExp = (e) => {
      state.profile.experience = e;
      rerender();
    };

    const submit = async () => {
      const btn = document.getElementById("onb-continue");
      btn.disabled = true;
      btn.textContent = "One moment";
      try {
        const role = state.profile.role === "__custom__" ? custom.trim().toLowerCase() : (state.profile.role || "").toLowerCase();
        const data = await api("/api/session", {
          method: "POST",
          json: { role: role || null, experience: state.profile.experience },
        });
        store.sid = data.session_id;
        go("#/dataset");
      } catch (e) {
        errorScreen(e, "#/");
      }
    };

    function view() {
      const ready =
        (state.profile.role === "__custom__" ? custom.trim().length > 0 : !!state.profile.role) &&
        !!state.profile.experience;

      return h(
        "div",
        { class: "onb" },
        h(
          "div",
          { class: "onb-left" },
          h("span", { class: "onb-kicker" }, APP_NAME),
          h("h1", {}, "Let's get to know you first"),
          h(
            "p",
            { class: "onb-sub" },
            "Not a real account and nothing to remember. This just changes how each idea gets explained to you.",
          ),
          h(
            "div",
            { class: "qgroup" },
            h("h3", {}, "What kind of work do you do?"),
            h(
              "div",
              { class: "chips" },
              roles.map((r) =>
                h(
                  "button",
                  { class: "chip", "aria-pressed": state.profile.role === r, onclick: () => pickRole(r) },
                  r,
                ),
              ),
              h("input", {
                class: "chip-input",
                placeholder: "Add your own",
                value: custom,
                oninput: (ev) => {
                  custom = ev.target.value;
                  state.profile.role = "__custom__";
                  const b = document.getElementById("onb-continue");
                  if (b) b.disabled = !(custom.trim() && state.profile.experience);
                  document.querySelectorAll(".chips .chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
                },
              }),
            ),
          ),
          h(
            "div",
            { class: "qgroup" },
            h("h3", {}, "How much data work have you done before?"),
            h(
              "div",
              { class: "chips" },
              exp.map((e) =>
                h(
                  "button",
                  { class: "chip", "aria-pressed": state.profile.experience === e, onclick: () => pickExp(e) },
                  e,
                ),
              ),
            ),
          ),
          h(
            "div",
            { class: "onb-cta" },
            h(
              "button",
              { id: "onb-continue", class: "btn btn-primary", disabled: !ready, onclick: submit },
              "Continue ",
              h("span", { html: icon.arrow }),
            ),
          ),
        ),
        h(
          "div",
          { class: "onb-right" },
          h("span", { class: "onb-shape ring" }),
          h("span", { class: "onb-shape dot" }),
          h("span", { class: "onb-shape square" }),
          h("span", { class: "onb-shape tri" }),
          h("img", { class: "onb-mascot", src: MASCOT, alt: "" }),
          h("span", { class: "speech" }, "let's take a look at your data"),
        ),
      );
    }

    rerender();
  }

  // ---------------------------------------------------------------- dataset

  function screenDataset() {
    if (!store.sid) return go("#/");
    let file = null;

    const submit = async (useSample) => {
      loading(useSample ? "Loading the sample and finding what needs fixing" : "Reading your file and finding what needs fixing");
      try {
        const fd = new FormData();
        if (useSample) fd.append("use_sample", "true");
        else fd.append("file", file);
        const data = await api("/api/dataset", { method: "POST", body: fd });
        state.dataset = data.dataset;
        state.roadmap = data.roadmap;
        state.levels = data.levels;
        state.guesses = {};
        state.verify = state.model = state.results = null;
        go("#/roadmap");
      } catch (e) {
        errorScreen(e, "#/dataset");
      }
    };

    const view = h(
      "div",
      { class: "screen" },
      h(
        "div",
        { class: "head" },
        h("img", { class: "head-mascot", src: MASCOT, alt: "" }),
        h(
          "div",
          {},
          h("h1", {}, "Bring in some data"),
          h(
            "p",
            { class: "lead" },
            "The agent will fix what is broken, check the result works, and fit a model to it. Use your own CSV, or start with the sample sales file.",
          ),
        ),
      ),
      h(
        "div",
        { class: "pick-grid" },
        h(
          "div",
          { class: "pick" },
          h("h3", {}, "Your own CSV"),
          h("p", {}, "A messy export is fine. That is the point."),
          (() => {
            const dz = h(
              "label",
              { class: "dropzone" },
              h("span", { html: icon.up }),
              h("div", {}, h("strong", {}, "Choose a file"), " or drop it here"),
              h("input", {
                type: "file",
                accept: ".csv,text/csv",
                hidden: true,
                onchange: (ev) => {
                  file = ev.target.files[0] || null;
                  nameEl.textContent = file ? file.name : "";
                  goBtn.disabled = !file;
                },
              }),
            );
            const nameEl = h("div", { class: "file-name" });
            const goBtn = h(
              "button",
              { class: "btn btn-berry", disabled: true, onclick: () => file && submit(false) },
              "Use this file ",
              h("span", { html: icon.arrow }),
            );
            dz.addEventListener("dragover", (e) => {
              e.preventDefault();
              dz.classList.add("hot");
            });
            dz.addEventListener("dragleave", () => dz.classList.remove("hot"));
            dz.addEventListener("drop", (e) => {
              e.preventDefault();
              dz.classList.remove("hot");
              file = e.dataTransfer.files[0] || null;
              nameEl.textContent = file ? file.name : "";
              goBtn.disabled = !file;
            });
            return h("div", {}, dz, nameEl, h("div", { style: "margin-top:14px" }, goBtn));
          })(),
        ),
        h(
          "div",
          { class: "pick" },
          h("h3", {}, "Sample sales dataset"),
          h("p", {}, "350 rows with missing deal values, three spellings of the same city, dollar amounts stored as text, and mixed date formats."),
          h(
            "div",
            { style: "margin-top:auto" },
            h(
              "button",
              { class: "btn btn-ghost", onclick: () => submit(true) },
              "Use the sample ",
              h("span", { html: icon.arrow }),
            ),
          ),
        ),
      ),
    );
    mount(view);
  }

  // ---------------------------------------------------------------- roadmap

  function screenRoadmap() {
    if (!state.roadmap) return go("#/dataset");
    const nodes = state.roadmap.nodes;
    const view = h(
      "div",
      { class: "screen" },
      h(
        "div",
        { class: "head" },
        h("img", { class: "head-mascot", src: MASCOT, alt: "" }),
        h(
          "div",
          {},
          h("h1", {}, "Since it is your data, here is your path"),
          h(
            "p",
            { class: "lead" },
            `Built from what is actually in ${state.roadmap.dataset_name}. Different data would give a different path.`,
          ),
        ),
      ),
      h(
        "div",
        { class: "path" },
        nodes.map((n, i) =>
          h(
            "div",
            { class: "path-node" + (i === 0 ? " current" : "") },
            h("div", { class: "node-dot" }, i === 0 ? "1" : String(i + 1)),
            h("div", { class: "node-title" }, n.title),
            h("div", { class: "node-detail" }, n.detail),
          ),
        ),
      ),
      h(
        "div",
        {},
        state.levels.length
          ? h(
              "button",
              { class: "btn btn-berry", onclick: () => go("#/level/0") },
              "Start cleaning ",
              h("span", { html: icon.arrow }),
            )
          : h(
              "button",
              { class: "btn btn-berry", onclick: () => go("#/verify") },
              "Nothing to clean, check the data ",
              h("span", { html: icon.arrow }),
            ),
      ),
    );
    mount(view);
  }

  // ---------------------------------------------------------------- rail

  function railSteps(activeKind, activeIndex) {
    const steps = state.levels.map((lv, i) => ({
      label: lv.title,
      kind: "level",
      i,
      done: !!state.guesses[lv.id],
    }));
    steps.push({ label: "Verification", kind: "verify", done: !!state.verify });
    steps.push({ label: "Modeling", kind: "model", done: !!state.model });
    steps.push({ label: "Results", kind: "results", done: !!state.results });

    return h(
      "nav",
      { class: "rail" },
      h("div", { class: "rail-title" }, "Your path"),
      steps.map((s) => {
        const active = s.kind === activeKind && (s.kind !== "level" || s.i === activeIndex);
        const cls = "rail-item" + (active ? " active" : "") + (s.done && !active ? " done" : "");
        return h(
          "div",
          { class: cls },
          h("span", { class: "rail-mark", html: s.done && !active ? icon.check : "" }, s.done && !active ? "" : ""),
          s.label,
        );
      }),
    );
  }

  // ---------------------------------------------------------------- level

  function screenLevel(idx) {
    if (!state.levels) return go("#/dataset");
    if (idx < 0 || idx >= state.levels.length) return go("#/verify");
    const level = state.levels[idx];
    const existing = state.guesses[level.id];
    let choice = existing ? existing.choice_id : null;

    const total = state.levels.length;
    const doneCount = Object.keys(state.guesses).length;

    const lock = async () => {
      const btn = document.getElementById("lock-btn");
      btn.disabled = true;
      btn.textContent = "Running the agent";
      try {
        const data = await api(`/api/levels/${level.id}/guess`, { method: "POST", json: { choice_id: choice } });
        state.guesses[level.id] = { choice_id: choice, ...data };
        render();
      } catch (e) {
        errorScreen(e, `#/level/${idx}`);
      }
    };

    const pointsBadge = h(
      "span",
      { class: "points-badge" },
      h("span", { html: icon.star }),
      `${currentPoints()} points`,
    );

    const top = h(
      "div",
      { class: "level-top" },
      h(
        "div",
        {},
        h(
          "button",
          { class: "btn btn-back", onclick: () => go(idx === 0 ? "#/roadmap" : `#/level/${idx - 1}`) },
          h("span", { html: icon.back }),
          " Back",
        ),
        h("div", { class: "level-label" }, `Level ${idx + 1} of ${total} - Cleaning`),
        h("div", { class: "level-col" }, level.column),
      ),
      pointsBadge,
    );

    const progress = h(
      "div",
      { class: "progress" },
      h("span", { style: `width:${Math.round((doneCount / total) * 100)}%` }),
    );

    let body;
    if (!existing) {
      body = h(
        "div",
        {},
        h(
          "div",
          { class: "talk" },
          h("img", { src: MASCOT, alt: "" }),
          h(
            "div",
            {},
            h("strong", {}, level.title + " in " + level.column + ". "),
            h("p", {}, level.analogy),
          ),
        ),
        h("div", { class: "guess-q" }, level.question),
        h(
          "div",
          { class: "options" },
          level.options.map((o) =>
            h(
              "button",
              {
                class: "option",
                "aria-pressed": choice === o.id,
                onclick: () => {
                  choice = o.id;
                  document.querySelectorAll(".options .option").forEach((el, i) =>
                    el.setAttribute("aria-pressed", level.options[i].id === choice),
                  );
                  document.getElementById("lock-btn").disabled = false;
                },
              },
              h("div", { class: "opt-label" }, o.label),
              o.blurb ? h("div", { class: "opt-blurb" }, o.blurb) : null,
            ),
          ),
        ),
        h(
          "div",
          { class: "level-actions" },
          h(
            "button",
            { id: "lock-btn", class: "btn btn-berry", disabled: !choice, onclick: lock },
            "Lock in my guess",
          ),
          h("span", { style: "color:var(--ink-soft);font-size:.88rem" }, "The agent decides on its own. Your guess is just scored."),
        ),
      );
    } else {
      body = revealBlock(level, idx, existing);
    }

    mount(
      h(
        "div",
        { class: "screen" },
        h("div", { class: "level-shell" }, railSteps("level", idx), h("div", {}, top, progress, body)),
      ),
    );
  }

  function revealBlock(level, idx, g) {
    const hit = g.correct;
    const nextIdx = g.next_level;
    const cards = g.attempts.map((a) => {
      const mine =
        (level.guess_kind === "which_strategy" && a.strategy === g.your_choice) ||
        (level.guess_kind === "pass_fail");
      const tags = [
        h("span", { class: "tag " + (a.passed ? "kept" : "discarded") }, a.passed ? "kept" : "discarded"),
      ];
      if (level.guess_kind === "which_strategy" && a.strategy === g.your_choice)
        tags.push(h("span", { class: "tag mine" }, "your guess"));
      const stats = [];
      if (a.before && a.before.skew != null && a.after && a.after.skew != null)
        stats.push(h("span", {}, `skew ${a.before.skew} to ${a.after.skew}`));
      if (a.before && a.before.null_pct != null && a.after)
        stats.push(h("span", {}, `blanks ${a.before.null_pct}% to ${a.after.null_pct}%`));
      if (a.before && a.before.unique_count != null && a.after && a.after.unique_count !== a.before.unique_count)
        stats.push(h("span", {}, `labels ${a.before.unique_count} to ${a.after.unique_count}`));
      return h(
        "div",
        { class: "attempt " + (a.passed ? "kept-row" : "rejected") },
        h("div", { class: "attempt-head" }, h("span", { class: "attempt-name" }, a.label), tags),
        h("p", { class: "attempt-reason" }, a.reason),
        stats.length ? h("div", { class: "attempt-stats" }, stats) : null,
      );
    });

    return h(
      "div",
      { class: "reveal-in" },
      h(
        "div",
        { class: "talk" },
        h("img", { src: MASCOT, alt: "" }),
        h(
          "div",
          {},
          h(
            "p",
            {},
            hit
              ? "Good call. Here is what the agent actually did."
              : "Not this time. Here is what the agent actually did.",
          ),
        ),
      ),
      h(
        "div",
        { class: "verdict " + (hit ? "hit" : "miss") },
        h("span", { html: hit ? icon.check : icon.cross }),
        hit ? "You guessed right" : "You guessed wrong",
      ),
      h("div", {}, cards),
      !g.resolved
        ? h(
            "div",
            { class: "error-box", style: "border-color:var(--gold);background:#fff5da;color:#7a5a06" },
            "Every strategy for this column failed its check, so the agent flagged it for a human. That is the honest-failure path, not a bug.",
          )
        : null,
      h("div", { class: "earn" }, h("span", { html: icon.star }), `+${g.points_awarded} points`),
      h(
        "div",
        { class: "level-actions" },
        h(
          "button",
          {
            class: "btn btn-berry",
            onclick: () => go(nextIdx != null ? `#/level/${nextIdx}` : "#/verify"),
          },
          nextIdx != null ? "Next level " : "Check the data works ",
          h("span", { html: icon.arrow }),
        ),
      ),
    );
  }

  function currentPoints() {
    return Object.values(state.guesses).reduce((s, g) => s + (g.points_awarded || 0), 0);
  }

  // ---------------------------------------------------------------- verify

  async function screenVerify() {
    if (!state.levels) return go("#/dataset");
    if (!state.verify) {
      loading("Checking the cleaned data can actually be used");
      try {
        state.verify = await api("/api/verify");
      } catch (e) {
        return errorScreen(e, "#/roadmap");
      }
    }
    const v = state.verify;
    const view = h(
      "div",
      { class: "screen" },
      h(
        "div",
        { class: "level-shell" },
        railSteps("verify"),
        h(
          "div",
          {},
          h("div", { class: "level-label" }, "Verification"),
          h("h1", {}, v.overall_passed ? "The cleaned data holds up" : "Some checks did not pass"),
          h(
            "p",
            { class: "lead" },
            "A column can look clean and still break a real task. The agent runs the tasks a learner would actually try next.",
          ),
          v.checks.map((c) =>
            h(
              "div",
              { class: "check " + (c.passed ? "pass" : "fail") },
              h("span", { class: "mark", html: c.passed ? icon.check : icon.cross }),
              h(
                "div",
                {},
                h("div", { class: "check-name" }, c.label),
                h("div", { class: "check-reason" }, c.reason),
                c.preview
                  ? h(
                      "div",
                      { class: "check-preview" },
                      Object.entries(c.preview)
                        .map(([k, val]) => `${k}: ${val}`)
                        .join("   "),
                    )
                  : null,
              ),
            ),
          ),
          h(
            "div",
            { class: "level-actions" },
            h(
              "button",
              { class: "btn btn-berry", onclick: () => go("#/model") },
              "On to modeling ",
              h("span", { html: icon.arrow }),
            ),
          ),
        ),
      ),
    );
    mount(view);
  }

  // ---------------------------------------------------------------- model

  async function screenModel() {
    if (!state.levels) return go("#/dataset");
    if (!state.model) {
      loading("Fitting models and checking which one actually fits");
      try {
        state.model = await api("/api/model");
      } catch (e) {
        return errorScreen(e, "#/verify");
      }
    }
    const m = state.model;
    let inner;
    if (!m.available) {
      inner = h(
        "div",
        {},
        h("h1", {}, "Modeling was skipped for this data"),
        h("p", { class: "lead" }, m.reason),
      );
    } else {
      inner = h(
        "div",
        {},
        h("div", { class: "level-label" }, "Modeling"),
        h("h1", {}, `Predicting ${m.target}`),
        h(
          "div",
          { class: "observe" },
          h("b", {}, "What the agent observed. "),
          `${m.observation.n_samples} rows, ${m.observation.n_features} features, and a ${m.observation.linearity_signal} straight-line signal (strongest correlation ${m.observation.max_abs_correlation}). ${m.start_reason}`,
        ),
        m.attempts.map((a) =>
          h(
            "div",
            { class: "check " + (a.passed ? "pass" : "fail") },
            h("span", { class: "mark", html: a.passed ? icon.check : icon.cross }),
            h(
              "div",
              {},
              h("div", { class: "check-name" }, a.label + (a.passed ? ", kept" : ", escalated")),
              h("div", { class: "check-reason" }, a.reason),
            ),
          ),
        ),
        m.chosen
          ? h("div", { class: "observe", style: "background:#eef7e0" }, h("b", {}, "Chosen. "), `${m.chosen.label} with a cross-validated R-squared of ${m.chosen.cv_r2}.`)
          : h("div", { class: "error-box" }, "No model met the bar, so this was flagged for a human. The agent will not force a low-confidence pick."),
      );
    }
    mount(
      h(
        "div",
        { class: "screen" },
        h(
          "div",
          { class: "level-shell" },
          railSteps("model"),
          h(
            "div",
            {},
            inner,
            h(
              "div",
              { class: "level-actions" },
              h(
                "button",
                { class: "btn btn-berry", onclick: () => go("#/results") },
                "See the results ",
                h("span", { html: icon.arrow }),
              ),
            ),
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------- results

  async function screenResults() {
    if (!state.levels) return go("#/dataset");
    if (!state.results) {
      loading("Putting your results together");
      try {
        state.results = await api("/api/results");
      } catch (e) {
        return errorScreen(e, "#/model");
      }
    }
    const r = state.results;
    const view = h(
      "div",
      { class: "screen" },
      h(
        "div",
        { class: "head" },
        h("img", { class: "head-mascot", src: MASCOT, alt: "" }),
        h(
          "div",
          {},
          h("h1", {}, "Your dataset, cleaned, checked, and modeled"),
          h("p", { class: "lead" }, "Everything here is the agent's real output. Your guesses were scored alongside it, never fed into it."),
        ),
      ),
      h(
        "div",
        { class: "stat-row" },
        h("div", { class: "stat" }, h("span", { class: "n" }, r.points_total), h("span", { class: "k" }, "points")),
        h(
          "div",
          { class: "stat" },
          h("span", { class: "n" }, `${r.levels_correct}/${r.levels_total}`),
          h("span", { class: "k" }, "guesses right"),
        ),
        h(
          "div",
          { class: "stat" },
          h("span", { class: "n" }, r.downstream_passed ? "Pass" : "Mixed"),
          h("span", { class: "k" }, "verification"),
        ),
        h(
          "div",
          { class: "stat" },
          h("span", { class: "n" }, r.model && r.model.chosen ? r.model.chosen.label : "None"),
          h("span", { class: "k" }, "model chosen"),
        ),
      ),
      h(
        "div",
        { style: "margin-top:26px" },
        h("h2", {}, "What changed"),
        h(
          "div",
          { class: "chips-changed" },
          r.columns_changed.length
            ? r.columns_changed.map((c) => h("span", { class: "chip-changed" }, c))
            : h("span", { class: "k" }, "no columns needed changes"),
        ),
      ),
      h(
        "div",
        { class: "table-wrap" },
        (() => {
          const t = h("table", { class: "preview" });
          t.append(h("thead", {}, h("tr", {}, r.cleaned_columns.map((c) => h("th", {}, c)))));
          t.append(
            h(
              "tbody",
              {},
              r.cleaned_preview.map((row) =>
                h(
                  "tr",
                  {},
                  r.cleaned_columns.map((c) =>
                    row[c] == null
                      ? h("td", { class: "cell-null" }, "empty")
                      : h("td", {}, String(row[c])),
                  ),
                ),
              ),
            ),
          );
          return t;
        })(),
      ),
      renderLesson(r.lesson),
      h(
        "div",
        { class: "level-actions", style: "margin-top:30px" },
        h("button", { class: "btn btn-berry", onclick: () => resetDataset() }, "Try another dataset"),
        h("button", { class: "btn btn-ghost", onclick: () => resetAll() }, "Start over"),
      ),
    );
    mount(view);
  }

  function renderLesson(md) {
    const box = h("div", { class: "lesson" });
    let ul = null;
    for (const raw of (md || "").split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      if (line.startsWith("## ")) {
        ul = null;
        box.append(h("h2", {}, line.slice(3)));
      } else if (line.startsWith("- ")) {
        if (!ul) {
          ul = h("ul", {});
          box.append(ul);
        }
        ul.append(h("li", {}, line.slice(2)));
      } else {
        ul = null;
        box.append(h("p", {}, line));
      }
    }
    return box;
  }

  function resetDataset() {
    state.dataset = state.roadmap = state.levels = state.verify = state.model = state.results = null;
    state.guesses = {};
    go("#/dataset");
  }

  function resetAll() {
    store.clear();
    Object.assign(state, {
      profile: { role: null, experience: null },
      dataset: null,
      roadmap: null,
      levels: null,
      guesses: {},
      verify: null,
      model: null,
      results: null,
    });
    go("#/");
  }

  // ---------------------------------------------------------------- router

  function render() {
    const hash = location.hash || "#/";
    const m = hash.match(/^#\/level\/(\d+)$/);
    if (m) return screenLevel(parseInt(m[1], 10));
    switch (hash) {
      case "#/":
        return screenOnboarding();
      case "#/dataset":
        return screenDataset();
      case "#/roadmap":
        return screenRoadmap();
      case "#/verify":
        return screenVerify();
      case "#/model":
        return screenModel();
      case "#/results":
        return screenResults();
      default:
        location.hash = "#/";
    }
  }

  window.addEventListener("hashchange", render);
  render();
})();
