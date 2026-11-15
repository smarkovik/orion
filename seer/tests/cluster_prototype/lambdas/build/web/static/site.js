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

  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var tag = (e.target && e.target.tagName) || "";
    if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
    var rel = e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : "";
    var link = rel && document.querySelector('a[rel="' + rel + '"]');
    if (link) window.location.href = link.href;
  });
})();
