// Small progressive enhancements. Every form still works without JavaScript.
//
// form[data-inplace]   inside a [data-row]: posts in the background; the server
//                      answers with just the updated row (X-Row header), which
//                      replaces the old one.
// form[data-refresh="#id"]  posts in the background, follows the redirect, and
//                      swaps #id (and the tab bar, for the list badge) from the
//                      page that comes back. Keeps your scroll position.
// input[data-live-search="#id"]  as you type, reloads the page's #id for the
//                      new search without a full page load.
(function () {
  function swapFrom(html, selectors) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    let swapped = 0;
    selectors.forEach(function (sel) {
      const fresh = doc.querySelector(sel);
      const old = document.querySelector(sel);
      if (fresh && old) { old.replaceWith(fresh); swapped++; }
    });
    // Flash messages from the new page, so feedback isn't lost.
    const alerts = doc.querySelectorAll("main > .alert");
    const main = document.querySelector("main");
    document.querySelectorAll("main > .alert").forEach(function (a) { a.remove(); });
    alerts.forEach(function (a) { main.prepend(a); });
    return swapped;
  }

  document.addEventListener("submit", async function (event) {
    const form = event.target;
    const refresh = form.dataset.refresh;
    const row = form.matches("[data-inplace]") ? form.closest("[data-row]") : null;
    if (!refresh && !row) return;
    event.preventDefault();
    const busy = row || document.querySelector(refresh) || form;
    busy.classList.add("is-saving");
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: row ? { "X-Requested-With": "fetch" } : {},
        credentials: "same-origin",
      });
      const html = await response.text();
      if (row) {
        if (!response.headers.get("X-Row")) { window.location.reload(); return; }
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        row.replaceWith(template.content.firstElementChild);
        return;
      }
      if (!response.ok || !swapFrom(html, refresh.split(",").concat([".tabbar"]))) {
        window.location.reload();
      }
    } catch (error) {
      form.submit();
    } finally {
      busy.classList.remove("is-saving");
    }
  });

  // Quantity boxes save when you leave them or press Enter.
  document.addEventListener("change", function (event) {
    if (event.target.matches("input[data-autosubmit]")) {
      event.target.form.requestSubmit();
    }
  });

  // Live search on Find.
  let timer = null;
  let lastQuery = null;
  document.addEventListener("input", function (event) {
    const input = event.target;
    const target = input.dataset ? input.dataset.liveSearch : null;
    if (!target) return;
    clearTimeout(timer);
    timer = setTimeout(async function () {
      const query = input.value.trim();
      if (query === lastQuery) return;
      lastQuery = query;
      const url = new URL(input.form.action, window.location.href);
      if (query) url.searchParams.set("q", query); else url.searchParams.delete("q");
      try {
        const response = await fetch(url, { credentials: "same-origin" });
        if (input.value.trim() !== query) return; // typed more since
        swapFrom(await response.text(), [target]);
        window.history.replaceState(null, "", url);
      } catch (error) { /* keep what's shown; Enter still submits */ }
    }, 180);
  });
})();
