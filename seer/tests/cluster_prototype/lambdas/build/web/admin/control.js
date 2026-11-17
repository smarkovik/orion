(function () {
  "use strict";
  var K = window.AdminKit;
  if (!K) return;
  var $ = K.$, h = K.h;
  var BASE = "/system/control/";
  var KEY = "seer.control.token";
  var EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"; // CloudFront signs POSTs to a function URL with this
  var DAYS = 14;
  var data = null;
  var timer = null;

  function usd(n) { return "$" + (n < 0.1 ? n.toFixed(4) : n.toFixed(2)); }
  function getToken() { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function setToken(t) { try { if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY); } catch (e) {} }
  function say(t, bad) { var m = $("ctlmsg"); m.textContent = t || ""; m.className = "ctlmsg" + (bad ? " bad" : ""); }

  function api(method, path) {
    var headers = { "x-seer-token": getToken() };
    if (method === "POST") headers["x-amz-content-sha256"] = EMPTY_SHA256;
    return fetch(BASE + path, { method: method, headers: headers, cache: "no-store" }).then(function (r) {
      return r.text().then(function (t) {
        var body = null;
        try { body = JSON.parse(t); } catch (e) {}
        return { status: r.status, body: body };
      });
    });
  }

  function tile(k, v, sub, status, label) {
    return h("div", { class: "tile " + (status || "") }, [h("div", { class: "k", text: k }), h("div", { class: "v", text: v }), label ? h("div", { class: "st", text: label }) : h("span"), h("div", { class: "s", text: sub || "" })]);
  }

  function render() {
    var box = $("logcost"), t = $("invocations");
    box.textContent = "";
    t.textContent = "";
    if (!data) return;
    var f = data.by_function || {}, n = 0, failed = 0;
    Object.keys(f).forEach(function (k) { n += f[k].invocations; failed += f[k].failed; });
    box.appendChild(tile("Lambda cost, last " + data.days + " days", usd(data.total_usd), Object.keys(f).map(function (k) { return k + " " + usd(f[k].usd); }).join(" · ") + " · " + n + " invocations"));
    box.appendChild(tile("Failed invocations", String(failed), failed ? usd(data.failed_usd) + " billed for runs that failed or timed out" : "none in this window", failed ? "warn" : "ok", failed ? "Check" : "OK"));
    var s = data.sync || {};
    var last = s.last_scrape_start ? Date.parse(s.last_scrape_start) : 0;
    var wait = last ? Math.ceil((last + s.cooldown_s * 1000 - Date.now()) / 60000) : 0;
    box.appendChild(tile("Sync", wait > 0 ? "in " + wait + " min" : "ready", "cooldown " + Math.round(s.cooldown_s / 60) + " min · " + s.scrape_starts_24h + " of " + s.max_per_day + " scrape starts in 24 h" + (last ? " · last " + K.pad(new Date(last).getHours()) + ":" + K.pad(new Date(last).getMinutes()) : "")));

    var cols = ["Start", "Function", "Edition", "Status", "Billed", "Memory", "Cost"];
    t.appendChild(h("thead", {}, [h("tr", {}, cols.map(function (c, i) { return h("th", { text: c, class: i < 4 ? "l" : "" }); }))]));
    var tb = h("tbody");
    data.invocations.slice(0, 40).forEach(function (r) {
      var d = new Date(r.start);
      var pill = h("span", { class: "pill " + (r.status === "ok" ? "ok" : "bad"), text: r.status });
      if (r.error) pill.title = r.error;
      tb.appendChild(h("tr", { class: r.status === "ok" ? "" : "attn" }, [
        h("td", { class: "l", text: K.pad(d.getMonth() + 1) + "-" + K.pad(d.getDate()) + " " + K.pad(d.getHours()) + ":" + K.pad(d.getMinutes()) + ":" + K.pad(d.getSeconds()) }),
        h("td", { class: "l", text: r.fn }), h("td", { class: "l", text: (r.editions || []).join(" + ") || "–" }), h("td", { class: "l" }, [pill]),
        h("td", { text: (r.billed_ms / 1000).toFixed(1) + " s" }), h("td", { text: r.memory_mb + " MB" }), h("td", { text: usd(r.usd) })]));
    });
    if (!data.invocations.length) tb.appendChild(h("tr", {}, [h("td", { class: "l", colspan: cols.length, text: "No invocations in the logs for this window." })]));
    t.appendChild(tb);
  }

  function load() {
    if (!getToken()) { data = null; render(); say("Set the token to load Lambda cost and use Sync (button Token)."); return Promise.resolve(); }
    return api("GET", "cost?days=" + DAYS).then(function (r) {
      if (r.status === 200) { data = r.body; say(""); render(); if (K.drawRuns) K.drawRuns(); }
      else if (r.status === 401) say("The token was rejected. Use the Token button to enter it again.", true);
      else if (r.status === 404) say("Sync and Lambda cost are only available on the deployed site.");
      else say("Could not load Lambda cost (HTTP " + r.status + ").", true);
    }).catch(function () { say("Sync and Lambda cost are only available on the deployed site."); });
  }

  function sync() {
    if (!getToken()) { askToken(); if (!getToken()) return; }
    var b = $("sync");
    b.disabled = true;
    say("Starting…");
    api("POST", "sync").then(function (r) {
      var j = r.body || {};
      if (r.status === 202) {
        say("Started " + j.started.join(" and ") + ". The build follows by itself; this page reloads the data in about two minutes.");
        clearTimeout(timer);
        timer = setTimeout(function () { load(); if (K.refresh) K.refresh(); }, 120000);
      } else if (r.status === 429 && j.error === "cooldown") say("Cooldown: try again in " + Math.ceil(j.retry_after_s / 60) + " min.", true);
      else if (r.status === 429) say("Daily limit reached (" + (j.message || "") + ").", true);
      else if (r.status === 401) say("The token was rejected. Use the Token button to enter it again.", true);
      else say("Sync failed (HTTP " + r.status + ").", true);
    }).catch(function () { say("Sync is only available on the deployed site.", true); }).then(function () { b.disabled = false; load(); });
  }

  function askToken() {
    var t = window.prompt("Control token (from seer/README.md). Empty clears it.", getToken());
    if (t !== null) { setToken(t.trim()); load(); }
  }

  // Cost of one run from the logs: its share of the build invocation that built it (by run id) and of the scrape
  // invocation that fetched it (same edition, started inside it). A sync's two editions share one of each.
  window.AdminControl = {
    runCost: function (run) {
      if (!data) return null;
      var t0 = Date.parse(run.scrape_started), sum = 0, hit = false;
      data.invocations.forEach(function (r) {
        var t = Date.parse(r.start), share = 0;
        if (r.fn === "build" && (r.run_ids || []).indexOf(run.run_id) >= 0) share = r.run_ids.length;
        else if (r.fn === "scrape" && (r.editions || []).indexOf(run._ed) >= 0 && t0 >= t - 20000 && t0 <= t + r.duration_ms + 20000) share = r.editions.length;
        if (share) { sum += r.usd / share; hit = true; }
      });
      return hit ? sum : null;
    }
  };

  $("sync").addEventListener("click", sync);
  $("tok").addEventListener("click", askToken);
  if (location.protocol !== "file:") load();
})();
