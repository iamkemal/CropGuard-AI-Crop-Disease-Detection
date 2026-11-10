(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const listen = (element, event, handler) => element?.addEventListener(event, handler);
  const make = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };

  // Navigation is shared by every workspace and keeps mobile state explicit.
  const menuToggle = document.querySelector("[data-menu-toggle]");
  const sidebar = byId("workspaceSidebar");
  const closeNavigation = () => {
    document.body.classList.remove("navigation-open");
    menuToggle?.setAttribute("aria-expanded", "false");
    document.querySelector(".navigation-backdrop")?.setAttribute("hidden", "");
  };
  listen(menuToggle, "click", () => {
    const open = !document.body.classList.contains("navigation-open");
    document.body.classList.toggle("navigation-open", open);
    menuToggle.setAttribute("aria-expanded", String(open));
    document.querySelector(".navigation-backdrop").hidden = !open;
    if (open) sidebar?.querySelector("a")?.focus();
  });
  document.querySelectorAll("[data-menu-close]").forEach((button) => listen(button, "click", () => {
    closeNavigation();
    menuToggle?.focus();
  }));
  listen(document, "keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("navigation-open")) {
      closeNavigation();
      menuToggle?.focus();
    }
    if (event.key === "Tab" && document.body.classList.contains("navigation-open") && sidebar) {
      const items = [...sidebar.querySelectorAll("a, button")].filter((item) => item.offsetParent !== null);
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  });
  listen(window, "resize", () => { if (window.innerWidth > 991) closeNavigation(); });
  const publicToggle = document.querySelector("[data-public-menu-toggle]");
  listen(publicToggle, "click", () => {
    const open = byId("publicMenu").classList.toggle("is-open");
    publicToggle.setAttribute("aria-expanded", String(open));
  });

  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const field = byId(button.dataset.passwordToggle);
    if (!field) return;
    button.hidden = false;
    listen(button, "click", () => {
      const reveal = field.type === "password";
      field.type = reveal ? "text" : "password";
      button.setAttribute("aria-pressed", String(reveal));
      button.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
    });
  });

  // Filter and paginate only records already rendered by the authorised server.
  document.querySelectorAll("table[data-table]").forEach((table) => {
    const rows = [...table.querySelectorAll("tbody > tr")].filter((row) => !row.querySelector("td[colspan]"));
    if (!rows.length) return;
    const headers = [...table.querySelectorAll("thead th")].map((cell) => cell.textContent.trim() || "Actions");
    rows.forEach((row) => [...row.cells].forEach((cell, cellIndex) => {
      cell.dataset.label = headers[cellIndex] || "Actions";
    }));
    table.dataset.cards = "true";
    table.classList.add("data-table");
    const holder = table.closest(".table-responsive") || table.parentElement;
    const toolbar = make("div", "table-toolbar");
    const searchLabel = make("label", "table-search");
    const search = make("input");
    search.type = "search";
    search.placeholder = table.dataset.searchLabel || "Search records";
    search.setAttribute("aria-label", search.placeholder);
    const searchGlyph = make("span", "search-symbol", "⌕");
    searchGlyph.setAttribute("aria-hidden", "true");
    searchLabel.append(searchGlyph, search);
    const options = make("div", "table-options");
    const filters = [];
    for (const key of ["crop", "status", "outcome"]) {
      const values = [...new Set(rows.map((row) => row.dataset[key]).filter(Boolean))].sort();
      if (values.length < 2) continue;
      const label = make("label");
      const select = make("select");
      select.setAttribute("aria-label", `Filter by ${key}`);
      const all = make("option", "", `All ${key === "status" ? "statuses" : key + "s"}`);
      all.value = "";
      select.append(all);
      values.forEach((value) => { const item = make("option", "", value); item.value = value; select.append(item); });
      label.append(select);
      options.append(label);
      filters.push({ key, select });
    }
    const sizeLabel = make("label", "", "Rows");
    const size = make("select");
    size.setAttribute("aria-label", "Rows per page");
    [10, 25, 50].forEach((value) => { const item = make("option", "", String(value)); item.value = String(value); size.append(item); });
    sizeLabel.append(size);
    options.append(sizeLabel);
    toolbar.append(searchLabel, options);
    holder.before(toolbar);
    const pagination = make("div", "table-pagination");
    const description = make("span");
    description.setAttribute("role", "status");
    description.setAttribute("aria-live", "polite");
    const controls = make("div", "pagination-controls");
    const previous = make("button", "", "Previous");
    const next = make("button", "", "Next");
    const indicator = make("span", "page-indicator");
    previous.type = next.type = "button";
    controls.append(previous, indicator, next);
    pagination.append(description, controls);
    holder.after(pagination);
    const empty = make("p", "table-empty-result", "No records match your search. Try another term or clear a filter.");
    empty.hidden = true;
    holder.after(empty);
    let currentPage = 1;
    const render = () => {
      const query = search.value.toLocaleLowerCase().trim();
      const matching = rows.filter((row) => row.textContent.toLocaleLowerCase().includes(query)
        && filters.every(({ key, select }) => !select.value || row.dataset[key] === select.value));
      const count = Number(size.value);
      const pageCount = Math.max(1, Math.ceil(matching.length / count));
      currentPage = Math.min(currentPage, pageCount);
      const offset = (currentPage - 1) * count;
      const visible = new Set(matching.slice(offset, offset + count));
      rows.forEach((row) => { row.hidden = !visible.has(row); });
      empty.hidden = matching.length > 0;
      description.textContent = matching.length
        ? `Showing ${offset + 1}–${Math.min(offset + count, matching.length)} of ${matching.length} records`
        : "0 matching records";
      indicator.textContent = `${currentPage} / ${pageCount}`;
      previous.disabled = currentPage <= 1;
      next.disabled = currentPage >= pageCount;
      controls.hidden = pageCount <= 1;
    };
    const reset = () => { currentPage = 1; render(); };
    listen(search, "input", reset);
    listen(size, "change", reset);
    filters.forEach(({ select }) => listen(select, "change", reset));
    listen(previous, "click", () => { currentPage -= 1; render(); });
    listen(next, "click", () => { currentPage += 1; render(); });
    render();
  });

  const assessment = document.querySelector("form[data-assessment-wizard]");
  if (assessment) {
    const symptomStep = assessment.querySelector("[data-assessment-step=symptoms]");
    const photoStep = assessment.querySelector("[data-assessment-step=review]");
    const next = assessment.querySelector("[data-review-next]");
    const back = assessment.querySelector("[data-review-back]");
    const submit = assessment.querySelector("[data-assessment-submit]");
    const boxes = [...assessment.querySelectorAll('input[name="symptoms"]')];
    const refresh = () => {
      const selected = boxes.filter((box) => box.checked);
      assessment.querySelectorAll("[data-selected-count]").forEach((node) => { node.textContent = `${selected.length} selected`; });
      assessment.querySelectorAll("[data-selected-symptoms]").forEach((list) => {
        list.replaceChildren();
        selected.forEach((box) => list.append(make("li", "", box.dataset.symptomLabel || box.value)));
        if (!selected.length) list.append(make("li", "", "No symptoms selected yet."));
      });
    };
    const show = (step, focus = true) => {
      assessment.dataset.currentStep = step;
      assessment.classList.toggle("review-ready", step === "review");
      symptomStep.hidden = step !== "symptoms";
      photoStep.hidden = step !== "review";
      next.hidden = step === "review";
      back.hidden = step !== "review";
      submit.hidden = step !== "review";
      assessment.querySelectorAll("[data-progress-step]").forEach((item) => {
        const current = item.dataset.progressStep === (step === "review" ? "3" : "2");
        item.classList.toggle("is-current", current);
        item.classList.toggle("is-done", Number(item.dataset.progressStep) < (step === "review" ? 3 : 2));
        if (current) item.setAttribute("aria-current", "step"); else item.removeAttribute("aria-current");
      });
      refresh();
      if (focus) {
        const heading = assessment.querySelector(step === "review" ? ".wizard-review-heading" : ".wizard-symptom-heading");
        heading?.focus({ preventScroll: true });
        assessment.scrollIntoView({ block: "start", behavior: "auto" });
      }
    };
    next.hidden = false;
    listen(next, "click", () => show("review"));
    listen(back, "click", () => show("symptoms"));
    assessment.querySelectorAll("[data-edit-observations]").forEach((button) => {
      button.hidden = false;
      listen(button, "click", () => show("symptoms"));
    });
    boxes.forEach((box) => listen(box, "change", refresh));
    listen(assessment, "submit", (event) => {
      if (assessment.dataset.currentStep !== "review") { event.preventDefault(); show("review"); }
    });
    show(assessment.dataset.initialStep === "review" ? "review" : "symptoms", false);
  }

  // Edit drawers use existing protected GET/POST routes and CSRF fields.
  const editor = byId("editorDialog");
  const editorContent = byId("editorContent");
  let editorVersion = 0;
  const closeEditor = () => { editorVersion += 1; editor?.close(); };
  listen(document.querySelector("[data-close-editor]"), "click", closeEditor);
  listen(editor, "cancel", closeEditor);
  listen(document, "click", async (event) => {
    const cancel = event.target.closest("[data-editor-cancel]");
    if (cancel && editor?.contains(cancel) && editor.open) { event.preventDefault(); closeEditor(); return; }
    const link = event.target.closest("a[data-editor-link]");
    if (!link || !editor || typeof editor.showModal !== "function" || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    event.preventDefault();
    const version = ++editorVersion;
    closeNavigation();
    editorContent.replaceChildren();
    editor.setAttribute("aria-busy", "true");
    if (!editor.open) editor.showModal();
    try {
      const response = await fetch(url, { credentials: "same-origin" });
      const html = await response.text();
      if (version !== editorVersion || !editor.open) return;
      const parsed = new DOMParser().parseFromString(html, "text/html");
      const panel = parsed.querySelector("[data-editor-panel]");
      if (!response.ok || !panel) throw new Error("Editor unavailable");
      // Field names and action targets stay intact, while IDs remain unique.
      panel.querySelectorAll("form").forEach((form) => { if (!form.getAttribute("action")) form.setAttribute("action", response.url); });
      panel.querySelectorAll("[id]").forEach((field) => {
        const old = field.id;
        const replacement = `drawer-${old}`;
        panel.querySelectorAll("label[for]").forEach((label) => { if (label.htmlFor === old) label.htmlFor = replacement; });
        panel.querySelectorAll("[aria-describedby], [aria-labelledby]").forEach((element) => {
          ["aria-describedby", "aria-labelledby"].forEach((name) => {
            const value = element.getAttribute(name);
            if (value) element.setAttribute(name, value.split(" ").map((id) => id === old ? replacement : id).join(" "));
          });
        });
        field.id = replacement;
      });
      editorContent.append(document.importNode(panel, true));
      editorContent.querySelector("input:not([type=hidden]), select, textarea")?.focus();
    } catch {
      if (version === editorVersion && editor.open) window.location.assign(url.href);
    } finally {
      if (version === editorVersion) editor.removeAttribute("aria-busy");
    }
  });

  const confirmation = byId("confirmDialog");
  let pendingForm = null;
  let pendingSubmitter = null;
  listen(document, "submit", (event) => {
    const form = event.target.closest("form[data-confirm-title]");
    if (!form || !confirmation || typeof confirmation.showModal !== "function") return;
    if (form.dataset.confirmed === "true") { delete form.dataset.confirmed; return; }
    event.preventDefault();
    pendingForm = form;
    pendingSubmitter = event.submitter;
    byId("confirmTitle").textContent = form.dataset.confirmTitle;
    byId("confirmDescription").textContent = form.dataset.confirmDescription || "This action cannot be undone.";
    confirmation.showModal();
    confirmation.querySelector("[data-confirm-cancel]").focus();
  });
  listen(document.querySelector("[data-confirm-cancel]"), "click", () => { pendingForm = null; confirmation.close(); });
  listen(confirmation, "cancel", () => { pendingForm = null; });
  listen(document.querySelector("[data-confirm-accept]"), "click", () => {
    if (!pendingForm) return;
    const form = pendingForm;
    const submitter = pendingSubmitter;
    pendingForm = null;
    confirmation.close();
    form.dataset.confirmed = "true";
    form.requestSubmit(submitter || undefined);
  });

  const imageDialog = byId("recordImageDialog");
  listen(document, "click", (event) => {
    const link = event.target.closest("a[data-image-preview]");
    if (!link || !imageDialog || typeof imageDialog.showModal !== "function" || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    event.preventDefault();
    byId("recordImage").src = url.href;
    imageDialog.showModal();
  });
  listen(document.querySelector("[data-close-image]"), "click", () => imageDialog.close());
  listen(imageDialog, "close", () => byId("recordImage").removeAttribute("src"));
})();
