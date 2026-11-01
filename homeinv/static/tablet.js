// The tablet screen (templates/tablet/screen.html). Written in plain ES5 for old Fire tablet browsers.
// Every form still works without it; this only makes taps feel instant:
//
// form[data-tile-form]  posts in the background; the server answers with the updated tile
//                       (X-Tile header), which replaces the old one. − and + change the count on
//                       screen straight away. Quick repeated taps are sent one after another.
// input[data-filter]    hides tiles that don't match what's typed.
//
// Left alone for a few minutes, the page reloads itself, so counts changed elsewhere show up and
// the form tokens never go stale.
(function () {
  "use strict";

  var IDLE_RELOAD_MS = 3 * 60 * 1000;
  var lastActivity = new Date().getTime();
  var queues = {};  // tile id -> {busy, jobs}

  function closest(el, attr) {
    while (el && el.nodeType === 1) {
      if (el.hasAttribute(attr)) return el;
      el = el.parentNode;
    }
    return null;
  }

  function formatQty(n) {
    return String(Math.round(n * 100) / 100);
  }

  function anyBusy() {
    for (var id in queues) {
      if (queues.hasOwnProperty(id) && (queues[id].busy || queues[id].jobs.length)) return true;
    }
    return false;
  }

  function showMessage(text) {
    var box = document.querySelector("[data-messages]");
    if (!box) {
      box = document.createElement("div");
      box.className = "messages";
      box.setAttribute("data-messages", "");
      box.setAttribute("role", "status");
      document.body.appendChild(box);
    }
    box.innerHTML = "";
    var message = document.createElement("div");
    message.className = "message message-danger";
    message.textContent = text;
    box.appendChild(message);
  }

  function replaceTile(tileId, html) {
    var holder = document.createElement("ul");
    holder.innerHTML = html;
    var fresh = holder.querySelector("[data-tile]");
    var old = document.getElementById(tileId);
    if (fresh && old) {
      old.parentNode.replaceChild(fresh, old);
      applyFilter();
    }
  }

  function send(tileId) {
    var queue = queues[tileId];
    if (!queue || queue.busy || !queue.jobs.length) return;
    var job = queue.jobs.shift();
    queue.busy = true;
    var xhr = new XMLHttpRequest();
    xhr.open("POST", job.action, true);
    xhr.setRequestHeader("X-Requested-With", "fetch");
    xhr.onload = function () {
      queue.busy = false;
      if (xhr.status !== 200 || !xhr.getResponseHeader("X-Tile")) {
        window.location.reload();  // not set up any more, or the form expired
        return;
      }
      if (queue.jobs.length) {
        send(tileId);
      } else {
        replaceTile(tileId, xhr.responseText);
      }
    };
    xhr.onerror = function () {
      queue.busy = false;
      queue.jobs = [];
      showMessage("Couldn't save. Check the Wi-Fi; the page will reload.");
      setTimeout(function () { window.location.reload(); }, 4000);
    };
    xhr.send(job.data);
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.hasAttribute("data-tile-form")) return;
    var tile = closest(form, "data-tile");
    if (!tile || !window.FormData) return;
    event.preventDefault();

    var delta = parseFloat(form.getAttribute("data-delta"));
    if (!isNaN(delta)) {
      var qty = tile.querySelector("[data-qty]");
      var now = parseFloat(qty.textContent);
      if (!isNaN(now)) {
        var next = Math.max(now + delta, 0);
        qty.textContent = formatQty(next);
        var minus = tile.querySelector(".step-minus");
        if (minus) minus.disabled = next <= 0;
      }
    } else {
      tile.className += " is-saving";
    }

    var queue = queues[tile.id] || (queues[tile.id] = { busy: false, jobs: [] });
    queue.jobs.push({ action: form.action, data: new FormData(form) });
    send(tile.id);
  });

  // Find: hide tiles that don't match.
  var filter = document.querySelector("[data-filter]");
  function applyFilter() {
    if (!filter) return;
    var text = filter.value.replace(/^\s+|\s+$/g, "").toLowerCase();
    var tiles = document.querySelectorAll("[data-tile]");
    var shown = 0;
    for (var i = 0; i < tiles.length; i++) {
      var match = !text || tiles[i].getAttribute("data-name").indexOf(text) !== -1;
      tiles[i].hidden = !match;
      if (match) shown++;
    }
    var none = document.querySelector("[data-no-match]");
    if (none) none.hidden = shown > 0;
  }
  if (filter) {
    filter.addEventListener("input", applyFilter);
    applyFilter();
  }

  // After adding something, the page comes back as /tablet#tile-N: outline that tile and scroll it
  // into view below the sticky header (old browsers don't know scroll-margin).
  if (window.location.hash.indexOf("#tile-") === 0) {
    var added = document.getElementById(window.location.hash.slice(1));
    if (added) {
      added.className += " is-new";
      setTimeout(function () {
        var header = document.querySelector(".top");
        var top = added.getBoundingClientRect().top + window.pageYOffset;
        window.scrollTo(0, Math.max(top - (header ? header.offsetHeight : 0) - 12, 0));
      }, 0);
    }
    if (window.history.replaceState) window.history.replaceState(null, "", window.location.pathname);
  }

  // Messages fade after a few seconds.
  var messages = document.querySelector("[data-messages]");
  if (messages) {
    setTimeout(function () { messages.hidden = true; }, 5000);
  }

  // Reload when left alone, unless someone is typing or a change is still saving.
  function touched() { lastActivity = new Date().getTime(); }
  ["touchstart", "mousedown", "keydown", "input"].forEach(function (name) {
    document.addEventListener(name, touched, true);
  });
  setInterval(function () {
    var idle = new Date().getTime() - lastActivity;
    if (idle > IDLE_RELOAD_MS && !(filter && filter.value) && !anyBusy()) {
      window.location.reload();
    }
  }, 30 * 1000);
})();
