// vedit review probe: injected into the review copy of index.html (never into .vedit/hf/).
// It wraps the HyperFrames player's seek; after each seek it measures every visible graphic host
// (text boxes, rendered px size, colour) and, once, every graphic's GSAP tweens, and posts them as JSON
// to vedit's receiver on 127.0.0.1 with a synchronous XHR (delivered before the screenshot is taken).
(function () {
  var SINK = "__VEDIT_SINK__";
  var sentTimelines = false;
  function post(obj) {
    try {
      var x = new XMLHttpRequest();
      x.open("POST", SINK, false);
      x.setRequestHeader("Content-Type", "text/plain");
      x.send(JSON.stringify(obj));
    } catch (e) {
      try { navigator.sendBeacon(SINK, JSON.stringify(obj)); } catch (e2) {}
    }
  }
  function tweensOf(tl) {
    var out = [];
    function walk(node, off) {
      var kids = node.getChildren ? node.getChildren(false, true, true) : [];
      for (var i = 0; i < kids.length; i++) {
        var k = kids[i];
        var s = off + k.startTime();
        if (k.getChildren) { walk(k, s); continue; }
        var v = k.vars || {};
        var keys = Object.keys(v).filter(function (n) {
          return ["duration", "ease", "delay", "stagger", "overwrite", "immediateRender", "onComplete",
                  "onUpdate", "onStart", "callbackScope", "data", "id", "repeat", "yoyo", "paused"].indexOf(n) < 0;
        });
        out.push({ s: +s.toFixed(4), d: +k.totalDuration().toFixed(4), keys: keys,
                   opacity: "opacity" in v ? Number(v.opacity) : (("autoAlpha" in v) ? Number(v.autoAlpha) : null),
                   ease: String(v.ease || "") });
      }
    }
    try { walk(tl, 0); } catch (e) {}
    return out;
  }
  function timelines() {
    var tls = window.__timelines || {}, out = {};
    Object.keys(tls).forEach(function (id) {
      if (id === "main") return;
      out[id] = { dur: tls[id].duration ? tls[id].duration() : null, tweens: tweensOf(tls[id]) };
    });
    return out;
  }
  function opacityChain(el, stop) {
    var o = 1;
    for (var e = el; e && e !== document.documentElement; e = e.parentElement) {
      var cs = getComputedStyle(e);
      if (cs.display === "none" || cs.visibility === "hidden") return 0;
      o *= parseFloat(cs.opacity);
      if (e === stop) break;
    }
    return o;
  }
  function scaleOf(el) {
    if (el instanceof SVGElement) {
      var m = el.getScreenCTM && el.getScreenCTM();
      return m ? Math.sqrt(m.c * m.c + m.d * m.d) : 1;
    }
    var r = el.getBoundingClientRect();
    return el.offsetHeight > 0 ? r.height / el.offsetHeight : 1;
  }
  function measureHost(host) {
    var texts = [], seen = new Map();
    var walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
    for (var n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.nodeValue || !n.nodeValue.trim()) continue;
      var el = n.parentElement;
      if (!el || el.closest("style,script,template")) continue;
      var op = opacityChain(el, null);
      if (op < 0.05) continue;
      var rg = document.createRange();
      rg.selectNodeContents(n);
      var rs = Array.from(rg.getClientRects()).filter(function (r) { return r.width > 0 && r.height > 0; });
      if (!rs.length) continue;
      var x0 = Math.min.apply(null, rs.map(function (r) { return r.left; }));
      var y0 = Math.min.apply(null, rs.map(function (r) { return r.top; }));
      var x1 = Math.max.apply(null, rs.map(function (r) { return r.right; }));
      var y1 = Math.max.apply(null, rs.map(function (r) { return r.bottom; }));
      if (x1 < 0 || y1 < 0 || x0 > 1920 || y0 > 1080) continue;
      var cs = getComputedStyle(el);
      var px = parseFloat(cs.fontSize) * scaleOf(el);
      var rec = seen.get(el);
      if (rec) {
        rec.box = [Math.min(rec.box[0], x0), Math.min(rec.box[1], y0), Math.max(rec.box[2], x1), Math.max(rec.box[3], y1)];
        rec.text = (rec.text + " " + n.nodeValue.trim()).slice(0, 60);
        continue;
      }
      rec = { text: n.nodeValue.trim().slice(0, 60), box: [x0, y0, x1, y1], px: px,
              color: cs.webkitTextFillColor && cs.webkitTextFillColor !== cs.color ? cs.webkitTextFillColor : cs.color,
              opacity: op, shadow: cs.textShadow !== "none" };
      seen.set(el, rec);
      texts.push(rec);
    }
    texts.forEach(function (r) { r.box = r.box.map(function (v) { return Math.round(v); }); r.px = +r.px.toFixed(1); r.opacity = +r.opacity.toFixed(2); });
    return texts;
  }
  function measure(t) {
    var hosts = {};
    document.querySelectorAll("[data-composition-src], [data-composition-file]").forEach(function (h) {
      var id = h.getAttribute("data-composition-id");
      if (opacityChain(h, null) < 0.05) return;
      hosts[id] = measureHost(h);
    });
    var msg = { t: t, hosts: hosts };
    if (!sentTimelines) { msg.timelines = timelines(); sentTimelines = true; }
    post(msg);
  }
  function wrap(p, name) {
    var orig = p[name];
    if (typeof orig !== "function" || orig.__vedit) return;
    var w = function (t) {
      var r = orig.apply(this, arguments);
      var at = Number(t);
      setTimeout(function () { measure(at); }, 0);
      return r;
    };
    w.__vedit = true;
    p[name] = w;
  }
  var tries = 0;
  var iv = setInterval(function () {
    var p = window.__player;
    if (p) { wrap(p, "renderSeek"); wrap(p, "seek"); clearInterval(iv); }
    if (++tries > 600) clearInterval(iv);
  }, 25);
})();
