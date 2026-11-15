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
      if (meta.querySelector(".mk-developing")) return;
      var upd = meta.querySelector(".mk-updated");
      if (upd) upd.hidden = true;
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

  function store(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (e) {}
  }

  function display() {
    var tg = document.getElementById("disp-toggle");
    var panel = document.getElementById("disp-panel");
    if (!tg || !panel) return;
    tg.hidden = false;
    var sizes = panel.querySelectorAll("[data-text]");
    var img = document.getElementById("disp-images");
    function paint() {
      var z = root.getAttribute("data-text") || "100";
      Array.prototype.forEach.call(sizes, function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-text") === z));
      });
      var on = root.getAttribute("data-images") !== "off";
      img.setAttribute("aria-checked", String(on));
      img.textContent = img.getAttribute(on ? "data-on" : "data-off");
    }
    function open(v) {
      panel.hidden = !v;
      tg.setAttribute("aria-expanded", String(v));
      if (v) {
        var first = panel.querySelector('[aria-pressed="true"]') || panel.querySelector("button");
        first.focus();
      }
    }
    Array.prototype.forEach.call(sizes, function (b) {
      b.addEventListener("click", function () {
        var z = b.getAttribute("data-text");
        if (z === "100") root.removeAttribute("data-text");
        else root.setAttribute("data-text", z);
        store("textsize", z === "100" ? null : z);
        paint();
      });
    });
    img.addEventListener("click", function () {
      var off = root.getAttribute("data-images") !== "off";
      if (off) root.setAttribute("data-images", "off");
      else root.removeAttribute("data-images");
      store("images", off ? "off" : null);
      paint();
    });
    tg.addEventListener("click", function () {
      open(panel.hidden);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) {
        open(false);
        tg.focus();
      }
    });
    document.addEventListener("click", function (e) {
      if (!panel.hidden && !panel.contains(e.target) && !tg.contains(e.target)) open(false);
    });
    paint();
  }

  function follows() {
    var key = body.getAttribute("data-follow");
    if (!key) return;
    var now = Date.now();
    var f = {};
    try {
      f = JSON.parse(localStorage.getItem(key)) || {};
    } catch (e) {}
    Object.keys(f).forEach(function (id) {
      if (!f[id] || typeof f[id].at !== "number" || now - f[id].at > 7 * 86400000) delete f[id];
    });
    function save() {
      var ids = Object.keys(f).sort(function (a, b) {
        return f[b].at - f[a].at;
      });
      ids.slice(50).forEach(function (id) {
        delete f[id];
      });
      store(key, ids.length ? JSON.stringify(f) : null);
    }
    var btn = document.querySelector(".follow");
    var current = btn ? btn.getAttribute("data-id") : "";
    if (btn) {
      var id = btn.getAttribute("data-id");
      var size = parseInt(btn.getAttribute("data-size"), 10) || 0;
      var paint = function () {
        var on = !!f[id];
        btn.setAttribute("aria-pressed", String(on));
        btn.textContent = btn.getAttribute(on ? "data-on" : "data-off");
      };
      if (f[id]) f[id] = { at: now, n: size };
      btn.hidden = false;
      paint();
      btn.addEventListener("click", function () {
        if (f[id]) delete f[id];
        else f[id] = { at: Date.now(), n: size };
        save();
        paint();
      });
    }
    save();
    if (!Object.keys(f).length || !window.fetch) return;
    var url = new URL(body.getAttribute("data-follow-json"), location.href);
    fetch(url.href, { cache: "no-cache" })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (doc) {
        if (!doc || !doc.stories) return;
        var changed = [];
        Object.keys(f).forEach(function (id) {
          var s = doc.stories[id];
          if (!s) delete f[id];
          else if (id === current) f[id].n = Math.max(f[id].n, s[0]);
          else if (s[0] > f[id].n) changed.push({ add: s[0] - f[id].n, title: s[2], href: new URL(s[3], url).href });
        });
        save();
        var note = document.getElementById("follow-notice");
        if (!note || !changed.length) return;
        var p = document.createElement("p");
        p.textContent = note.getAttribute(changed.length === 1 ? "data-one" : "data-many").replace("{n}", changed.length);
        var ul = document.createElement("ul");
        changed.forEach(function (c) {
          var li = document.createElement("li");
          var a = document.createElement("a");
          a.href = c.href;
          var t = document.createElement("span");
          t.textContent = c.title;
          var n = document.createElement("span");
          n.className = "plus";
          n.textContent = "+" + c.add;
          a.appendChild(t);
          a.appendChild(n);
          li.appendChild(a);
          ul.appendChild(li);
        });
        note.appendChild(p);
        note.appendChild(ul);
        note.hidden = false;
      })
      .catch(function () {});
  }

  visits();
  display();
  follows();
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
