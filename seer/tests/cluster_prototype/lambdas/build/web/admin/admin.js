(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var $ = function (id) { return document.getElementById(id); };
  var state = { days: 14, ed: "all", index: null, runs: [] };
  var files = {};
  var tip = $("tip");

  function h(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") e.textContent = attrs[k];
      else if (k === "class") e.className = attrs[k];
      else e.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { e.appendChild(c); });
    return e;
  }
  function s(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") e.textContent = attrs[k];
      else e.setAttribute(k, attrs[k]);
    });
    if (parent) parent.appendChild(e);
    return e;
  }
  function num(n, d) {
    if (n == null || isNaN(n)) return "–";
    if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(1) + " G";
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + " M";
    if (Math.abs(n) >= 1e4) return (n / 1e3).toFixed(1) + " k";
    return n.toLocaleString("en", { maximumFractionDigits: d == null ? 0 : d });
  }
  function usd(n) { return "$" + (n < 0.1 ? n.toFixed(4) : n.toFixed(2)); }
  function bytes(n) {
    if (n >= 1e9) return (n / 1e9).toFixed(2) + " GB";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + " MB";
    return (n / 1e3).toFixed(0) + " kB";
  }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function dkey(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function hm(t) { var d = new Date(t); return pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes()); }
  function ago(ms) {
    var m = Math.round(ms / 60000);
    if (m < 90) return m + " min ago";
    if (m < 2880) return Math.round(m / 60) + " h ago";
    return Math.round(m / 1440) + " days ago";
  }
  function tzParts(tz, t) {
    try {
      var p = {};
      new Intl.DateTimeFormat("en-CA", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit" })
        .formatToParts(new Date(t)).forEach(function (x) { p[x.type] = x.value; });
      return { date: p.year + "-" + p.month + "-" + p.day, hour: +p.hour };
    } catch (e) { return { date: dkey(new Date(t)), hour: new Date(t).getHours() }; }
  }
  function sum(a, f) { return a.reduce(function (t, x) { return t + (f ? f(x) : x); }, 0); }
  function srcSum(run, k) { var o = run.scrape.sources; return sum(Object.keys(o), function (d) { return o[d][k] || 0; }); }
  function slot(i) { return "var(--s" + ((i % 8) + 1) + ")"; }

  // ---- data
  function getJson(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function dayFile(ed, day) {
    var k = ed + "/" + day;
    if (!files[k]) files[k] = getJson("data/" + ed + "/" + day + ".json");
    return files[k];
  }
  function dates(back, from) {
    var out = [], d = new Date(from || Date.now());
    for (var i = 0; i < back; i++) { out.push(dkey(d)); d.setDate(d.getDate() - 1); }
    return out.reverse();
  }
  function load() {
    $("charts").classList.add("stale");
    var eds = Object.keys(state.index.editions);
    var now = new Date();
    var need = Math.max(state.days, now.getDate());
    var wanted = dates(need);
    var jobs = [];
    eds.forEach(function (ed) {
      state.index.editions[ed].days.forEach(function (d) {
        if (wanted.indexOf(d) >= 0) jobs.push(dayFile(ed, d));
      });
    });
    return Promise.all(jobs).then(function (docs) {
      var runs = [];
      docs.forEach(function (doc) {
        if (!doc) return;
        doc.runs.forEach(function (r) { r._day = doc.date; r._t = Date.parse(r.built_at); r._ed = doc.edition; runs.push(r); });
      });
      runs.sort(function (a, b) { return a._t - b._t; });
      state.runs = runs;
      $("charts").classList.remove("stale");
    });
  }
  function scoped() {
    var from = dates(state.days)[0];
    return state.runs.filter(function (r) { return r._day >= from && (state.ed === "all" || r._ed === state.ed); });
  }
  function edList() { return state.ed === "all" ? Object.keys(state.index.editions) : [state.ed]; }
  function edColor(ed) { return slot(Object.keys(state.index.editions).indexOf(ed)); }

  // ---- tooltip
  function showTip(head, rows, x, y) {
    tip.textContent = "";
    tip.appendChild(h("div", { class: "h", text: head }));
    rows.forEach(function (r) {
      var row = h("div", { class: "r" }, [h("i", { style: "border-color:" + r.color + (r.dash ? ";border-top-style:dashed" : "") }), h("b", { text: r.value }), h("span", { text: r.name })]);
      tip.appendChild(row);
    });
    tip.hidden = false;
    var w = tip.offsetWidth, hh = tip.offsetHeight;
    var left = x + 14, top = y - hh - 10;
    if (left + w > innerWidth - 8) left = x - w - 14;
    if (left < 8) left = 8;
    if (top < 8) top = y + 16;
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }
  function hideTip() { tip.hidden = true; }

  // ---- chart frame
  function niceMax(v) {
    if (v <= 0) return 1;
    var p = Math.pow(10, Math.floor(Math.log10(v))), f = v / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }
  function frame(card, spec) {
    var plot = card.querySelector(".plot");
    plot.textContent = "";
    var legend = card.querySelector(".legend");
    legend.textContent = "";
    var tb = card.querySelector("details.tbl");
    if (tb) tb.remove();
    if (!spec || !spec.series.length || !spec.n) {
      plot.appendChild(h("p", { class: "empty", text: "No data in this window yet." }));
      return null;
    }
    if (spec.series.length > 1) {
      spec.series.forEach(function (se) {
        legend.appendChild(h("span", {}, [h("i", { class: spec.kind === "lines" ? "ln" + (se.dash ? " dash" : "") : "", style: spec.kind === "lines" ? "border-color:" + se.color : "background:" + se.color }), document.createTextNode(se.name)]));
      });
    }
    if (spec.table) {
      var t = h("table"), hd = h("tr");
      spec.table.head.forEach(function (c, i) { hd.appendChild(h("th", { text: c, class: i ? "" : "l" })); });
      t.appendChild(hd);
      spec.table.rows.forEach(function (r) {
        var tr = h("tr");
        r.forEach(function (c) { tr.appendChild(h("td", { text: c })); });
        t.appendChild(tr);
      });
      card.appendChild(h("details", { class: "tbl" }, [h("summary", { text: "Table view" }), h("div", { class: "scroll" }, [t])]));
    }
    return plot;
  }
  function geometry(plot, spec) {
    var W = Math.max(plot.clientWidth || 600, 520), H = 230;
    var m = { l: 46, r: spec.endLabels ? 74 : 12, t: 10, b: 28 };
    return { W: W, H: H, m: m, iw: W - m.l - m.r, ih: H - m.t - m.b };
  }
  function axes(svg, g, ymax, fmt) {
    for (var i = 0; i <= 4; i++) {
      var y = g.m.t + g.ih - (g.ih * i) / 4;
      s("line", { x1: g.m.l, x2: g.W - g.m.r, y1: y, y2: y, style: "stroke:" + (i ? "var(--grid)" : "var(--axis)"), "stroke-width": 1 }, svg);
      s("text", { x: g.m.l - 6, y: y + 4, "text-anchor": "end", text: (fmt || num)((ymax * i) / 4) }, svg);
    }
  }
  function attach(svg, g, xs, labelsFn, onShow, onHide) {
    var active = -1;
    function nearest(px) {
      var lo = 0, hi = xs.length - 1;
      while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (xs[mid] < px) lo = mid; else hi = mid; }
      return Math.abs(xs[lo] - px) <= Math.abs(xs[hi] - px) ? lo : hi;
    }
    function show(i, cx, cy) {
      active = i;
      onShow(i);
      var r = svg.getBoundingClientRect();
      var sc = r.width / g.W;
      var res = labelsFn(i);
      showTip(res.head, res.rows, cx == null ? r.left + xs[i] * sc : cx, cy == null ? r.top + g.m.t * sc + 30 : cy);
    }
    svg.addEventListener("pointermove", function (e) {
      var r = svg.getBoundingClientRect();
      var px = (e.clientX - r.left) * (g.W / r.width);
      show(nearest(px), e.clientX, e.clientY);
    });
    svg.addEventListener("pointerleave", function () { onHide(); hideTip(); active = -1; });
    svg.addEventListener("blur", function () { onHide(); hideTip(); active = -1; });
    svg.addEventListener("focus", function () { if (active < 0) show(xs.length - 1); });
    svg.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
      e.preventDefault();
      var i = active < 0 ? xs.length - 1 : active;
      i = e.key === "Home" ? 0 : e.key === "End" ? xs.length - 1 : Math.max(0, Math.min(xs.length - 1, i + (e.key === "ArrowLeft" ? -1 : 1)));
      show(i);
    });
  }
  function xlabels(svg, g, xs, labels) {
    var step = Math.max(1, Math.ceil((xs.length * 64) / g.iw));
    labels.forEach(function (t, i) {
      if (i % step === 0) s("text", { x: xs[i], y: g.H - 8, "text-anchor": "middle", text: t }, svg);
    });
  }

  // bars: spec {title, cats:[label], series:[{name,color,vals}], fmt}
  function bars(card, spec) {
    spec.n = spec.cats.length;
    var plot = frame(card, spec);
    if (!plot) return;
    var g = geometry(plot, spec), n = spec.n;
    var tot = spec.cats.map(function (_, i) { return sum(spec.series, function (se) { return se.vals[i]; }); });
    var ymax = niceMax(Math.max.apply(null, tot));
    if (!(Math.max.apply(null, tot) > 0)) { plot.textContent = ""; plot.appendChild(h("p", { class: "empty", text: "Nothing to show in this window." })); return; }
    var svg = s("svg", { width: g.W, height: g.H, viewBox: "0 0 " + g.W + " " + g.H, tabindex: 0, role: "img", "aria-label": spec.title });
    plot.appendChild(svg);
    axes(svg, g, ymax, spec.fmt);
    var slotw = g.iw / n, bw = Math.max(2, Math.min(28, slotw * 0.72));
    var xs = spec.cats.map(function (_, i) { return g.m.l + slotw * (i + 0.5); });
    var hl = s("rect", { y: g.m.t, height: g.ih, width: slotw, style: "fill:var(--ink);opacity:0.07", visibility: "hidden" }, svg);
    spec.cats.forEach(function (_, i) {
      var y = g.m.t + g.ih;
      spec.series.forEach(function (se) {
        var v = se.vals[i];
        if (!(v > 0)) return;
        var hgt = Math.max(1, (v / ymax) * g.ih - 2);
        y -= hgt + 2;
        s("rect", { x: xs[i] - bw / 2, y: y + 2, width: bw, height: hgt, rx: Math.min(3, bw / 2), style: "fill:" + se.color }, svg);
      });
    });
    xlabels(svg, g, xs, spec.cats);
    attach(svg, g, xs, function (i) {
      var rows = spec.series.map(function (se) { return { color: se.color, name: se.name, value: (spec.fmt || num)(se.vals[i], 2) }; }).reverse();
      if (spec.series.length > 1) rows.push({ color: "var(--axis)", name: "total", value: (spec.fmt || num)(tot[i], 2) });
      return { head: spec.cats[i], rows: rows };
    }, function (i) { hl.setAttribute("x", xs[i] - slotw / 2); hl.setAttribute("visibility", "visible"); }, function () { hl.setAttribute("visibility", "hidden"); });
  }

  // lines: spec {series:[{name,color,dash,pts:[[t,y]]}]}
  function lines(card, spec) {
    spec.series = spec.series.filter(function (se) { return se.pts.length; });
    spec.n = spec.series.length ? 1 : 0;
    spec.endLabels = spec.series.length > 1 && spec.series.length <= 4;
    var plot = frame(card, spec);
    if (!plot) return;
    var g = geometry(plot, spec);
    var all = [];
    spec.series.forEach(function (se) { se.pts.forEach(function (p) { all.push(p[0]); }); });
    var ts = all.filter(function (v, i) { return all.indexOf(v) === i; }).sort(function (a, b) { return a - b; });
    var t0 = ts[0], t1 = ts[ts.length - 1] || t0 + 1;
    if (t1 === t0) t1 = t0 + 1;
    var ymaxRaw = Math.max.apply(null, spec.series.map(function (se) { return Math.max.apply(null, se.pts.map(function (p) { return p[1]; })); }));
    var ymax = niceMax(ymaxRaw);
    var X = function (t) { return g.m.l + ((t - t0) / (t1 - t0)) * g.iw; };
    var Y = function (v) { return g.m.t + g.ih - (v / ymax) * g.ih; };
    var svg = s("svg", { width: g.W, height: g.H, viewBox: "0 0 " + g.W + " " + g.H, tabindex: 0, role: "img", "aria-label": spec.title });
    plot.appendChild(svg);
    axes(svg, g, ymax, spec.fmt);
    var xs = ts.map(X);
    for (var i = 0; i <= 4; i++) {
      var t = t0 + ((t1 - t0) * i) / 4;
      s("text", { x: X(t), y: g.H - 8, "text-anchor": i === 0 ? "start" : i === 4 ? "end" : "middle", text: hm(t) }, svg);
    }
    var cross = s("line", { y1: g.m.t, y2: g.m.t + g.ih, style: "stroke:var(--ink2)", "stroke-width": 1, visibility: "hidden" }, svg);
    var dots = spec.series.map(function (se) { return s("circle", { r: 4, style: "fill:" + se.color + ";stroke:var(--surface)", "stroke-width": 2, visibility: "hidden" }, svg); });
    var ends = [];
    spec.series.forEach(function (se) {
      var d = se.pts.map(function (p, k) { return (k ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1); }).join("");
      s("path", { d: d, fill: "none", "stroke-width": 2, "stroke-linejoin": "round", "stroke-dasharray": se.dash ? "5 4" : "none", style: "stroke:" + se.color }, svg);
      var last = se.pts[se.pts.length - 1];
      if (se.pts.length === 1) s("circle", { cx: X(last[0]), cy: Y(last[1]), r: 4, style: "fill:" + se.color }, svg);
      ends.push({ se: se, y: Y(last[1]) });
    });
    if (spec.endLabels) {
      ends.sort(function (a, b) { return a.y - b.y; });
      var prev = -99;
      ends.forEach(function (e) {
        var y = Math.max(e.y, prev + 13);
        prev = y;
        s("text", { x: g.W - g.m.r + 6, y: y + 4, class: "lbl", text: e.se.short || e.se.name }, svg);
      });
    }
    function nearestPt(se, t) {
      var best = se.pts[0];
      se.pts.forEach(function (p) { if (Math.abs(p[0] - t) < Math.abs(best[0] - t)) best = p; });
      return best;
    }
    attach(svg, g, xs, function (i) {
      var rows = [];
      spec.series.forEach(function (se) {
        var p = nearestPt(se, ts[i]);
        if (Math.abs(p[0] - ts[i]) > (t1 - t0) / 40 + 3600000) return;
        rows.push({ color: se.color, dash: se.dash, name: se.name, value: (spec.fmt || num)(p[1], 2) });
      });
      return { head: hm(ts[i]), rows: rows };
    }, function (i) {
      cross.setAttribute("x1", xs[i]); cross.setAttribute("x2", xs[i]); cross.setAttribute("visibility", "visible");
      spec.series.forEach(function (se, k) {
        var p = nearestPt(se, ts[i]);
        var near = Math.abs(p[0] - ts[i]) <= (t1 - t0) / 40 + 3600000;
        dots[k].setAttribute("visibility", near ? "visible" : "hidden");
        dots[k].setAttribute("cx", X(p[0])); dots[k].setAttribute("cy", Y(p[1]));
      });
    }, function () { cross.setAttribute("visibility", "hidden"); dots.forEach(function (d) { d.setAttribute("visibility", "hidden"); }); });
  }

  // ---- charts
  var CHARTS = [
    ["new", "New articles per day", "Articles first seen by the scraper, per day and edition"],
    ["stories", "Open and multi-source stories", "Per run. Solid: open stories. Dashed: stories with 2+ outlets"],
    ["sizes", "Story size distribution", "Open stories by number of articles, as of the last run of each day"],
    ["growth", "Growth of the largest stories", "Article count per run for stories that were in a top 5 (latest 8)"],
    ["duration", "Run duration", "Seconds per run: scrape and build (latest 60 runs)"],
    ["phases", "Build phases", "Seconds per phase of the build (latest 60 runs)"],
    ["thumbs", "Thumbnails per day", "Fetched and failed downloads"],
    ["cost", "Estimated cost per day", "List prices; storage is the accrued cost of the data added that day. Estimate"],
    ["storage", "Storage added", "Cumulative GB added by type since the start of the window"]
  ];
  function perDay(runs, days, ed, f) {
    return days.map(function (d) { return sum(runs.filter(function (r) { return r._day === d && r._ed === ed; }), f); });
  }
  function drawCharts() {
    var runs = scoped(), days = dates(state.days), eds = edList();
    var spec = {};
    spec["new"] = { kind: "bars", cats: days.map(function (d) { return d.slice(5); }), series: eds.map(function (e) { return { name: e, color: edColor(e), vals: perDay(runs, days, e, function (r) { return srcSum(r, "new"); }) }; }) };
    var st = [];
    eds.forEach(function (e) {
      var rs = runs.filter(function (r) { return r._ed === e; });
      st.push({ name: e + " open", short: e + " open", color: edColor(e), pts: rs.map(function (r) { return [r._t, r.stories.open]; }) });
      st.push({ name: e + " 2+ outlets", short: e + " 2+", color: edColor(e), dash: true, pts: rs.map(function (r) { return [r._t, r.stories.multi_source]; }) });
    });
    spec.stories = { kind: "lines", series: st };
    var names = ["1 article", "2", "3-4", "5-9", "10+"], keys = ["1", "2", "3-4", "5-9", "10+"];
    spec.sizes = { kind: "bars", cats: days.map(function (d) { return d.slice(5); }), series: keys.map(function (k, i) {
      return { name: names[i], color: "var(--q" + (i + 1) + ")", vals: days.map(function (d) {
        return sum(eds, function (e) {
          var rs = runs.filter(function (r) { return r._day === d && r._ed === e; });
          return rs.length ? rs[rs.length - 1].stories.size_buckets[k] || 0 : 0;
        });
      }) };
    }) };
    var tops = {};
    runs.forEach(function (r) {
      (r.stories.top || []).forEach(function (x) {
        var id = x[0];
        tops[id] = tops[id] || { id: id, title: x[3], pts: [], last: 0 };
        tops[id].pts.push([r._t, x[1]]);
        tops[id].last = r._t;
        tops[id].title = x[3];
      });
    });
    var grow = Object.keys(tops).map(function (k) { return tops[k]; }).sort(function (a, b) { return b.last - a.last; }).slice(0, 8);
    spec.growth = { kind: "lines", series: grow.map(function (t, i) { return { name: t.id + " " + t.title.slice(0, 48), color: slot(i), pts: t.pts }; }) };
    var rr = runs.slice(-60);
    var rl = rr.map(function (r) { return hm(r._t) + " " + r._ed; });
    spec.duration = { kind: "bars", cats: rl, fmt: function (v) { return num(v, 1) + " s"; }, series: [
      { name: "scrape", color: "var(--s1)", vals: rr.map(function (r) { return r.scrape_s; }) },
      { name: "build", color: "var(--s2)", vals: rr.map(function (r) { return r.build_s; }) }] };
    var ph = [["embed", ["embed"]], ["thumbs", ["thumbs"]], ["logos", ["logos"]], ["render", ["render"]], ["other", ["load", "ingest", "assign", "days", "save"]]];
    spec.phases = { kind: "bars", cats: rl, fmt: function (v) { return num(v, 1) + " s"; }, series: ph.map(function (p, i) {
      return { name: p[0], color: slot(i), vals: rr.map(function (r) { return sum(p[1], function (k) { return (r.timings || {})[k] || 0; }); }) };
    }) };
    spec.thumbs = { kind: "bars", cats: days.map(function (d) { return d.slice(5); }), series: [
      { name: "fetched", color: "var(--s1)", vals: days.map(function (d) { return sum(runs.filter(function (r) { return r._day === d; }), function (r) { return r.site.thumbs.fetched || 0; }); }) },
      { name: "failed", color: "var(--s2)", vals: days.map(function (d) { return sum(runs.filter(function (r) { return r._day === d; }), function (r) { return r.site.thumbs.failed || 0; }); }) }] };
    var cd = function (k) { return days.map(function (d) { return sum(runs.filter(function (r) { return r._day === d; }), function (r) { return r.cost[k] || 0; }); }); };
    spec.cost = { kind: "bars", cats: days.map(function (d) { return d.slice(5); }), fmt: function (v) { return usd(v); }, series: [
      { name: "Lambda", color: "var(--s1)", vals: cd("lambda_usd") },
      { name: "S3 requests", color: "var(--s2)", vals: cd("s3_usd") },
      { name: "Storage accrual", color: "var(--s3)", vals: cd("storage_usd") }] };
    var types = ["raw", "archive", "thumbs", "pages"];
    spec.storage = { kind: "lines", fmt: function (v) { return v.toFixed(v < 1 ? 3 : 2) + " GB"; }, series: types.map(function (ty, i) {
      var acc = 0;
      return { name: ty, color: slot(i), pts: days.map(function (d) {
        acc += sum(runs.filter(function (r) { return r._day === d; }), function (r) { return ((r.cost.storage_bytes || {})[ty] || 0) / 1e9; });
        return [Date.parse(d + "T12:00:00"), acc];
      }) };
    }) };
    CHARTS.forEach(function (c) {
      var card = $("c-" + c[0]), sp = spec[c[0]];
      sp.title = c[1];
      sp.table = tableFor(sp);
      (sp.kind === "bars" ? bars : lines)(card, sp);
    });
  }
  function tableFor(sp) {
    if (sp.kind === "bars") {
      var f = sp.fmt || num;
      return { head: ["", ].concat(sp.series.map(function (x) { return x.name; })), rows: sp.cats.map(function (c, i) { return [c].concat(sp.series.map(function (x) { return f(x.vals[i], 2); })); }) };
    }
    var f2 = sp.fmt || num;
    return { head: ["series", "first", "last", "min", "max"], rows: sp.series.filter(function (x) { return x.pts.length; }).map(function (x) {
      var v = x.pts.map(function (p) { return p[1]; });
      return [x.name, f2(v[0], 2), f2(v[v.length - 1], 2), f2(Math.min.apply(null, v), 2), f2(Math.max.apply(null, v), 2)];
    }) };
  }
  function buildCards() {
    var box = $("charts");
    CHARTS.forEach(function (c) {
      box.appendChild(h("div", { class: "card", id: "c-" + c[0] }, [h("h3", { text: c[1] }), h("p", { class: "sub", text: c[2] }), h("div", { class: "legend" }), h("div", { class: "plot" })]));
    });
  }

  // ---- tiles
  function tile(k, v, sub, status, label) {
    return h("div", { class: "tile " + (status || "") }, [h("div", { class: "k", text: k }), h("div", { class: "v", text: v }), label ? h("div", { class: "st", text: label }) : h("span"), h("div", { class: "s", text: sub || "" })]);
  }
  function drawTiles() {
    var box = $("tiles"), now = Date.now(), runs = scoped(), idx = state.index, all = state.runs;
    box.textContent = "";
    var eds = edList(), dayAgo = now - 864e5;
    eds.forEach(function (e) {
      var info = idx.editions[e], last = info.last_run, rs = state.runs.filter(function (r) { return r._ed === e; });
      var t = rs.length ? rs[rs.length - 1]._t : last ? Date.parse(last.at) : 0;
      if (!t) { box.appendChild(tile("Last run · " + e, "–", "no runs yet")); return; }
      var tz = tzParts(info.tz, now), age = now - t, status = "ok", label = "On schedule";
      if (tz.hour >= 8 && tz.hour < 22 && age > 75 * 60000) { status = "warn"; label = "Late"; }
      if (age > 3 * 3600000 && tz.hour >= 8 && tz.hour < 22) { status = "bad"; label = "Stale"; }
      if (tz.hour < 8 || tz.hour >= 22) { if (status === "ok") label = "Off hours"; }
      var ok = last ? last.ok : true;
      box.appendChild(tile("Last run · " + info.name, ago(age), hm(t) + (ok ? "" : " · source errors"), status, label));
    });
    var todayRuns = 0, todayNew = 0, parts = [];
    eds.forEach(function (e) {
      var d = tzParts(idx.editions[e].tz, now).date, rs = state.runs.filter(function (r) { return r._ed === e && r._day === d; });
      todayRuns += rs.length; todayNew += sum(rs, function (r) { return srcSum(r, "new"); });
      parts.push(e + " " + rs.length);
    });
    box.appendChild(tile("Runs today", String(todayRuns), parts.join(" · ")));
    var r24 = all.filter(function (r) { return r._t >= dayAgo && eds.indexOf(r._ed) >= 0; });
    var errs = sum(r24, function (r) { return srcSum(r, "errors"); }), fails = sum(r24, function (r) { return srcSum(r, "failures"); });
    var bad = {};
    r24.forEach(function (r) { Object.keys(r.scrape.sources).forEach(function (d) { var x = r.scrape.sources[d]; if (x.errors || x.failures) bad[r._ed + d] = 1; }); });
    box.appendChild(tile("Errors, last 24 h", String(errs), fails + " failed fetches · " + Object.keys(bad).length + " sources affected", errs ? "warn" : "ok", errs ? "Check sources" : "No errors"));
    box.appendChild(tile("New articles today", num(todayNew), "first seen since local midnight"));
    var open = 0, multi = 0;
    eds.forEach(function (e) {
      var rs = state.runs.filter(function (r) { return r._ed === e; });
      if (rs.length) { open += rs[rs.length - 1].stories.open; multi += rs[rs.length - 1].stories.multi_source; }
    });
    box.appendChild(tile("Open stories now", num(open), num(multi) + " with 2+ outlets"));
    // cost
    var ref = tzParts(idx.editions[Object.keys(idx.editions)[0]].tz, now).date, month = ref.slice(0, 7);
    var dim = new Date(+ref.slice(0, 4), +ref.slice(5, 7), 0).getDate();
    var frac = Math.min(1, ((+ref.slice(8, 10)) - 1 + new Date().getHours() / 24) / dim) || 1 / dim;
    var mtd = sum(all.filter(function (r) { return r._day.slice(0, 7) === month && eds.indexOf(r._ed) >= 0; }), function (r) { return r.cost.total_usd; });
    var share = eds.length / Object.keys(idx.editions).length;
    var fixed = idx.fixed_month_usd * share, cf = idx.cloudfront_month.usd * share;
    var proj = mtd / frac + fixed + cf, mtdAll = mtd + (fixed + cf) * frac;
    box.appendChild(tile("Estimated cost, month to date", usd(mtdAll), "runs " + usd(mtd) + " · fixed + CloudFront prorated " + usd((fixed + cf) * frac), "", ""));
    var t2 = tile("Projected for the month", usd(proj), "runs " + usd(mtd / frac) + " · fixed " + usd(fixed) + " · CloudFront " + usd(cf) + " at " + num(idx.assumed_views_month) + " views (" + idx.cloudfront_month.gb + " GB)");
    t2.appendChild(h("div", { class: "s", text: "Estimate, list prices before free tier." }));
    box.appendChild(t2);
  }

  // ---- tables
  var sortKey = "new", sortDir = -1;
  function drawSources() {
    var t = $("sources"), now = Date.now(), dayAgo = now - 864e5, runs = scoped(), rows = {};
    runs.forEach(function (r) {
      Object.keys(r.scrape.sources).forEach(function (d) {
        var x = r.scrape.sources[d], k = r._ed + "|" + d;
        var o = rows[k] = rows[k] || { ed: r._ed, domain: d, new: 0, fetched: 0, failures: 0, errors: 0, runs: 0, errRuns: 0, days: {}, lastErr: 0, new24: 0, err24: 0, runs24: 0 };
        o.new += x.new; o.fetched += x.fetched; o.failures += x.failures; o.errors += x.errors; o.runs++;
        o.days[r._day] = (o.days[r._day] || 0) + x.new;
        if (x.errors) { o.errRuns++; o.lastErr = r._t; }
        if (r._t >= dayAgo) { o.new24 += x.new; o.err24 += x.errors; o.runs24++; }
      });
    });
    var list = Object.keys(rows).map(function (k) {
      var o = rows[k];
      o.rate = o.runs ? (100 * o.errRuns) / o.runs : 0;
      o.zero = Object.keys(o.days).filter(function (d) { return !o.days[d]; }).length;
      o.attn = o.err24 > 0 || (o.runs24 > 0 && o.new24 === 0);
      return o;
    });
    list.sort(function (a, b) {
      var x = a[sortKey], y = b[sortKey];
      return (typeof x === "string" ? x.localeCompare(y) : x - y) * sortDir || a.domain.localeCompare(b.domain);
    });
    var cols = [["domain", "Outlet", 1], ["ed", "Edition", 1], ["new", "New articles"], ["fetched", "Fetched"], ["failures", "Failures"], ["errors", "Errors"], ["rate", "Runs with errors"], ["zero", "Days with no new"], ["lastErr", "Last error run"]];
    t.textContent = "";
    var hd = h("tr");
    cols.forEach(function (c) {
      var b = h("button", { type: "button", text: c[1] });
      if (sortKey === c[0]) b.setAttribute("data-dir", sortDir > 0 ? "asc" : "desc");
      b.addEventListener("click", function () { if (sortKey === c[0]) sortDir = -sortDir; else { sortKey = c[0]; sortDir = c[2] ? 1 : -1; } drawSources(); });
      hd.appendChild(h("th", { class: c[2] ? "l" : "", "aria-sort": sortKey === c[0] ? (sortDir > 0 ? "ascending" : "descending") : "none" }, [b]));
    });
    t.appendChild(h("thead", {}, [hd]));
    var tb = h("tbody");
    if (!list.length) tb.appendChild(h("tr", {}, [h("td", { class: "l", colspan: cols.length, text: "No data in this window yet." })]));
    list.forEach(function (o) {
      var vals = [o.domain, o.ed, num(o.new), num(o.fetched), num(o.failures), num(o.errors), o.rate.toFixed(0) + " %", String(o.zero), o.lastErr ? hm(o.lastErr) : "–"];
      var tr = h("tr", { class: o.attn ? "attn" : "" });
      vals.forEach(function (v, i) { tr.appendChild(h("td", { text: v, class: i < 2 ? "l" : "" })); });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
  }
  function drawRuns() {
    var t = $("runs"), runs = scoped().slice(-50).reverse();
    t.textContent = "";
    var cols = ["Time", "Edition", "Status", "Records", "Inserted", "Embedded", "New stories", "Duration", "Cost"];
    t.appendChild(h("thead", {}, [h("tr", {}, cols.map(function (c, i) { return h("th", { text: c, class: i < 3 ? "l" : "" }); }))]));
    var tb = h("tbody");
    if (!runs.length) tb.appendChild(h("tr", {}, [h("td", { class: "l", colspan: cols.length, text: "No runs in this window yet." })]));
    runs.forEach(function (r) {
      var errs = srcSum(r, "errors");
      var btn = h("button", { type: "button", class: "xbtn", "aria-expanded": "false", text: "▸" });
      var tr = h("tr", {}, [
        h("td", { class: "l" }, [btn, document.createTextNode(hm(r._t))]), h("td", { class: "l", text: r._ed }),
        h("td", { class: "l" }, [h("span", { class: "pill " + (errs || r.scrape.truncated ? "bad" : "ok"), text: errs ? errs + " errors" : r.scrape.truncated ? "truncated" : "ok" })]),
        h("td", { text: num(r.scrape.records) }), h("td", { text: num(r.build.inserted) }), h("td", { text: num(r.build.embedded) }),
        h("td", { text: num(r.stories.new) }), h("td", { text: num(r.scrape_s + r.build_s, 0) + " s" }), h("td", { text: usd(r.cost.total_usd) })]);
      var raw = null;
      btn.addEventListener("click", function () {
        if (raw) { raw.remove(); raw = null; btn.textContent = "▸"; btn.setAttribute("aria-expanded", "false"); return; }
        raw = h("tr", { class: "raw" }, [h("td", { colspan: cols.length }, [h("pre", { text: JSON.stringify(r, null, 1) })])]);
        tr.after(raw); btn.textContent = "▾"; btn.setAttribute("aria-expanded", "true");
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
  }

  function draw() {
    drawTiles(); drawCharts(); drawSources(); drawRuns();
    $("stamp").textContent = state.runs.length ? state.runs.length + " runs loaded · data generated " + new Date(state.index.generated).toLocaleString() : "";
  }
  function refresh() { return load().then(draw); }
  function msg(t) { var m = $("msg"); m.textContent = t; m.hidden = !t; }

  function init() {
    buildCards();
    $("win").addEventListener("click", function (e) {
      var b = e.target.closest("button[data-days]");
      if (!b) return;
      state.days = +b.getAttribute("data-days");
      Array.prototype.forEach.call($("win").children, function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      refresh();
    });
    $("ed").addEventListener("change", function () { state.ed = $("ed").value; draw(); });
    $("theme").addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
    var rt;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (state.index) drawCharts(); }, 150); });
    document.addEventListener("scroll", hideTip, { passive: true });
    if (location.protocol === "file:") { msg("This page reads JSON files, which browsers block when it is opened from disk. Serve the site over http (make preview) and open /admin/."); return; }
    getJson("data/index.json").then(function (ix) {
      if (!ix || !ix.editions || !Object.keys(ix.editions).length) { msg("No data yet. The first build writes admin/data/index.json; reload after the next run."); return; }
      state.index = ix;
      $("title").textContent = "Admin";
      if (ix.brand) $("title").appendChild(h("small", { text: ix.brand }));
      document.title = "Admin · " + (ix.brand || "");
      Object.keys(ix.editions).forEach(function (c) { $("ed").appendChild(h("option", { value: c, text: ix.editions[c].name + " (" + c + ")" })); });
      refresh();
    });
  }
  init();
})();
