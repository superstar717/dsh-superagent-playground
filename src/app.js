/* 方法论工作台 前端逻辑（无依赖，vanilla JS） */
(function () {
  "use strict";
  var DATA = window.__WB_DATA__;
  var B = {}; // bloggers by id
  DATA.bloggers.forEach(function (b) { B[b.id] = b; });
  var $ = function (s) { return document.querySelector(s); };
  var main = $("#main"), nav = $("#nav"), crumb = $("#crumb"), qin = $("#q");

  $("#gm-link").href = DATA.graphmind_url;

  var TYPE_COLORS = ["#A6402C", "#33616B", "#B08D3E", "#5E6F45", "#6B4E71", "#8A5A2B", "#4A5A8A"];
  function typeColor(t) {
    if (!t) return "#948A78";
    if (t === "person") return "#A6402C";
    var h = 0;
    for (var i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) >>> 0;
    return TYPE_COLORS[h % TYPE_COLORS.length];
  }
  function pathURL(p) { return "file://" + encodeURI(p || ""); }
  function fileURL(dir, name) {
    if (!dir || !name) return "#";
    return pathURL(dir.replace(/\/$/, "") + "/" + name.split("/").pop());
  }

  /* ---------------- 导航 ---------------- */
  function buildNav() {
    var html = '<div class="nav-sec">总 览</div>';
    html += '<a class="nav-a" data-r="overview"><span class="dot" style="background:#B08D3E"></span>工作台总览</a>';
    html += '<div class="nav-sec">博 主</div>';
    DATA.bloggers.forEach(function (b) {
      var n = b.groups.reduce(function (s, g) { return s + g.items.length; }, 0);
      html += '<a class="nav-a" data-r="b:' + b.id + '"><span class="dot" style="background:' + b.accent + '"></span>' +
        b.name + '<span class="cnt">' + n + " 条</span></a>";
    });
    html += '<div class="nav-sec">图 谱</div>';
    html += '<a class="nav-a" data-r="graph"><span class="dot" style="background:#5E6F45"></span>知识图谱</a>';
    html += '<div class="nav-sec">附 录</div>';
    html += '<a class="nav-a" data-r="about"><span class="dot" style="background:#948A78"></span>数据与口径</a>';
    nav.innerHTML = html;
    nav.addEventListener("click", function (e) {
      var a = e.target.closest(".nav-a");
      if (!a) return;
      var r = a.getAttribute("data-r");
      if (r === "overview") location.hash = "#/overview";
      else if (r === "graph") location.hash = "#/graph";
      else if (r === "about") location.hash = "#/about";
      else if (r.indexOf("b:") === 0) location.hash = "#/b/" + r.slice(2);
    });
  }

  function markNav(route) {
    nav.querySelectorAll(".nav-a").forEach(function (a) {
      var r = a.getAttribute("data-r");
      var on = (r === route.v) || (r === "b:" + route.b && (route.v === "b" || route.v === "item"));
      a.classList.toggle("on", on);
    });
  }

  /* ---------------- 总览 ---------------- */
  function vOverview() {
    crumb.innerHTML = "总览 · <b>两位博主的提炼成果</b>";
    var duo = DATA.bloggers.map(function (b, i) {
      var stats = b.stats.map(function (s) {
        return '<div class="st"><div class="k">' + s.k + '</div><div class="v">' + s.v + "</div></div>";
      }).join("");
      var chips = b.groups.map(function (g) {
        return '<span class="chip">' + g.title + " · " + g.items.length + "</span>";
      }).join("");
      return '<div class="bcard" style="--acc:' + b.accent + ';--i:' + i + '" data-b="' + b.id + '">' +
        '<span class="bseal">' + b.seal + "</span>" +
        "<h3>" + b.name + "</h3>" +
        '<div class="tag">「' + b.tagline + "」</div>" +
        '<div class="statrow">' + stats + "</div>" +
        '<div class="chips">' + chips + "</div>" +
        '<button class="enterbtn" data-b="' + b.id + '">进入阅读 →</button></div>';
    }).join("");
    main.innerHTML = '<div class="view stagger">' +
      '<div class="hero"><h2>方法论工作台</h2><span class="sub">系统 · 框架 · 方法论 —— 提炼成果的陈列与查阅</span></div>' +
      '<div class="duo">' + duo + "</div>" +
      '<div class="flow"><b>数据流向</b><span>kb 知识库 / 框架汇总文档 / LightRAG 图谱</span><span class="arr">→</span>' +
      "<span>build.py 只读构建</span><span class=\"arr\">→</span><span>本页（双击即开，离线可用）</span>" +
      '<span class="arr">→</span><span>深度问答走 <a href="' + DATA.graphmind_url + '" target="_blank" rel="noopener">GraphMind</a></span></div>' +
      "</div>";
    main.querySelectorAll(".enterbtn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        location.hash = "#/b/" + btn.getAttribute("data-b");
      });
    });
  }

  /* ---------------- 博主阅读页 ---------------- */
  function findItem(bid, iid) {
    var b = B[bid];
    if (!b) return null;
    for (var gi = 0; gi < b.groups.length; gi++) {
      var g = b.groups[gi];
      for (var ii = 0; ii < g.items.length; ii++) {
        if (g.items[ii].id === iid) return { g: g, it: g.items[ii] };
      }
    }
    return null;
  }

  function vBlogger(bid, iid) {
    var b = B[bid];
    if (!b) { location.hash = "#/overview"; return; }
    if (!iid || !findItem(bid, iid)) iid = b.groups[0].items[0].id;
    var hit = findItem(bid, iid);
    crumb.innerHTML = b.name + " · <b>" + (hit ? hit.it.title : "") + "</b>";

    var list = b.groups.map(function (g) {
      var items = g.items.map(function (it) {
        return '<a class="ia' + (it.id === iid ? " on" : "") + '" data-i="' + it.id + '">' +
          '<span class="badge">' + (it.badge || "") + "</span>" + it.title + "</a>";
      }).join("");
      return '<div class="igroup">' + g.title + "</div>" + items;
    }).join("");

    var refs = "";
    if (hit && hit.it.refs && hit.it.refs.length) {
      refs = '<div class="refrow">' + hit.it.refs.map(function (r) {
        var label = '<span class="d">' + r.date + "</span>" + (r.title ? "《" + r.title + "》" : "");
        if (r.matched) {
          return '<a class="refchip" href="' + fileURL(DATA.graphs[bid].dir, r.file) + '" title="打开本机转写原文">' + label + " ↗</a>";
        }
        return '<span class="refchip unmatched" title="未在本机转写目录中定位到对应文件">' + label + "</span>";
      }).join("") + "</div>";
    }

    var meta = '<div class="a-meta"><span>来源</span><a href="' + pathURL(hit.it.source) + '">' + hit.it.source + "</a></div>";

    main.innerHTML = '<div class="view">' +
      '<div class="intro-note"><b style="font-family:var(--serif)">' + b.name + "</b>　" + b.intro +
      (b.doc_intro ? '<div class="doc-intro md">' + b.doc_intro + "</div>" : "") + "</div>" +
      '<div class="reader"><div class="itemlist">' + list + "</div>" +
      '<div class="article"><div class="a-head"><h2>' + hit.it.title + "</h2>" + meta + "</div>" +
      refs + '<div class="md">' + hit.it.html + "</div></div></div></div>";

    main.querySelectorAll(".ia").forEach(function (a) {
      a.addEventListener("click", function () {
        location.hash = "#/b/" + bid + "/" + a.getAttribute("data-i");
      });
    });
  }

  /* ---------------- 图谱页 ---------------- */
  var G = { ds: "jianghushu", raf: 0, nodes: [], edges: [], selOld: -1, sel: -1, hover: -1, alpha: 0, W: 0, H: 0, N: 420 };

  function vGraph() {
    crumb.innerHTML = "知识图谱 · <b>实体与关系</b>";
    main.innerHTML = '<div class="view"><div class="graph-wrap">' +
      '<div class="gpanel"><div class="gctrl">' +
      '<div class="gtabs">' + DATA.bloggers.map(function (b) {
        var g = DATA.graphs[b.id];
        return '<span class="gtab' + (G.ds === b.id ? " on" : "") + '" data-ds="' + b.id + '" style="--acc:' + b.accent + '">' + g.label + "</span>";
      }).join("") + "</div>" +
      '<input type="search" id="gq" placeholder="搜实体，回车聚焦…">' +
      '<label>核心子图 <input type="range" id="gn" min="100" max="1200" step="20" value="' + G.N + '"><span id="gnv">' + G.N + "</span></label>" +
      '<button class="gbtn" id="gre">重排</button>' +
      '<span class="ghint" id="ghint"></span>' +
      '<span id="glegend" style="display:flex;gap:10px;flex-wrap:wrap"></span></div>' +
      '<canvas id="gcanvas"></canvas></div>' +
      '<div class="gnp" id="gnp"><div class="placeholder">点击节点查看详情；<br>悬停看名称；<br>双击节点聚焦邻域；<br>「重排」回到核心子图。</div></div>' +
      "</div></div>";

    main.querySelectorAll(".gtab").forEach(function (t) {
      t.addEventListener("click", function () { G.ds = t.getAttribute("data-ds"); G.selOld = -1; G.sel = -1; vGraph(); });
    });
    main.querySelector("#gn").addEventListener("input", function (e) {
      G.N = +e.target.value; main.querySelector("#gnv").textContent = G.N;
      loadGraph(false);
    });
    main.querySelector("#gre").addEventListener("click", function () { G.selOld = -1; G.sel = -1; resetPanel(); loadGraph(true); });
    main.querySelector("#gq").addEventListener("keydown", function (e) {
      if (e.key !== "Enter") return;
      var k = e.target.value.trim().toLowerCase();
      if (!k) return;
      var g = DATA.graphs[G.ds];
      var idx = -1, best = -1;
      g.nodes.forEach(function (n, i) {
        var nm = n.n.toLowerCase();
        if (nm === k && idx < 0) idx = i;
        else if (nm.indexOf(k) >= 0 && best < 0) best = i;
      });
      if (idx < 0) idx = best;
      if (idx >= 0) focusNode(idx); else hint("未找到该实体");
    });
    setupCanvas();
    renderLegend();
    loadGraph(true);
  }

  function renderLegend() {
    var g = DATA.graphs[G.ds];
    var cnt = {};
    g.nodes.forEach(function (n) { var t = n.t || "未分类"; cnt[t] = (cnt[t] || 0) + 1; });
    var top = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; }).slice(0, 6);
    var el = main.querySelector("#glegend");
    if (!el) return;
    el.innerHTML = top.map(function (t) {
      return '<span class="lgd"><i style="background:' + typeColor(t === "未分类" ? "" : t) + '"></i>' + t + "</span>";
    }).join("");
  }

  function stopGraphLoop() {
    if (G.raf) { cancelAnimationFrame(G.raf); G.raf = 0; }
  }

  function hint(t) {
    var h = main.querySelector("#ghint");
    if (h) { h.textContent = t; setTimeout(function () { if (h && h.textContent === t) h.textContent = ""; }, 3000); }
  }

  function loadGraph(reinit) {
    var g = DATA.graphs[G.ds];
    var nodes = g.nodes, edges = g.edges;
    var N = Math.min(G.N, nodes.length);
    var keep = {};
    for (var i = 0; i < N; i++) keep[i] = 1;
    if (G.selOld >= 0) {
      keep[G.selOld] = 1;
      edges.forEach(function (e) {
        if (e[0] === G.selOld) keep[e[1]] = 1;
        if (e[1] === G.selOld) keep[e[0]] = 1;
      });
    }
    var idxs = Object.keys(keep).map(Number).sort(function (a, b) { return a - b; });
    var remap = {}; idxs.forEach(function (old, nw) { remap[old] = nw; });
    var prev = {};
    G.nodes.forEach(function (p) { prev[p.old] = [p.x, p.y]; });
    G.nodes = idxs.map(function (old) {
      var n = nodes[old];
      return { n: n.n, t: n.t, d: n.d, f: n.f, deg: n.deg, x: 0, y: 0, vx: 0, vy: 0, old: old };
    });
    G.edges = edges.filter(function (e) { return keep[e[0]] && keep[e[1]]; })
      .map(function (e) { return [remap[e[0]], remap[e[1]], e[2], e[3], e[4]]; });
    var selLocal = G.selOld >= 0 ? remap[G.selOld] : -1;
    G.sel = (selLocal === undefined) ? -1 : selLocal;
    hint("显示 " + G.nodes.length + " 实体 / " + G.edges.length + " 关系（数据集共 " + nodes.length + " 实体 / " + edges.length + " 关系）");
    var c = $("#gcanvas");
    if (!c) return;
    G.W = c.clientWidth; G.H = c.clientHeight;
    G.nodes.forEach(function (n) {
      if (prev[n.old]) { n.x = prev[n.old][0]; n.y = prev[n.old][1]; }
    });
    if (reinit) {
      G.alpha = 1;
      var R = Math.min(G.W, G.H) * 0.42;
      G.nodes.forEach(function (n, i) {
        if (!prev[n.old]) {
          var a = (i / G.nodes.length) * Math.PI * 2, r = R * (0.35 + 0.65 * Math.random());
          n.x = G.W / 2 + Math.cos(a) * r; n.y = G.H / 2 + Math.sin(a) * r;
        }
        n.vx = 0; n.vy = 0;
      });
    }
    stopGraphLoop();
    var tick = function () {
      step(); draw();
      if (G.alpha >= 0.02) { G.raf = requestAnimationFrame(tick); }
      else { G.raf = 0; draw(); } // 力学静止后停帧，省 CPU；交互时按需重绘
    };
    G.raf = requestAnimationFrame(tick);
    if (G.sel >= 0) showNodePanel(G.sel);
  }

  function step() {
    if (G.alpha < 0.02) return;
    var ns = G.nodes, es = G.edges, n = ns.length;
    var k = G.alpha;
    for (var i = 0; i < n; i++) {
      var a = ns[i];
      for (var j = i + 1; j < n; j++) {
        var b = ns[j];
        var dx = b.x - a.x, dy = b.y - a.y;
        var d2 = dx * dx + dy * dy + 40;
        var f = 1800 * k / d2;
        var d = Math.sqrt(d2);
        var fx = dx / d * f, fy = dy / d * f;
        a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
      }
    }
    es.forEach(function (e) {
      var a = ns[e[0]], b = ns[e[1]];
      var dx = b.x - a.x, dy = b.y - a.y;
      var d = Math.sqrt(dx * dx + dy * dy) || 1;
      var rest = 92 - Math.min(30, e[2] * 6);
      var f = (d - rest) * 0.012 * k;
      var fx = dx / d * f, fy = dy / d * f;
      a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
    });
    ns.forEach(function (p) {
      p.vx += (G.W / 2 - p.x) * 0.0045 * k;
      p.vy += (G.H / 2 - p.y) * 0.0045 * k;
      p.vx *= 0.86; p.vy *= 0.86;
      p.x += Math.max(-14, Math.min(14, p.vx));
      p.y += Math.max(-14, Math.min(14, p.vy));
    });
    G.alpha *= 0.985;
  }

  function draw() {
    var c = $("#gcanvas");
    if (!c || !c.clientWidth) return;
    var dpr = window.devicePixelRatio || 1;
    if (c.width !== c.clientWidth * dpr || c.height !== c.clientHeight * dpr) {
      c.width = c.clientWidth * dpr; c.height = c.clientHeight * dpr;
      G.W = c.clientWidth; G.H = c.clientHeight;
    }
    var ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, G.W, G.H);
    var sel = G.sel, ns = G.nodes;
    G.edges.forEach(function (e) {
      var a = ns[e[0]], b = ns[e[1]];
      var on = sel >= 0 && (e[0] === sel || e[1] === sel);
      ctx.strokeStyle = on ? "rgba(166,64,44,.85)" : "rgba(90,80,60," + (sel >= 0 ? 0.05 : 0.13) + ")";
      ctx.lineWidth = on ? 1.2 : 0.5;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    });
    ns.forEach(function (p, i) {
      var r = 2.5 + Math.sqrt(p.deg) * 0.9;
      var col = typeColor(p.t);
      var linked = sel >= 0 && sel !== i && G.edges.some(function (e) {
        return (e[0] === sel && e[1] === i) || (e[1] === sel && e[0] === i);
      });
      if (sel >= 0 && sel !== i) ctx.globalAlpha = linked ? 1 : 0.14;
      ctx.fillStyle = col;
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
      if (sel === i) {
        ctx.strokeStyle = "#26211A"; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(p.x, p.y, r + 3, 0, Math.PI * 2); ctx.stroke();
      }
      if (p.deg >= 42 || sel === i || i === G.hover || (sel >= 0 && linked)) {
        ctx.globalAlpha = sel >= 0 && sel !== i && !linked ? 0.25 : 0.9;
        ctx.font = "11px 'PingFang SC'";
        ctx.fillStyle = "#26211A";
        ctx.fillText(p.n, p.x + r + 3, p.y + 4);
      }
      ctx.globalAlpha = 1;
    });
  }

  function pickNode(mx, my) {
    var best = -1, bd = 144;
    G.nodes.forEach(function (p, i) {
      var dx = p.x - mx, dy = p.y - my, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = i; }
    });
    return best;
  }

  function setupCanvas() {
    var c = $("#gcanvas");
    c.addEventListener("mousemove", function (e) {
      var r = c.getBoundingClientRect();
      var h = pickNode(e.clientX - r.left, e.clientY - r.top);
      if (h !== G.hover) { G.hover = h; if (!G.raf) draw(); }
      c.style.cursor = G.hover >= 0 ? "pointer" : "grab";
    });
    c.addEventListener("click", function (e) {
      var r = c.getBoundingClientRect();
      var i = pickNode(e.clientX - r.left, e.clientY - r.top);
      if (i >= 0) {
        G.sel = i; G.selOld = G.nodes[i].old;
        showNodePanel(i);
      } else {
        G.sel = -1; G.selOld = -1;
        resetPanel();
      }
      if (!G.raf) draw();
    });
    c.addEventListener("dblclick", function (e) {
      var r = c.getBoundingClientRect();
      var i = pickNode(e.clientX - r.left, e.clientY - r.top);
      if (i >= 0) {
        G.selOld = G.nodes[i].old;
        loadGraph(true);
      }
    });
  }

  function focusNode(oldIdx) {
    G.selOld = oldIdx;
    loadGraph(true);
  }

  function resetPanel() {
    var p = $("#gnp");
    if (p) p.innerHTML = '<div class="placeholder">点击节点查看详情；<br>悬停看名称；<br>双击节点聚焦邻域；<br>「重排」回到核心子图。</div>';
  }

  function showNodePanel(localIdx) {
    var g = DATA.graphs[G.ds];
    var lp = G.nodes[localIdx];
    if (!lp) return;
    var n = g.nodes[lp.old];
    var files = (n.f || []).map(function (f) {
      return '<a class="file" href="' + fileURL(g.dir, f) + '">📄 ' + f.split("/").pop() + "</a>";
    }).join("");
    var rel = [];
    G.edges.forEach(function (e) {
      var other = -1;
      if (e[0] === localIdx) other = e[1]; else if (e[1] === localIdx) other = e[0];
      if (other >= 0) rel.push({ other: other, kw: e[3], w: e[2] });
    });
    rel.sort(function (a, b) { return b.w - a.w; });
    var relHtml = rel.slice(0, 8).map(function (r) {
      var nm = G.nodes[r.other] ? G.nodes[r.other].n : "?";
      return '<div class="edge"><b>' + nm + "</b>" + (r.kw ? "　" + r.kw : "") + "</div>";
    }).join("") || '<div class="edge">无（当前子图内）</div>';
    $("#gnp").innerHTML =
      "<h4>" + n.n + "</h4>" +
      '<span class="type">' + (n.t || "未分类") + " · 关联 " + n.deg + "</span>" +
      '<div class="sec">描 述</div><p>' + (n.d || "（无描述）") + "</p>" +
      '<div class="sec">出处文件</div>' + (files || '<p style="color:var(--ink-faint)">未记录</p>') +
      '<div class="sec">主要关联（按权重）</div>' + relHtml +
      '<div style="margin-top:14px"><a class="gbtn" style="display:inline-block;text-decoration:none" href="' + DATA.graphmind_url + '" target="_blank" rel="noopener">在 GraphMind 中追问 ↗</a></div>';
  }

  /* ---------------- 检索 ---------------- */
  function searchAll(qs) {
    qs = qs.trim().toLowerCase();
    if (!qs) return [];
    var res = [];
    DATA.bloggers.forEach(function (b) {
      b.groups.forEach(function (g) {
        g.items.forEach(function (it) {
          var t = (it.title + " " + it.text).toLowerCase();
          var score = 0;
          if (it.title.toLowerCase().indexOf(qs) >= 0) score += 3;
          var pos = t.indexOf(qs);
          if (pos >= 0) score += 1 + Math.min(2, (t.split(qs).length - 1) / 4);
          if (score > 0) res.push({ b: b, g: g, it: it, score: score });
        });
      });
    });
    res.sort(function (a, b2) { return b2.score - a.score; });
    return res.slice(0, 24);
  }

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function hilite(text, qs) {
    var t = esc(text);
    var i = t.toLowerCase().indexOf(qs.toLowerCase());
    if (i < 0) return t;
    return t.slice(0, i) + "<mark>" + t.slice(i, i + qs.length) + "</mark>" + t.slice(i + qs.length);
  }

  function vSearch(qs) {
    crumb.innerHTML = "检索 · <b>" + esc(qs || "…") + "</b>";
    var res = searchAll(qs);
    var body;
    if (!qs.trim()) body = '<div class="empty">输入关键词，跨两位博主的全部框架与方法中即时检索</div>';
    else if (!res.length) body = '<div class="empty">未检索到「' + esc(qs) + "」</div>";
    else {
      body = res.map(function (r, i) {
        var low = r.it.text.toLowerCase();
        var p = low.indexOf(qs.trim().toLowerCase());
        var snip = p >= 0 ? r.it.text.slice(Math.max(0, p - 40), p + 80) : r.it.text.slice(0, 100);
        return '<div class="rcard" data-b="' + r.b.id + '" data-i="' + r.it.id + '" style="--i:' + Math.min(i, 10) + '">' +
          '<div class="rmeta"><span style="color:' + r.b.accent + '">●</span>' + r.b.name + " · " + r.g.title + "</div>" +
          '<div class="rt">' + hilite(r.it.title, qs) + "</div>" +
          '<div class="rsnip">…' + hilite(snip, qs) + "…</div></div>";
      }).join("");
    }
    main.innerHTML = '<div class="view stagger sres">' + body + "</div>";
    main.querySelectorAll(".rcard").forEach(function (c) {
      c.addEventListener("click", function () {
        location.hash = "#/b/" + c.getAttribute("data-b") + "/" + c.getAttribute("data-i");
      });
    });
  }

  /* ---------------- 关于 ---------------- */
  function vAbout() {
    crumb.innerHTML = "附录 · <b>数据与口径</b>";
    var gj = DATA.graphs.jianghushu, gl = DATA.graphs.ligongzi;
    main.innerHTML = '<div class="view about">' +
      "<h2>数据与口径</h2>" +
      '<div class="sec">来 源（全部只读）</div>' +
      '<table class="srctable"><tr><th>内容</th><th>路径</th><th>规模</th></tr>' +
      "<tr><td>姜胡说 · 知识库</td><td><code>~/姜胡说/kb/</code>（SYSTEM + INDEX + 9 主题）</td><td>544 视频 · ≈190 万字</td></tr>" +
      "<tr><td>姜胡说 · 转写原文</td><td><code>~/姜胡说/asr/</code></td><td>600+ 篇</td></tr>" +
      "<tr><td>李公子 · 框架汇总</td><td><code>~/李公子/框架体系汇总-详细版.md</code>、<code>知识金字塔-详细梳理.md</code></td><td>9 框架 + 金字塔详解</td></tr>" +
      "<tr><td>李公子 · 转写原文</td><td><code>" + gl.dir + "</code></td><td>228 条</td></tr>" +
      "<tr><td>图谱 · 姜</td><td><code>" + gj.dataset + "</code></td><td>" + gj.nodes.length + " 实体 / " + gj.edges.length + " 关系</td></tr>" +
      "<tr><td>图谱 · 李</td><td><code>" + gl.dataset + "</code></td><td>" + gl.nodes.length + " 实体 / " + gl.edges.length + " 关系</td></tr></table>" +
      '<div class="sec">刷 新</div>' +
      "<p style='font-size:13px;color:var(--ink-soft)'>数据更新后重新构建即可（只读消费，不改任何源文件）：</p>" +
      "<div class='rebuild'>python3 ~/src/methodology-workbench-6596a21a169f/build.py</div>" +
      '<div class="sec">口径与边界（诚实说明）</div><ul>' +
      "<li>统计口径以 kb/INDEX.md 为准：视频总数 544、ASR 完成 100%（SYSTEM.md 文头写 542，为早期口径）。</li>" +
      "<li>出处链接指向本机转写原文（file://），文件移动或改名后会失效；标注为灰色的条目未定位到对应文件。</li>" +
      "<li>转写为语音识别结果，存在同音误差（如「挨打模型」实为 AIDA、「耐克模型」疑为滑梯模型），阅读原文时留意文档中的勘误表。</li>" +
      "<li>图谱页为按关联度取前 N 的<b>核心子图</b>；全量图谱、向量检索与问答在 GraphMind（需已启动 " + DATA.graphmind_url + "）。</li>" +
      "<li>本页只展示博主的方法论提炼成果；不含我方应用方案（如金字塔结构层 v1.1 计划）。</li>" +
      "</ul></div>";
  }

  /* ---------------- 路由 ---------------- */
  function route() {
    var h = location.hash.replace(/^#\//, "");
    var seg = h.split("/");
    var r = { v: "overview" };
    if (seg[0] === "b" && seg[1]) { r.v = seg[2] ? "item" : "b"; r.b = seg[1]; r.i = seg[2]; }
    else if (seg[0] === "graph") r.v = "graph";
    else if (seg[0] === "about") r.v = "about";
    else if (seg[0] === "search") { r.v = "search"; r.q = decodeURIComponent(seg.slice(1).join("/") || ""); }
    markNav(r);
    if (r.v !== "graph") stopGraphLoop();
    if (r.v === "overview") vOverview();
    else if (r.v === "b" || r.v === "item") vBlogger(r.b, r.i);
    else if (r.v === "graph") vGraph();
    else if (r.v === "about") vAbout();
    else if (r.v === "search") { if (qin.value !== r.q) qin.value = r.q; vSearch(r.q); }
  }

  qin.addEventListener("input", function () {
    var q = qin.value.trim();
    if (!q) { if (location.hash.indexOf("#/search") === 0) location.hash = "#/overview"; return; }
    var target = "#/search/" + encodeURIComponent(q);
    if (location.hash === target) vSearch(q); else location.hash = target;
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && document.activeElement !== qin && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
      e.preventDefault(); qin.focus();
    }
  });
  window.addEventListener("hashchange", route);

  buildNav();
  if (!location.hash) location.hash = "#/overview";
  route();

  /* 调试钩子（不影响正常使用） */
  window.__WB_DEBUG__ = { G: G, focusNode: focusNode, DATA: DATA };
})();
