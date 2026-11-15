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
        navigator
          .share({ title: box.getAttribute("data-title"), url: url })
          .then(function () {
            ping("s");
          })
          .catch(function () {});
        return;
      }
      links.hidden = !links.hidden;
      btn.setAttribute("aria-expanded", String(!links.hidden));
    });
    links.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest("a[data-href]")) ping("s");
    });
    copy.addEventListener("click", function () {
      var done = function () {
        ping("s");
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

  function meta(name) {
    var m = document.querySelector('meta[name="seer:' + name + '"]');
    return m ? m.getAttribute("content") || "" : "";
  }

  var statsKey = (body.getAttribute("data-stats") || "") + ":";

  function counting() {
    try {
      return localStorage.getItem(statsKey + "nocount") !== "1";
    } catch (e) {
      return false;
    }
  }

  function two(n) {
    return (n < 10 ? "0" : "") + n;
  }

  function isoWeek(d) {
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var day = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - day);
    var w = Math.ceil(((t - Date.UTC(t.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7);
    return t.getUTCFullYear() + "-W" + two(w);
  }

  var ping = function () {};

  function stats() {
    var page = meta("page");
    var kind = meta("kind");
    var base = body.getAttribute("data-ping");
    if (!page || !kind || !base || !counting()) return;
    var d = new Date();
    var today = d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate());
    var week = isoWeek(d);
    var month = today.slice(0, 7);
    var st = {};
    try {
      st = JSON.parse(localStorage.getItem(statsKey + "stats")) || {};
    } catch (e) {}
    var fresh = {
      fd: st.day !== today ? 1 : 0,
      fw: st.week !== week ? 1 : 0,
      fm: st.month !== month ? 1 : 0,
    };
    var first = typeof st.first === "string" && /^\d{4}-\d\d-\d\d$/.test(st.first) ? st.first : today;
    try {
      localStorage.setItem(
        statsKey + "stats",
        JSON.stringify({ first: first, day: today, week: week, month: month })
      );
    } catch (e) {
      return;
    }
    var id = Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10);
    var common = {
      v: 1,
      ed: meta("edition"),
      k: kind,
      p: page,
      st: meta("story"),
      sec: meta("section"),
      n: first < today ? 1 : 0,
      id: id,
    };
    // iPadOS Safari reports a Mac user agent
    if (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1) common.tm = 1;

    function url(extra) {
      var parts = [];
      [common, extra].forEach(function (o) {
        Object.keys(o).forEach(function (k) {
          if (o[k] !== "" && o[k] != null) parts.push(k + "=" + encodeURIComponent(o[k]));
        });
      });
      return base + "?" + parts.join("&");
    }

    function send(extra) {
      if (!counting()) return;
      var u = url(extra);
      if (window.fetch) fetch(u, { keepalive: true, cache: "no-store" }).catch(function () {});
      else new Image().src = u;
    }

    ping = function (e, extra) {
      var o = { e: e };
      Object.keys(extra || {}).forEach(function (k) {
        o[k] = extra[k];
      });
      send(o);
    };

    var view = { e: "v" };
    if (fresh.fd) view.fd = 1;
    if (fresh.fw) view.fw = 1;
    if (fresh.fm) view.fm = 1;
    new Image().src = url(view);

    var shown = 0;
    var since = document.visibilityState === "visible" ? Date.now() : 0;
    var left = false;
    function leave() {
      if (left) return;
      left = true;
      if (since) shown += Date.now() - since;
      since = 0;
      send({ e: "l", t: Math.min(shown, 1800000) });
    }
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") leave();
      else if (!left) since = Date.now();
    });
    window.addEventListener("pagehide", leave);

    function out(ev) {
      var a = ev.target && ev.target.closest ? ev.target.closest("a[data-story]") : null;
      if (!a) return;
      var outlet = a.getAttribute("data-outlet") || a.hostname.replace(/^www\./, "");
      ping("o", { st: a.getAttribute("data-story"), o: outlet });
    }
    document.addEventListener("click", out);
    document.addEventListener("auxclick", out);
  }

  function display() {
    var tg = document.getElementById("disp-toggle");
    var panel = document.getElementById("disp-panel");
    if (!tg || !panel) return;
    tg.hidden = false;
    var sizes = panel.querySelectorAll("[data-text]");
    var img = document.getElementById("disp-images");
    var cnt = document.getElementById("disp-count");
    function paint() {
      var z = root.getAttribute("data-text") || "100";
      Array.prototype.forEach.call(sizes, function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-text") === z));
      });
      var on = root.getAttribute("data-images") !== "off";
      img.setAttribute("aria-checked", String(on));
      img.textContent = img.getAttribute(on ? "data-on" : "data-off");
      var c = counting();
      cnt.setAttribute("aria-checked", String(c));
      cnt.textContent = cnt.getAttribute(c ? "data-on" : "data-off");
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
    cnt.addEventListener("click", function () {
      var off = counting();
      store(statsKey + "nocount", off ? "1" : null);
      if (off) store(statsKey + "stats", null);
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
        else {
          f[id] = { at: Date.now(), n: size };
          ping("f");
        }
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
  stats();
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
