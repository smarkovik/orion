// Readers tab: reads data/readers/*.json (contract: READERS.md section 3). Uses helpers exported by admin.js.
(function () {
  "use strict";
  var K = window.AdminKit;
  if (!K) return;
  var h = K.h, s = K.s, num = K.num, $ = K.$, sum = K.sum;
  var BASE = "data/readers/";
  var BOUNDS = [5, 10, 20, 30, 60, 120, 300, 600, 1800];
  var BLABEL = ["up to 5 s", "5–10 s", "10–20 s", "20–30 s", "30–60 s", "1–2 min", "2–5 min", "5–10 min", "10–30 min", "over 30 min"];
  var GROUPS = [["under 10 s", 0, 1], ["10–30 s", 2, 3], ["30 s – 2 min", 4, 5], ["2–10 min", 6, 7], ["over 10 min", 8, 9]];
  var KINDS = ["story", "front", "section", "day", "week", "briefing", "calendar", "about", "chooser"];
  var NEW_C = "var(--s1)", RET_C = "var(--s2)", OTHER_C = "var(--muted)";
  var R = { open: false, ix: null, cache: {}, files: [], end: null, from: null, win: 14, catalog: undefined, mode: "all", sortKey: "views", sortDir: -1, gen: 0, built: false };
  var root = $("view-readers");

  // ---- small helpers
  function pct(x, d) { return x == null || isNaN(x) ? "–" : (100 * x).toFixed(d == null ? 0 : d) + " %"; }
  function dur(sec) {
    if (sec == null) return "–";
    if (sec < 60) return Math.round(sec) + " s";
    var m = Math.floor(sec / 60), r = Math.round(sec - m * 60);
    return m + " min " + (r < 10 ? "0" : "") + r + " s";
  }
  function dstr(t) { return new Date(t).toISOString().slice(0, 10); }
  function dnum(d) { return Date.parse(d + "T12:00:00Z"); }
  function addDays(d, n) { return dstr(dnum(d) + n * 864e5); }
  function isoWeek(d) {
    var t = new Date(dnum(d)), day = (t.getUTCDay() + 6) % 7;
    t.setUTCDate(t.getUTCDate() - day + 3);
    var y = t.getUTCFullYear(), j = new Date(Date.UTC(y, 0, 4));
    return { year: y, week: 1 + Math.round(((t - j) / 864e5 - 3 + ((j.getUTCDay() + 6) % 7)) / 7) };
  }
  function wkey(d) { var w = isoWeek(d); return w.year + "-W" + K.pad(w.week); }
  function monday(d) { return addDays(d, -((new Date(dnum(d)).getUTCDay() + 6) % 7)); }
  function median(hist) {
    var n = sum(hist);
    if (!n) return null;
    var half = n / 2, cum = 0;
    for (var i = 0; i < hist.length; i++) {
      if (hist[i] && cum + hist[i] >= half) {
        if (i >= BOUNDS.length) return BOUNDS[BOUNDS.length - 1];
        var lo = i ? BOUNDS[i - 1] : 0;
        return lo + ((half - cum) / hist[i]) * (BOUNDS[i] - lo);
      }
      cum += hist[i];
    }
    return null;
  }
  function addHist(a, b) { for (var i = 0; i < 10; i++) a[i] = (a[i] || 0) + ((b && b[i]) || 0); return a; }
  function getJson(u) { return K.getJson(u); }
  function sel() {
    var b = document.querySelector('#win [aria-pressed="true"]');
    return { days: b ? +b.getAttribute("data-days") : 14, ed: $("ed").value || "all" };
  }
  function edList() { return !R.ix ? [] : sel().ed === "all" ? Object.keys(R.ix.editions) : [sel().ed]; }
  function tipRows(rows) { return rows; }
  function hover(el, head, rowsFn) {
    function go(x, y) { K.showTip(head, rowsFn(), x, y); }
    el.addEventListener("pointermove", function (e) { go(e.clientX, e.clientY); });
    el.addEventListener("pointerleave", K.hideTip);
    el.addEventListener("focus", function () { var r = el.getBoundingClientRect(); go(r.left + Math.min(r.width, 200) / 2, r.top); });
    el.addEventListener("blur", K.hideTip);
  }

  // ---- loading
  function dayDoc(ed, d) {
    var k = ed + "/" + d;
    if (!R.cache[k]) R.cache[k] = getJson(BASE + ed + "/" + d + ".json");
    return R.cache[k];
  }
  function load() {
    var gen = ++R.gen, win = sel().days;
    root.classList.add("stale");
    return getJson(BASE + "index.json").then(function (ix) {
      if (gen !== R.gen) return;
      R.ix = ix && ix.editions ? ix : null;
      if (!R.ix) { R.files = []; R.end = null; return; }
      var eds = Object.keys(R.ix.editions), end = "";
      eds.forEach(function (e) { (R.ix.editions[e].days || []).forEach(function (d) { if (d > end) end = d; }); });
      if (!end) { R.files = []; R.end = null; return; }
      var ws = addDays(end, -(win - 1));
      // whole ISO weeks and months for the weekly/monthly sums; 38 days back for the never-read check (catalog keeps 35)
      var from = [ws, monday(ws), ws.slice(0, 8) + "01", addDays(end, -37)].sort()[0];
      R.end = end; R.from = from; R.win = win; R.ws = ws;
      var jobs = [];
      eds.forEach(function (e) { (R.ix.editions[e].days || []).forEach(function (d) { if (d >= from && d <= end) jobs.push(dayDoc(e, d)); }); });
      return Promise.all(jobs).then(function (docs) { if (gen === R.gen) R.files = docs.filter(Boolean); });
    }).then(function () { if (gen === R.gen) { root.classList.remove("stale"); draw(); } });
  }
  function loadCatalog() {
    if (R.catalog !== undefined) return Promise.resolve();
    R.catalog = null;
    return getJson(BASE + "stories.json").then(function (c) { R.catalog = c && c.stories ? c : null; });
  }

  // ---- aggregation (scoped by edition filter)
  function scopeFiles() { var eds = edList(); return R.files.filter(function (f) { return eds.indexOf(f.edition) >= 0; }); }
  function emptyDay() { return { readers: 0, returning: 0, views: 0, vret: 0, fw: 0, fm: 0, kinds: {}, sections: {}, hist: [] }; }
  function byDay(files) {
    var m = {};
    files.forEach(function (f) {
      var o = m[f.date] = m[f.date] || emptyDay();
      o.readers += f.readers_day || 0; o.returning += f.returning_day || 0; o.views += f.views || 0; o.vret += f.views_returning || 0;
      o.fw += f.first_week || 0; o.fm += f.first_month || 0;
      Object.keys(f.kinds || {}).forEach(function (k) { o.kinds[k] = (o.kinds[k] || 0) + (f.kinds[k].views || 0); });
      Object.keys(f.sections || {}).forEach(function (k) { o.sections[k] = (o.sections[k] || 0) + (f.sections[k].views || 0); });
      var t = f.kinds && f.kinds.story && f.kinds.story.time;
      if (t) addHist(o.hist, t.hist);
    });
    return m;
  }
  // stable colour order: ranked over everything loaded for all editions
  function rankOrder(field) {
    var tot = {};
    R.files.forEach(function (f) {
      var o = f[field] || {};
      Object.keys(o).forEach(function (k) { tot[k] = (tot[k] || 0) + (o[k].views || 0); });
    });
    return Object.keys(tot).sort(function (a, b) { return tot[b] - tot[a] || a.localeCompare(b); });
  }
  function stackSpec(order, days, dayMap, key) {
    var top = order.slice(0, 7), series = top.map(function (k, i) {
      return { name: k, color: K.slot(i), vals: days.map(function (d) { return dayMap[d] ? dayMap[d][key][k] || 0 : 0; }) };
    });
    var other = days.map(function (d) {
      if (!dayMap[d]) return 0;
      return sum(Object.keys(dayMap[d][key]), function (k) { return top.indexOf(k) >= 0 ? 0 : dayMap[d][key][k]; });
    });
    if (order.length > 7 && sum(other)) series.push({ name: "Other", color: OTHER_C, vals: other });
    return series.filter(function (x) { return sum(x.vals) > 0; });
  }

  // ---- skeleton
  function block(id, title, def) {
    return h("section", { class: "block", id: id }, [h("h2", { text: title }), h("p", { class: "sub", text: def })]);
  }
  function card(id, title, sub) {
    return h("div", { class: "card", id: id }, [h("h3", { text: title }), h("p", { class: "sub", text: sub }), h("div", { class: "legend" }), h("div", { class: "plot" })]);
  }
  function build() {
    if (R.built) return;
    R.built = true;
    root.classList.add("rd");
    var b0 = block("rd-tiles", "Today", "Today is the latest day with data. Readers: browsers that opened the site for the first time that day. Averages cover the 7 days ending then.");
    b0.appendChild(h("div", { id: "rd-tile-box", class: "tiles" }));
    var b1 = block("rd-trends", "Trends", "Readers are counted once per browser per day, week or month; a browser is returning if its first visit was on an earlier day.");
    var g = h("div", { class: "charts" });
    var daily = card("rd-daily", "Daily readers and returning share", "Bars: readers per day, new and returning. Line: returning readers as a share of the day's readers.");
    daily.appendChild(h("p", { class: "cap" }, [h("i", { style: "border-color:" + RET_C }), document.createTextNode("Returning share of readers (%), own axis")]));
    daily.appendChild(h("div", { class: "plot2" }));
    g.appendChild(daily);
    g.appendChild(card("rd-weekly", "Weekly readers", "Sum of each day's first-of-week readers per ISO week. The latest week is still in progress."));
    g.appendChild(card("rd-monthly", "Monthly readers", "Sum of each day's first-of-month readers per month. The latest month is still in progress."));
    g.appendChild(card("rd-kind", "Views per day by page kind", "All page views, stacked by kind of page."));
    g.appendChild(card("rd-sect", "Views per day by section", "All page views, stacked by the section of the page or story."));
    b1.appendChild(g);
    var b2 = block("rd-read", "What readers read", "Views, returning share and read-on clicks of stories over the selected window. Time is the average visible time on the story page (time sum / leave events). Returning mode shows views from returning browsers only.");
    var tg = h("div", { class: "seg", id: "rd-mode", role: "group", "aria-label": "Readers" }, [
      h("button", { type: "button", "data-m": "all", "aria-pressed": "true", text: "All readers" }),
      h("button", { type: "button", "data-m": "ret", "aria-pressed": "false", text: "Returning readers" })]);
    b2.appendChild(h("div", { class: "bar2" }, [tg]));
    b2.appendChild(h("div", { class: "split" }, [
      h("div", {}, [h("div", { class: "scroll sc" }, [h("table", { id: "rd-top" })])]),
      h("div", { class: "card", id: "rd-share" }, [h("h3", { text: "Sections: new vs returning" }), h("p", { class: "sub", text: "Share of each group's views that went to the section." }), h("div", { class: "legend" }), h("div", { class: "hbox" })])]));
    var b3 = block("rd-never", "Never read", "Stories in the catalog, published in the window and more than 24 h ago, with no views and no read-on clicks since they were published. A story counts for every outlet that reported it.");
    b3.appendChild(h("div", { id: "rd-never-box" }));
    var b4 = block("rd-time", "Time on page", "Visible time per page load, from leave events. The median is read from the histogram (linear within a bucket), so it is approximate.");
    b4.appendChild(h("div", { class: "card", id: "rd-timecard" }, [h("div", { class: "legend" }), h("div", { class: "hbox" })]));
    var empty = h("p", { id: "rd-empty", class: "msg", hidden: "" });
    var body = h("div", { id: "rd-body" }, [b0, b1, b2, b3, b4]);
    root.appendChild(empty); root.appendChild(body);
    tg.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-m]");
      if (!b) return;
      R.mode = b.getAttribute("data-m");
      Array.prototype.forEach.call(tg.children, function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      drawTop();
    });
  }

  // ---- tiles
  function tile(k, v, sub) { return h("div", { class: "tile" }, [h("div", { class: "k", text: k }), h("div", { class: "v", text: v }), h("div", { class: "s", text: sub })]); }
  function drawTiles(dm) {
    var box = $("rd-tile-box"), end = R.end;
    box.textContent = "";
    var days7 = [], i;
    for (i = 0; i < 7; i++) { var d = addDays(end, -i); if (dm[d]) days7.push(dm[d]); }
    var t = dm[end] || emptyDay(), n7 = days7.length || 1;
    var avg = function (f) { return sum(days7, f) / n7; };
    var r7 = sum(days7, function (x) { return x.readers; });
    var hist7 = [];
    days7.forEach(function (x) { addHist(hist7, x.hist); });
    var m0 = median(t.hist), m7 = median(hist7);
    box.appendChild(tile("Readers today", num(t.readers), "7-day average " + num(avg(function (x) { return x.readers; })) + " · " + end));
    box.appendChild(tile("Returning today", t.readers ? pct(t.returning / t.readers) : "–", "7-day average " + (r7 ? pct(sum(days7, function (x) { return x.returning; }) / r7) : "–")));
    box.appendChild(tile("Views today", num(t.views), "7-day average " + num(avg(function (x) { return x.views; }))));
    box.appendChild(tile("Median time on story pages today", dur(m0), "7-day median " + dur(m7)));
  }

  // ---- trends
  function dailyCard(days, dm) {
    var c = $("rd-daily");
    var ret = days.map(function (d) { return dm[d] ? dm[d].returning : 0; });
    var nw = days.map(function (d) { return dm[d] ? dm[d].readers - dm[d].returning : 0; });
    var cats = days.map(function (d) { return d.slice(5); });
    var spec = { title: "Daily readers", cats: cats, series: [{ name: "New", color: NEW_C, vals: nw }, { name: "Returning", color: RET_C, vals: ret }] };
    spec.table = { head: ["Day", "Readers", "New", "Returning", "Returning share"], rows: days.map(function (d, i) { return [cats[i], num(nw[i] + ret[i]), num(nw[i]), num(ret[i]), nw[i] + ret[i] ? pct(ret[i] / (nw[i] + ret[i]), 1) : "–"]; }) };
    K.bars(c, spec);
    // returning share line, same x positions as the bars
    var p2 = c.querySelector(".plot2");
    p2.textContent = "";
    var vals = days.map(function (d, i) { return nw[i] + ret[i] ? ret[i] / (nw[i] + ret[i]) : null; });
    if (!vals.some(function (v) { return v != null; })) { p2.appendChild(h("p", { class: "empty", text: "No data in this window yet." })); return; }
    var g = K.geometry(p2, {});
    g.H = 150; g.ih = g.H - g.m.t - g.m.b;
    var ymax = Math.min(1, Math.ceil((Math.max.apply(null, vals.filter(function (v) { return v != null; })) * 1.1) / 0.2) * 0.2);
    var svg = s("svg", { width: g.W, height: g.H, viewBox: "0 0 " + g.W + " " + g.H, tabindex: 0, role: "img", "aria-label": "Returning share of readers per day, line chart; arrow keys read each day" }, p2);
    K.axes(svg, g, ymax, function (v) { return Math.round(v * 100) + " %"; });
    var slotw = g.iw / days.length, xs = days.map(function (_, i) { return g.m.l + slotw * (i + 0.5); });
    var Y = function (v) { return g.m.t + g.ih - (v / ymax) * g.ih; };
    var dpath = "", pen = false;
    vals.forEach(function (v, i) { if (v == null) { pen = false; return; } dpath += (pen ? "L" : "M") + xs[i].toFixed(1) + " " + Y(v).toFixed(1); pen = true; });
    s("path", { d: dpath, fill: "none", "stroke-width": 2, "stroke-linejoin": "round", style: "stroke:" + RET_C }, svg);
    // isolated days have no segment, so mark them
    vals.forEach(function (v, i) { if (v != null && vals[i - 1] == null && vals[i + 1] == null) s("circle", { cx: xs[i], cy: Y(v), r: 3, style: "fill:" + RET_C }, svg); });
    K.xlabels(svg, g, xs, cats);
    var cross = s("line", { y1: g.m.t, y2: g.m.t + g.ih, style: "stroke:var(--ink2)", "stroke-width": 1, visibility: "hidden" }, svg);
    var dot = s("circle", { r: 4, style: "fill:" + RET_C + ";stroke:var(--surface)", "stroke-width": 2, visibility: "hidden" }, svg);
    K.attach(svg, g, xs, function (i) {
      return { head: cats[i], rows: [{ color: RET_C, name: "returning share", value: pct(vals[i], 1) }, { color: "var(--axis)", name: "returning of readers", value: num(ret[i]) + " of " + num(ret[i] + nw[i]) }] };
    }, function (i) {
      cross.setAttribute("x1", xs[i]); cross.setAttribute("x2", xs[i]); cross.setAttribute("visibility", "visible");
      if (vals[i] == null) dot.setAttribute("visibility", "hidden"); else { dot.setAttribute("cx", xs[i]); dot.setAttribute("cy", Y(vals[i])); dot.setAttribute("visibility", "visible"); }
    }, function () { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); });
  }
  function periodCard(id, title, cats, vals) {
    var spec = { kind: "bars", title: title, cats: cats, series: [{ name: "Readers", color: NEW_C, vals: vals }] };
    spec.table = K.tableFor(spec);
    K.bars($(id), spec);
  }
  function stackCard(id, title, days, series) {
    var spec = { kind: "bars", title: title, cats: days.map(function (d) { return d.slice(5); }), series: series };
    spec.table = K.tableFor(spec);
    K.bars($(id), spec);
  }
  function drawTrends(dm) {
    var days = [], d;
    for (d = R.ws; d <= R.end; d = addDays(d, 1)) days.push(d);
    dailyCard(days, dm);
    var wk = {}, wo = [], mo = {}, mn = [];
    Object.keys(dm).sort().forEach(function (x) {
      var wi = wkey(x), mi = x.slice(0, 7);
      if (!(wi in wk)) { wk[wi] = 0; wo.push(wi); }
      if (!(mi in mo)) { mo[mi] = 0; mn.push(mi); }
      wk[wi] += dm[x].fw; mo[mi] += dm[x].fm;
    });
    var firstWk = wkey(R.ws), firstMo = R.ws.slice(0, 7);
    wo = wo.filter(function (k) { return k >= firstWk; });
    mn = mn.filter(function (k) { return k >= firstMo; });
    periodCard("rd-weekly", "Weekly readers", wo.map(function (k) { return "W" + k.slice(6); }), wo.map(function (k) { return wk[k]; }));
    periodCard("rd-monthly", "Monthly readers", mn, mn.map(function (k) { return mo[k]; }));
    stackCard("rd-kind", "Views per day by page kind", days, stackSpec(rankOrder("kinds"), days, dm, "kinds"));
    stackCard("rd-sect", "Views per day by section", days, stackSpec(rankOrder("sections"), days, dm, "sections"));
  }

  // ---- what readers read
  var TOPCOLS = [["title", "Story", 1], ["ed", "Edition", 1], ["section", "Section", 1], ["views", "Views"], ["share", "Returning share"], ["out", "Read on"], ["avg", "Avg time"]];
  function aggStories() {
    var m = {}, cat = R.catalog ? R.catalog.stories : {};
    scopeFiles().forEach(function (f) {
      if (f.date < R.ws) return;
      Object.keys(f.stories || {}).forEach(function (id) {
        var x = f.stories[id], o = m[id] = m[id] || { id: id, ed: f.edition, views: 0, vret: 0, out: 0, tn: 0, ts: 0 };
        o.views += x.views || 0; o.vret += x.views_returning || 0; o.out += x.out || 0; o.tn += x.time_n || 0; o.ts += x.time_sum_ms || 0;
      });
    });
    return Object.keys(m).map(function (id) {
      var o = m[id], c = cat[id] || {};
      o.title = c.title || id; o.section = c.section || "–"; o.page = c.page || "";
      o.share = o.views ? o.vret / o.views : 0; o.avg = o.tn ? o.ts / o.tn / 1000 : null;
      return o;
    });
  }
  function drawTop() {
    var t = $("rd-top"), list = aggStories(), ret = R.mode === "ret";
    list.forEach(function (o) { o.v = ret ? o.vret : o.views; });
    var key = R.sortKey === "views" ? "v" : R.sortKey;
    list = list.filter(function (o) { return o.v > 0; });
    list.sort(function (a, b) {
      var x = a[key], y = b[key];
      if (x == null) x = -1; if (y == null) y = -1;
      return (typeof x === "string" ? x.localeCompare(y) : x - y) * R.sortDir || b.v - a.v || a.id.localeCompare(b.id);
    });
    t.textContent = "";
    var hd = h("tr");
    TOPCOLS.forEach(function (c) {
      var b = h("button", { type: "button", text: c[1] });
      if (R.sortKey === c[0]) b.setAttribute("data-dir", R.sortDir > 0 ? "asc" : "desc");
      b.addEventListener("click", function () { if (R.sortKey === c[0]) R.sortDir = -R.sortDir; else { R.sortKey = c[0]; R.sortDir = c[2] ? 1 : -1; } drawTop(); });
      hd.appendChild(h("th", { class: c[2] ? "l" : "", "aria-sort": R.sortKey === c[0] ? (R.sortDir > 0 ? "ascending" : "descending") : "none" }, [b]));
    });
    t.appendChild(h("thead", {}, [hd]));
    var tb = h("tbody");
    if (!list.length) tb.appendChild(h("tr", {}, [h("td", { class: "l", colspan: TOPCOLS.length, text: "No story views in this window yet." })]));
    list.slice(0, 30).forEach(function (o) {
      var ttl = o.page ? h("a", { href: "../../" + o.page, text: o.title }) : document.createTextNode(o.title);
      tb.appendChild(h("tr", {}, [h("td", { class: "l t" }, [ttl]), h("td", { class: "l", text: o.ed }), h("td", { class: "l", text: o.section }),
        h("td", { text: num(o.v) }), h("td", { text: pct(o.share) }), h("td", { text: num(o.out) }), h("td", { text: dur(o.avg) })]));
    });
    t.appendChild(tb);
    t.setAttribute("aria-label", "Top stories, " + (ret ? "returning readers" : "all readers") + ", up to 30 rows");
  }
  function drawShares() {
    var c = $("rd-share"), box = c.querySelector(".hbox"), lg = c.querySelector(".legend"), nv = {}, rv = {}, tn = 0, tr = 0;
    scopeFiles().forEach(function (f) {
      if (f.date < R.ws) return;
      Object.keys(f.sections || {}).forEach(function (k) {
        var x = f.sections[k], r = x.views_returning || 0, n = (x.views || 0) - r;
        nv[k] = (nv[k] || 0) + n; rv[k] = (rv[k] || 0) + r; tn += n; tr += r;
      });
    });
    box.textContent = ""; lg.textContent = "";
    var all = Object.keys(nv).sort(function (a, b) { return (nv[b] + rv[b]) - (nv[a] + rv[a]) || a.localeCompare(b); });
    if (!all.length || !(tn + tr)) { box.appendChild(h("p", { class: "empty", text: "No data in this window yet." })); return; }
    [["New readers", NEW_C], ["Returning readers", RET_C]].forEach(function (x) { lg.appendChild(h("span", {}, [h("i", { style: "background:" + x[1] }), document.createTextNode(x[0])])); });
    var rows = all.slice(0, 8).map(function (k) { return [k, nv[k], rv[k]]; });
    if (all.length > 8) rows.push(["Other", sum(all.slice(8), function (k) { return nv[k]; }), sum(all.slice(8), function (k) { return rv[k]; })]);
    var mx = Math.max.apply(null, rows.map(function (r) { return Math.max(tn ? r[1] / tn : 0, tr ? r[2] / tr : 0); })) || 1;
    var grid = h("div", { class: "hb", role: "list" });
    rows.forEach(function (r) {
      var a = tn ? r[1] / tn : 0, b = tr ? r[2] / tr : 0;
      var row = h("div", { class: "row", tabindex: 0, role: "listitem", "aria-label": r[0] + ": new readers " + pct(a, 1) + ", returning readers " + pct(b, 1) }, [
        h("div", { class: "nm", text: r[0], title: r[0] }),
        h("div", { class: "bars" }, [
          h("div", { class: "bl" }, [h("i", { style: "background:" + NEW_C + ";width:" + (a / mx) * 70 + "%" }), document.createTextNode(pct(a, 1))]),
          h("div", { class: "bl" }, [h("i", { style: "background:" + RET_C + ";width:" + (b / mx) * 70 + "%" }), document.createTextNode(pct(b, 1))])])]);
      hover(row, r[0], function () { return [{ color: NEW_C, name: "new readers · " + num(r[1]) + " views", value: pct(a, 1) }, { color: RET_C, name: "returning readers · " + num(r[2]) + " views", value: pct(b, 1) }]; });
      grid.appendChild(row);
    });
    box.appendChild(grid);
    var tbl = h("table"), hd = h("tr");
    ["Section", "New views", "New share", "Returning views", "Returning share"].forEach(function (x, i) { hd.appendChild(h("th", { text: x, class: i ? "" : "l" })); });
    tbl.appendChild(hd);
    rows.forEach(function (r) { tbl.appendChild(h("tr", {}, [r[0], num(r[1]), pct(tn ? r[1] / tn : 0, 1), num(r[2]), pct(tr ? r[2] / tr : 0, 1)].map(function (x, i) { return h("td", { text: x, class: i ? "" : "l" }); }))); });
    box.appendChild(h("details", { class: "tbl" }, [h("summary", { text: "Table view" }), h("div", { class: "scroll" }, [tbl])]));
  }

  // ---- never read
  function neverRead() {
    if (!R.catalog) return null;
    var eds = edList(), used = {}, now = Date.now(), minPub = R.ws;
    R.files.forEach(function (f) {
      Object.keys(f.stories || {}).forEach(function (id) {
        var x = f.stories[id], o = used[id] = used[id] || { v: 0, o: 0 };
        o.v += x.views || 0; o.o += x.out || 0;
      });
    });
    var scope = [], never = [];
    Object.keys(R.catalog.stories).forEach(function (id) {
      var c = R.catalog.stories[id], t = Date.parse(c.first_published);
      if (eds.indexOf(c.edition) < 0 || isNaN(t) || now - t < 864e5 || dstr(t) < minPub) return;
      c = Object.assign({ id: id }, c);
      scope.push(c);
      var u = used[id];
      if (!u || (!u.v && !u.o)) never.push(c);
    });
    return { scope: scope, never: never };
  }
  function countBy(list, f) { var m = {}; list.forEach(function (c) { f(c).forEach(function (k) { m[k] = (m[k] || 0) + 1; }); }); return m; }
  function miniTable(head, rows) {
    var t = h("table"), hd = h("tr");
    head.forEach(function (x, i) { hd.appendChild(h("th", { text: x, class: i ? "" : "l" })); });
    t.appendChild(hd);
    if (!rows.length) t.appendChild(h("tr", {}, [h("td", { class: "l", colspan: head.length, text: "None" })]));
    rows.forEach(function (r) { t.appendChild(h("tr", {}, r.map(function (x, i) { return h("td", { text: x, class: i ? "" : "l" }); }))); });
    return h("div", { class: "scroll sc" }, [t]);
  }
  function drawNever() {
    var box = $("rd-never-box");
    box.textContent = "";
    var r = neverRead();
    if (!r) { box.appendChild(h("p", { class: "empty", text: "No story catalog yet (data/readers/stories.json)." })); return; }
    if (!r.scope.length) { box.appendChild(h("p", { class: "empty", text: "No catalog stories in this window yet." })); return; }
    var n = r.never.length, tot = r.scope.length;
    box.appendChild(h("div", { class: "tiles", id: "rd-never-tiles" }, [
      tile("Never read", String(n), "stories with no views and no read-on clicks"),
      tile("Share of stories", pct(n / tot, 1), n + " of " + tot + " stories older than 24 h")]));
    var sT = countBy(r.scope, function (c) { return [c.section || "–"]; }), sN = countBy(r.never, function (c) { return [c.section || "–"]; });
    var oT = countBy(r.scope, function (c) { return c.outlets || []; }), oN = countBy(r.never, function (c) { return c.outlets || []; });
    var secRows = Object.keys(sT).map(function (k) { return [k, sN[k] || 0, sT[k]]; }).sort(function (a, b) { return b[1] - a[1] || b[2] - a[2] || a[0].localeCompare(b[0]); });
    var outRows = Object.keys(oT).map(function (k) { return [k, oN[k] || 0, oT[k]]; }).sort(function (a, b) { return b[1] - a[1] || b[2] - a[2] || a[0].localeCompare(b[0]); }).slice(0, 15);
    var fmt = function (a) { return [a[0], String(a[1]), String(a[2]), a[2] ? pct(a[1] / a[2], 1) : "–"]; };
    var big = r.never.slice().sort(function (a, b) { return (b.sources || 0) - (a.sources || 0) || Date.parse(b.first_published) - Date.parse(a.first_published) || a.id.localeCompare(b.id); }).slice(0, 20);
    var bt = h("table", { id: "rd-never-list" }), hd = h("tr");
    ["Story", "Edition", "Section", "Outlets", "Published"].forEach(function (x, i) { hd.appendChild(h("th", { text: x, class: i < 3 ? "l" : "" })); });
    bt.appendChild(hd);
    if (!big.length) bt.appendChild(h("tr", {}, [h("td", { class: "l", colspan: 5, text: "Every story in this window was opened at least once." })]));
    big.forEach(function (c) {
      var ttl = c.page ? h("a", { href: "../../" + c.page, text: c.title || c.id }) : document.createTextNode(c.title || c.id);
      bt.appendChild(h("tr", {}, [h("td", { class: "l t" }, [ttl]), h("td", { class: "l", text: c.edition }), h("td", { class: "l", text: c.section || "–" }), h("td", { text: String(c.sources || 0) }), h("td", { text: String(c.first_published).slice(0, 10) })]));
    });
    var sec = h("div", { id: "rd-never-sec" }, [h("h3", { class: "h3s", text: "By section" }), miniTable(["Section", "Never read", "Stories", "Share"], secRows.map(fmt))]);
    var out = h("div", { id: "rd-never-out" }, [h("h3", { class: "h3s", text: "By outlet (top 15)" }), miniTable(["Outlet", "Never read", "Stories", "Share"], outRows.map(fmt))]);
    box.appendChild(h("div", { class: "split3" }, [sec, out]));
    box.appendChild(h("h3", { class: "h3s", text: "Biggest never-read stories (most outlets first, top 20)" }));
    box.appendChild(h("div", { class: "scroll sc" }, [bt]));
  }

  // ---- time on page
  function drawTime() {
    var c = $("rd-timecard"), box = c.querySelector(".hbox"), lg = c.querySelector(".legend"), agg = {};
    scopeFiles().forEach(function (f) {
      if (f.date < R.ws) return;
      Object.keys(f.kinds || {}).forEach(function (k) {
        var t = f.kinds[k].time;
        if (!t || !t.n) return;
        var o = agg[k] = agg[k] || { n: 0, hist: [] };
        o.n += t.n; addHist(o.hist, t.hist);
      });
    });
    box.textContent = ""; lg.textContent = "";
    var kinds = KINDS.filter(function (k) { return agg[k]; }).concat(Object.keys(agg).filter(function (k) { return KINDS.indexOf(k) < 0; }));
    if (!kinds.length) { box.appendChild(h("p", { class: "empty", text: "No time-on-page data in this window yet." })); return; }
    GROUPS.forEach(function (g, i) { lg.appendChild(h("span", {}, [h("i", { style: "background:var(--q" + (i + 1) + ")" }), document.createTextNode(g[0])])); });
    var grid = h("div", { class: "hb td", role: "list" });
    var tb = h("table"), hd = h("tr");
    ["Page kind", "Leaves", "Median"].concat(BLABEL).forEach(function (x, i) { hd.appendChild(h("th", { text: x, class: i ? "" : "l" })); });
    tb.appendChild(hd);
    kinds.forEach(function (k) {
      var a = agg[k], tot = sum(a.hist) || 1, med = median(a.hist);
      var gs = GROUPS.map(function (g) { return sum(a.hist.slice(g[1], g[2] + 1)) / tot; });
      var segs = h("div", { class: "dist" });
      gs.forEach(function (v, i) {
        var seg = h("i", { style: "background:var(--q" + (i + 1) + ");flex:" + v + " 1 0" });
        hover(seg, k + " · " + GROUPS[i][0], function () { return [{ color: "var(--q" + (i + 1) + ")", name: "of page loads", value: pct(v, 1) }]; });
        segs.appendChild(seg);
      });
      var row = h("div", { class: "row", tabindex: 0, role: "listitem", "aria-label": k + ": median " + dur(med) + ", " + GROUPS.map(function (g, i) { return pct(gs[i], 0) + " " + g[0]; }).join(", ") }, [
        h("div", { class: "nm", text: k }), h("div", { class: "md", text: dur(med) }), segs]);
      hover(row, k + " · median " + dur(med), function () { return GROUPS.map(function (g, i) { return { color: "var(--q" + (i + 1) + ")", name: g[0], value: pct(gs[i], 1) }; }); });
      grid.appendChild(row);
      tb.appendChild(h("tr", {}, [k, num(a.n), dur(med)].concat(a.hist.map(function (v) { return num(v); })).map(function (x, i) { return h("td", { text: x, class: i ? "" : "l" }); })));
    });
    box.appendChild(grid);
    box.appendChild(h("details", { class: "tbl" }, [h("summary", { text: "Table view" }), h("div", { class: "scroll" }, [tb])]));
  }

  // ---- orchestration
  function draw() {
    if (!R.open) return;
    build();
    var empty = $("rd-empty"), body = $("rd-body");
    if (!R.ix || !R.files.length) {
      empty.textContent = R.ix ? "No reader data in this window yet. Day files appear after the first build that processes site logs." : "No reader data yet. The build writes system/admin/data/readers/ once the site's ping and logs are processed.";
      empty.hidden = false; body.hidden = true;
      return;
    }
    empty.hidden = true; body.hidden = false;
    var dm = byDay(scopeFiles());
    drawTiles(dm); drawTrends(dm);
    drawTop(); drawShares(); drawNever(); drawTime();
  }
  function show(name) {
    var rd = name === "readers";
    $("view-ops").hidden = rd; root.hidden = !rd;
    [["ops", !rd], ["readers", rd]].forEach(function (x) { var b = $("tab-" + x[0]); b.setAttribute("aria-selected", String(x[1])); b.tabIndex = x[1] ? 0 : -1; });
    try { history.replaceState(null, "", rd ? "#readers" : location.pathname + location.search); } catch (e) {}
    K.hideTip();
    if (rd && !R.open) { R.open = true; build(); Promise.all([loadCatalog(), load()]).then(draw); }
    else if (rd) draw();
  }
  function init() {
    $("tab-ops").addEventListener("click", function () { show("ops"); });
    $("tab-readers").addEventListener("click", function () { show("readers"); });
    document.querySelector(".tabs").addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      var to = $("tab-readers").getAttribute("aria-selected") === "true" ? "ops" : "readers";
      show(to); $("tab-" + to).focus();
    });
    $("win").addEventListener("click", function () { if (R.open) load(); });
    $("ed").addEventListener("change", function () { if (R.open) draw(); });
    var rt;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (R.open && !root.hidden && R.files.length) draw(); }, 150); });
    window.addEventListener("hashchange", function () { var rd = location.hash === "#readers"; if (rd !== ($("tab-readers").getAttribute("aria-selected") === "true")) show(rd ? "readers" : "ops"); });
    if (location.hash === "#readers") show("readers");
  }
  init();
})();
