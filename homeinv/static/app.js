// In-place updates for inventory rows.
// Forms marked data-inplace post in the background; the server answers with the
// updated row (marked with an X-Row header), which replaces the old one.
// Anything unexpected falls back to a normal page load.
(function () {
  document.addEventListener("submit", async function (event) {
    const form = event.target.closest("form[data-inplace]");
    if (!form) return;
    const row = form.closest("[data-row]");
    if (!row) return;
    event.preventDefault();
    row.classList.add("is-saving");
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin",
      });
      if (!response.headers.get("X-Row")) {
        window.location.reload();
        return;
      }
      const template = document.createElement("template");
      template.innerHTML = (await response.text()).trim();
      const fresh = template.content.firstElementChild;
      row.replaceWith(fresh);
    } catch (error) {
      form.submit();
    }
  });

  // Quantity boxes save when you leave them or press Enter.
  document.addEventListener("change", function (event) {
    if (event.target.matches("input[data-autosubmit]")) {
      event.target.form.requestSubmit();
    }
  });
})();
