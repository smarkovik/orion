(function () {
  var root = document.documentElement;
  var btn = document.getElementById("theme-toggle");
  var media = window.matchMedia("(prefers-color-scheme: dark)");

  function current() {
    var t = root.getAttribute("data-theme");
    return t === "light" || t === "dark" ? t : media.matches ? "dark" : "light";
  }

  function label() {
    if (!btn) return;
    var next = current() === "dark" ? "light" : "dark";
    var name = btn.getAttribute("data-" + next);
    btn.querySelector(".lbl").textContent = name;
    btn.setAttribute("aria-label", btn.getAttribute("data-label") + ": " + name);
  }

  if (btn) {
    btn.hidden = false;
    label();
    btn.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem("theme", next);
      } catch (e) {}
      label();
    });
    if (media.addEventListener) media.addEventListener("change", label);
  }

  var body = document.body;

  function visits() {
    var key = body.getAttribute("data-visit");
    if (!key) return;
    var now = Date.now();
    var st = {};
    try {
      st = JSON.parse(localStorage.getItem(key)) || {};
    } catch (e) {}
    var prev = typeof st.prev === "number" ? st.prev : 0;
    var last = typeof st.last === "number" ? st.last : 0;
    if (last && now - last > 30 * 60 * 1000) prev = last;
    try {
      localStorage.setItem(key, JSON.stringify({ prev: prev || null, last: now }));
    } catch (e) {}
    if (!prev) return;
    root.classList.add("has-prev");
    var label = body.getAttribute("data-new");
    var count = 0;
    Array.prototype.forEach.call(document.querySelectorAll("[data-created]"), function (el) {
      var t = Date.parse(el.getAttribute("data-created"));
      var meta = el.querySelector(".meta");
      if (!(t > prev) || !meta) return;
      count++;
      var mk = document.createElement("span");
      mk.className = "mk mk-fresh";
      mk.appendChild(document.createTextNode(" \u00b7 "));
      var m = document.createElement("span");
      m.className = "mark mark-new";
      m.textContent = label;
      mk.appendChild(m);
      meta.appendChild(mk);
    });
    var note = document.getElementById("since");
    if (note && count > 0) {
      note.textContent = note.getAttribute(count === 1 ? "data-one" : "data-many").replace("{n}", count);
      note.hidden = false;
    }
  }

  function share() {
    var box = document.querySelector(".share");
    if (!box) return;
    var btn = box.querySelector(".share-btn");
    var links = box.querySelector(".share-links");
    var note = box.querySelector(".share-note");
    var copy = box.querySelector(".share-copy");
    var url = location.href;
    box.hidden = false;
    Array.prototype.forEach.call(links.querySelectorAll("a[data-href]"), function (a) {
      a.href = a.getAttribute("data-href") + encodeURIComponent(url);
    });
    btn.addEventListener("click", function () {
      if (navigator.share) {
        navigator.share({ title: box.getAttribute("data-title"), url: url }).catch(function () {});
        return;
      }
      links.hidden = !links.hidden;
      btn.setAttribute("aria-expanded", String(!links.hidden));
    });
    copy.addEventListener("click", function () {
      var done = function () {
        note.textContent = copy.getAttribute("data-done");
        setTimeout(function () {
          note.textContent = "";
        }, 3000);
      };
      var fallback = function () {
        var ta = document.createElement("textarea");
        ta.value = url;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try {
          if (document.execCommand("copy")) done();
        } catch (e) {}
        document.body.removeChild(ta);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, fallback);
      } else {
        fallback();
      }
    });
  }

  function worker() {
    var path = body.getAttribute("data-sw");
    if (!path || !("serviceWorker" in navigator) || !/^https?:$/.test(location.protocol)) return;
    var controlled = !!navigator.serviceWorker.controller;
    navigator.serviceWorker
      .register(path)
      .then(function () {
        return navigator.serviceWorker.ready;
      })
      .then(function (reg) {
        if (controlled || !reg.active) return;
        var urls = [location.href].concat(
          performance.getEntriesByType("resource").map(function (e) {
            return e.name;
          })
        );
        reg.active.postMessage({ urls: urls });
      })
      .catch(function () {});
  }

  visits();
  share();
  worker();

  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var tag = (e.target && e.target.tagName) || "";
    if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
    var rel = e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : "";
    var link = rel && document.querySelector('a[rel="' + rel + '"]');
    if (link) window.location.href = link.href;
  });
})();
