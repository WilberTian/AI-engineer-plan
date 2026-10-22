/* AI Engineer 转型实操手册 · 交互层 */
(function () {
  'use strict';

  /* ---------- theme ---------- */
  var root = document.documentElement;
  var saved = null;
  try { saved = localStorage.getItem('aip-theme'); } catch (e) {}
  if (saved) root.setAttribute('data-theme', saved);

  function currentTheme() {
    return root.getAttribute('data-theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function syncBtn() {
    var b = document.getElementById('themeBtn');
    if (b) b.textContent = currentTheme() === 'dark' ? '\u2600' : '\u263E';
    if (b) b.title = currentTheme() === 'dark' ? '切换到浅色' : '切换到深色';
  }

  /* ---------- progress bar ---------- */
  var bar = document.getElementById('pbar');
  function onScroll() {
    if (!bar) return;
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var p = h > 0 ? (window.scrollY / h) * 100 : 0;
    bar.style.width = Math.min(100, Math.max(0, p)) + '%';
  }

  /* ---------- toc active highlight ---------- */
  function initToc() {
    var links = [].slice.call(document.querySelectorAll('.sidebar nav a[href^="#"]'));
    if (!links.length) return;
    var map = {};
    links.forEach(function (a) {
      var id = a.getAttribute('href').slice(1);
      var el = document.getElementById(id);
      if (el) map[id] = a;
    });
    var targets = Object.keys(map).map(function (id) {
      return document.getElementById(id);
    }).filter(Boolean);
    if (!targets.length) return;

    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        links.forEach(function (l) { l.classList.remove('on'); });
        var a = map[en.target.id];
        if (a) a.classList.add('on');
      });
    }, { rootMargin: '-72px 0px -70% 0px', threshold: 0 });
    targets.forEach(function (t) { obs.observe(t); });
  }

  /* ---------- copy buttons ---------- */
  function initCopy() {
    [].slice.call(document.querySelectorAll('pre')).forEach(function (pre) {
      if (pre.querySelector('.copybtn')) return;
      var btn = document.createElement('button');
      btn.className = 'copybtn';
      btn.type = 'button';
      btn.textContent = '复制';
      btn.addEventListener('click', function () {
        var code = pre.querySelector('code') || pre;
        var text = code.innerText;
        var done = function () {
          btn.textContent = '已复制';
          btn.classList.add('done');
          setTimeout(function () {
            btn.textContent = '复制';
            btn.classList.remove('done');
          }, 1400);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, fallback);
        } else { fallback(); }
        function fallback() {
          var ta = document.createElement('textarea');
          ta.value = text;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand('copy'); done(); } catch (e) { btn.textContent = '复制失败'; }
          document.body.removeChild(ta);
        }
      });
      pre.appendChild(btn);
    });
  }

  /* ---------- sidebar toggle (mobile) ---------- */
  function initMenu() {
    var b = document.getElementById('menuBtn');
    var s = document.getElementById('sidebar');
    if (!b || !s) return;
    b.addEventListener('click', function () { s.classList.toggle('open'); });
    s.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') s.classList.remove('open');
    });
  }

  /* ---------- expand / collapse all tasks ---------- */
  function initExpand() {
    var all = document.getElementById('expandAll');
    if (!all) return;
    var tasks = function () {
      return [].slice.call(document.querySelectorAll('details.task'));
    };
    all.addEventListener('click', function () {
      var anyClosed = tasks().some(function (d) { return !d.open; });
      tasks().forEach(function (d) { d.open = anyClosed; });
      all.textContent = anyClosed ? '全部折叠' : '全部展开';
      all.setAttribute('aria-expanded', anyClosed ? 'true' : 'false');
    });
  }

  /* ==========================================================
     学习笔记：纯前端实现，数据只存在本机 localStorage，无任何后端
     - 区块笔记：h2[id] / h3[id] / details.task[id] 旁边一个「笔记」按钮
     - 页面笔记：面板顶部「本页随手记」
     - 导出：Markdown（阅读归档）/ JSON（备份迁移）
     ========================================================== */
  var NKEY = 'aip-plan:notes:v1';
  var PAGE_ORDER = ['index', 'env', 'stage-p0', 'stage-p1', 'stage-p2', 'stage-p3', 'stage-p4', 'stage-p5', 'stage-p6', 'resources'];
  var PAGE_META = {
    index: ['总览', 'index.html'],
    env: ['Day 0 · 环境与工具链', 'env.html'],
    'stage-p0': ['P0 · 定位与基线', 'stage-p0.html'],
    'stage-p1': ['P1 · 地基：Python + agent loop', 'stage-p1.html'],
    'stage-p2': ['P2 · 检索与上下文', 'stage-p2.html'],
    'stage-p3': ['P3 · Agent 运行时（harness）', 'stage-p3.html'],
    'stage-p4': ['P4 · 可靠性、安全与成本', 'stage-p4.html'],
    'stage-p5': ['P5 · 产品化与差异化', 'stage-p5.html'],
    'stage-p6': ['P6 · 求职冲刺', 'stage-p6.html'],
    resources: ['资源库与 Harness 地图', 'resources.html']
  };

  var NSTORE = (function () {
    var d = { v: 1, pages: {} };
    try {
      var raw = localStorage.getItem(NKEY);
      if (raw) {
        var o = JSON.parse(raw);
        if (o && typeof o === 'object' && o.pages && typeof o.pages === 'object') d = o;
      }
    } catch (e) {}
    return d;
  })();
  var nWarned = false;

  function nSave() {
    try { localStorage.setItem(NKEY, JSON.stringify(NSTORE)); return true; }
    catch (e) { return false; }
  }
  function nPage() {
    var seg = (location.pathname || '').split('/').pop() || '';
    seg = seg.replace(/\.html?$/i, '');
    return seg || 'index';
  }
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function pad2(n) { return n < 10 ? '0' + n : '' + n; }
  function fmtT(ts) {
    var d = new Date(ts || Date.now());
    return pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }
  function fmtFull(ts) {
    var d = new Date(ts || Date.now());
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }
  function stampDate() {
    var d = new Date();
    return '' + d.getFullYear() + pad2(d.getMonth() + 1) + pad2(d.getDate());
  }
  function pageMeta(p) { return PAGE_META[p] || [p, p + '.html']; }
  function allPages() {
    var extra = Object.keys(NSTORE.pages).filter(function (p) { return PAGE_ORDER.indexOf(p) < 0; });
    return PAGE_ORDER.concat(extra);
  }
  function noteOf(page, key) {
    var P = NSTORE.pages[page];
    return P && P[key] ? P[key] : null;
  }
  function noteSet(page, key, title, text) {
    var P = NSTORE.pages[page];
    if (!text || !String(text).trim()) {
      if (P) {
        delete P[key];
        if (!Object.keys(P).length) delete NSTORE.pages[page];
      }
    } else {
      if (!P) P = NSTORE.pages[page] = {};
      var old = P[key];
      P[key] = {
        title: title || (old && old.title) || key,
        text: String(text),
        t: (old && old.t) || Date.now(),
        u: Date.now()
      };
    }
    if (!nSave() && !nWarned) {
      nWarned = true;
      toast('浏览器存储不可用，笔记无法保存（隐私模式？）');
    }
  }
  function noteCount(page) {
    var P = NSTORE.pages[page];
    return P ? Object.keys(P).length : 0;
  }
  function totalCount() {
    var n = 0;
    Object.keys(NSTORE.pages).forEach(function (p) { n += Object.keys(NSTORE.pages[p]).length; });
    return n;
  }

  /* ---------- 小工具 ---------- */
  var toastTimer = null;
  function toast(msg) {
    var t = document.getElementById('nToast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'nToast';
      t.className = 'n-toast';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove('on'); }, 2400);
  }
  function download(name, text, mime) {
    var blob = new Blob([text], { type: (mime || 'text/plain') + ';charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      if (a.parentNode) a.parentNode.removeChild(a);
      URL.revokeObjectURL(url);
    }, 1200);
  }

  /* ---------- 区块标题 ---------- */
  function blockTitle(el) {
    if (el.tagName === 'DETAILS') {
      var tid = el.querySelector('.tid');
      var tn = el.querySelector('.tname');
      var s = (tid ? tid.textContent : '') + ' ' + (tn ? tn.textContent : '');
      s = s.replace(/\s+/g, ' ').trim();
      return s.length > 80 ? s.slice(0, 80) + '…' : s;
    }
    var c = el.cloneNode(true);
    [].slice.call(c.querySelectorAll('.num,.notebtn,.tmin,.ne-head')).forEach(function (n) {
      if (n.parentNode) n.parentNode.removeChild(n);
    });
    var t = (c.textContent || '').replace(/\s+/g, ' ').trim();
    return t.length > 80 ? t.slice(0, 80) + '…' : t;
  }

  /* ---------- 按钮 / 编辑器 ---------- */
  function syncMarks() {
    var p = nPage();
    [].slice.call(document.querySelectorAll('.notebtn')).forEach(function (b) {
      var k = b.getAttribute('data-nid');
      b.classList.toggle('has', !!noteOf(p, k));
      b.title = noteOf(p, k) ? '已有笔记，点击编辑' : '为这一节写笔记';
    });
    var badge = document.getElementById('nfBadge');
    var n = totalCount();
    if (badge) {
      badge.textContent = n > 99 ? '99+' : String(n);
      badge.classList.toggle('on', n > 0);
    }
  }

  function ensureEditor(el, key, title) {
    var box = document.querySelector('.note-editor[data-nid="' + key + '"]');
    if (box) return box;
    box = document.createElement('div');
    box.className = 'note-editor';
    box.setAttribute('data-nid', key);
    box.innerHTML =
      '<div class="ne-head">' +
        '<span class="ne-tag">笔记</span>' +
        '<span class="ne-meta"></span>' +
        '<span class="ne-sp"></span>' +
        '<button type="button" class="ne-btn ne-del">删除</button>' +
        '<button type="button" class="ne-btn ne-close">收起</button>' +
      '</div>' +
      '<textarea rows="3" spellcheck="false" placeholder="这节看懂了什么？哪一行没跑通？下一步做什么？（⌘/Ctrl + Enter 收起）"></textarea>' +
      '<div class="ne-hint">只保存在本机浏览器，不会上传。</div>';

    var ta = box.querySelector('textarea');
    var meta = box.querySelector('.ne-meta');
    var tmr = null;
    var save = function (show) {
      noteSet(nPage(), key, title, ta.value);
      if (show) {
        meta.textContent = ta.value.trim() ? '已保存 ' + fmtT(Date.now()) : '空笔记不入库';
        meta.classList.toggle('ok', !!ta.value.trim());
      }
      syncMarks();
      renderPanelSafe();
    };
    ta.addEventListener('input', function () {
      meta.textContent = '输入中…';
      meta.classList.remove('ok');
      clearTimeout(tmr);
      tmr = setTimeout(function () { save(true); }, 700);
    });
    ta.addEventListener('blur', function () {
      clearTimeout(tmr);
      save(true);
      renderPanelSafe();
    });
    ta.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        clearTimeout(tmr);
        save(true);
        box.classList.remove('open');
        ta.blur();
      }
    });
    box.querySelector('.ne-close').addEventListener('click', function () {
      clearTimeout(tmr);
      save(true);
      box.classList.remove('open');
    });
    box.querySelector('.ne-del').addEventListener('click', function () {
      if (!ta.value.trim()) { box.classList.remove('open'); return; }
      if (!confirm('删除这条笔记？删除后不可恢复。')) return;
      ta.value = '';
      clearTimeout(tmr);
      save(true);
      box.classList.remove('open');
      toast('已删除');
    });
    el.insertAdjacentElement('afterend', box);
    return box;
  }

  function openEditor(el, key, title) {
    var box = ensureEditor(el, key, title);
    var ta = box.querySelector('textarea');
    var meta = box.querySelector('.ne-meta');
    if (box.classList.contains('open')) {
      box.classList.remove('open');
      return;
    }
    var rec = noteOf(nPage(), key);
    if (!ta.value && rec) ta.value = rec.text;
    meta.textContent = rec ? '上次保存 ' + fmtT(rec.u || rec.t) : '还没有笔记';
    meta.classList.toggle('ok', !!rec);
    box.classList.add('open');
    ta.focus();
    setTimeout(function () {
      box.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }, 80);
  }

  /* ---------- 面板 ---------- */
  function renderPanelSafe() {
    var dr = document.getElementById('noteDrawer');
    if (!dr || !dr.classList.contains('open')) return;
    var body = document.getElementById('ndBody');
    var ae = document.activeElement;
    if (body && ae && body.contains(ae) && ae.tagName === 'TEXTAREA') return;
    renderPanel();
  }

  function gotoBlock(page, key) {
    var meta = pageMeta(page);
    var url = (key === '_page') ? meta[1] : meta[1] + '#' + key;
    if (page !== nPage()) {
      location.href = url;
      return;
    }
    if (key === '_page') {
      closeDrawer();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    var el = document.getElementById(key);
    if (el) {
      var d = el.closest('details.task');
      if (d) d.open = true;
      el.scrollIntoView({ block: 'start', behavior: 'smooth' });
      el.classList.add('n-flash');
      setTimeout(function () { el.classList.remove('n-flash'); }, 1400);
    }
    closeDrawer();
  }

  function renderPanel() {
    var body = document.getElementById('ndBody');
    if (!body) return;
    var allChk = document.getElementById('ndAll');
    var all = !!(allChk && allChk.checked);
    var inp = document.getElementById('ndSearch');
    var q = inp ? (inp.value || '').trim().toLowerCase() : '';
    var cur = nPage();
    var pages = all ? allPages() : [cur];
    var out = [];
    var hits = 0;

    if (!all) {
      var pr = noteOf(cur, '_page');
      out.push(
        '<div class="nd-quick">' +
          '<div class="nd-qh">本页随手记<span>' + (pr ? '已保存 ' + fmtT(pr.u || pr.t) : '整章感想 / 待解决问题') + '</span></div>' +
          '<textarea id="ndQuick" rows="2" spellcheck="false" placeholder="这章读完的整体感受、还没想明白的点…">' + esc(pr ? pr.text : '') + '</textarea>' +
        '</div>'
      );
    }

    pages.forEach(function (p) {
      var P = NSTORE.pages[p] || {};
      var keys = Object.keys(P).filter(function (k) {
        if (k === '_page' && !all) return false;
        if (!q) return true;
        var r = P[k];
        return (r.title || '').toLowerCase().indexOf(q) >= 0 || (r.text || '').toLowerCase().indexOf(q) >= 0;
      });
      keys.sort(function (a, b) { return (P[b].u || P[b].t || 0) - (P[a].u || P[a].t || 0); });

      if (all) {
        var pm = pageMeta(p);
        if (!keys.length) return;
        out.push('<div class="nd-sec">' + esc(pm[0]) + '<em>' + keys.length + '</em></div>');
      }

      if (!keys.length) {
        if (!all && !q) {
          out.push('<div class="nd-empty">这一页还没有区块笔记。<br>把鼠标移到正文的标题或任务卡上，点「笔记」就能记。</div>');
        }
        return;
      }

      keys.forEach(function (k) {
        var r = P[k];
        var pm2 = pageMeta(p);
        var href = (k === '_page') ? pm2[1] : pm2[1] + '#' + k;
        hits++;
        out.push(
          '<a class="nd-item" href="' + href + '" data-page="' + esc(p) + '" data-key="' + esc(k) + '">' +
            '<b>' + esc(r.title || k) + '</b>' +
            '<span class="nd-snip">' + esc((r.text || '').trim()) + '</span>' +
            '<em class="nd-time">' + fmtT(r.u || r.t) + (all ? ' · ' + esc(pm2[1]) : '') + '</em>' +
          '</a>'
        );
      });
    });

    if (!hits && q) out.push('<div class="nd-empty">没有匹配「' + esc(q) + '」的笔记。</div>');
    if (!hits && !q && all) out.push('<div class="nd-empty">全站还没有笔记。</div>');

    body.innerHTML = out.join('');

    var cnt = document.getElementById('ndCnt');
    if (cnt) {
      var np = allPages().filter(function (p) { return noteCount(p) > 0; }).length;
      cnt.textContent = totalCount() + ' 条 · ' + np + ' 页';
    }

    [].slice.call(body.querySelectorAll('.nd-item')).forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        gotoBlock(a.getAttribute('data-page'), a.getAttribute('data-key'));
      });
    });

    var qa = document.getElementById('ndQuick');
    if (qa) {
      var tm = null;
      var saveQ = function () { noteSet(cur, '_page', '本页随手记', qa.value); syncMarks(); };
      qa.addEventListener('input', function () {
        clearTimeout(tm);
        tm = setTimeout(saveQ, 700);
      });
      qa.addEventListener('blur', function () { clearTimeout(tm); saveQ(); });
    }
  }

  function openDrawer() {
    var dr = document.getElementById('noteDrawer');
    if (!dr) return;
    dr.classList.add('open');
    renderPanel();
    var s = document.getElementById('ndSearch');
    if (s && window.innerWidth > 640) s.focus();
  }
  function closeDrawer() {
    var dr = document.getElementById('noteDrawer');
    if (dr) dr.classList.remove('open');
  }
  function toggleDrawer() {
    var dr = document.getElementById('noteDrawer');
    if (!dr) return;
    if (dr.classList.contains('open')) closeDrawer(); else openDrawer();
  }

  function buildPanel() {
    if (document.getElementById('noteFab')) return;

    var fab = document.createElement('button');
    fab.type = 'button';
    fab.id = 'noteFab';
    fab.className = 'note-fab';
    fab.title = '我的学习笔记（只存在本机）';
    fab.setAttribute('aria-label', '打开学习笔记');
    fab.innerHTML = '<span class="nf-ico">✎</span><span class="nf-badge" id="nfBadge"></span>';
    fab.addEventListener('click', toggleDrawer);
    document.body.appendChild(fab);

    var dr = document.createElement('aside');
    dr.className = 'note-drawer';
    dr.id = 'noteDrawer';
    dr.setAttribute('aria-label', '学习笔记');
    dr.innerHTML =
      '<div class="nd-head">' +
        '<b>学习笔记</b>' +
        '<span class="nd-cnt" id="ndCnt"></span>' +
        '<button type="button" class="nd-x" id="ndX" title="关闭">×</button>' +
      '</div>' +
      '<div class="nd-tools">' +
        '<input type="search" id="ndSearch" class="nd-search" placeholder="搜索笔记…">' +
        '<label class="nd-scope"><input type="checkbox" id="ndAll"> 全站</label>' +
      '</div>' +
      '<div class="nd-body" id="ndBody"></div>' +
      '<div class="nd-foot">' +
        '<button type="button" class="txtbtn" id="ndMd">导出 Markdown</button>' +
        '<button type="button" class="txtbtn" id="ndJson">备份 JSON</button>' +
        '<button type="button" class="txtbtn" id="ndImp">导入</button>' +
        '<button type="button" class="txtbtn nd-danger" id="ndClear">清空</button>' +
        '<input type="file" id="ndFile" accept="application/json,.json" hidden>' +
      '</div>' +
      '<div class="nd-tip">笔记保存在本机浏览器（localStorage），不经过任何服务器。换设备或清理浏览器数据前，请先「备份 JSON」。</div>';
    document.body.appendChild(dr);

    document.getElementById('ndX').addEventListener('click', closeDrawer);
    document.getElementById('ndAll').addEventListener('change', renderPanel);

    var st = null;
    document.getElementById('ndSearch').addEventListener('input', function () {
      clearTimeout(st);
      st = setTimeout(renderPanel, 140);
    });

    document.getElementById('ndMd').addEventListener('click', function () {
      var all = document.getElementById('ndAll').checked;
      var pages = all ? allPages() : [nPage()];
      var md = buildMarkdown(pages, all);
      if (!md) { toast('还没有笔记可以导出'); return; }
      download('AI学习笔记_' + stampDate() + (all ? '_全站' : '') + '.md', md, 'text/markdown');
      toast('已导出 Markdown');
    });

    document.getElementById('ndJson').addEventListener('click', function () {
      if (!totalCount()) { toast('还没有笔记可以备份'); return; }
      download('AI学习笔记_备份_' + stampDate() + '.json', JSON.stringify(NSTORE, null, 2), 'application/json');
      toast('已导出 JSON 备份');
    });

    document.getElementById('ndImp').addEventListener('click', function () {
      document.getElementById('ndFile').click();
    });

    document.getElementById('ndFile').addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0];
      if (!f) return;
      var fr = new FileReader();
      fr.onload = function () {
        var o = null;
        try { o = JSON.parse(String(fr.result)); } catch (err) { toast('不是合法的 JSON 文件'); return; }
        if (!o || !o.pages || typeof o.pages !== 'object') { toast('文件格式不对：缺少 pages'); return; }
        var add = 0, upd = 0;
        Object.keys(o.pages).forEach(function (p) {
          var src = o.pages[p];
          if (!src || typeof src !== 'object') return;
          var dst = NSTORE.pages[p] || (NSTORE.pages[p] = {});
          Object.keys(src).forEach(function (k) {
            var r = src[k];
            if (!r || typeof r !== 'object' || typeof r.text !== 'string' || !r.text.trim()) return;
            var ru = r.u || r.t || 0;
            var old = dst[k];
            if (!old) {
              dst[k] = { title: r.title || k, text: r.text, t: r.t || ru, u: ru };
              add++;
            } else if (ru > (old.u || old.t || 0)) {
              dst[k] = { title: r.title || old.title || k, text: r.text, t: old.t || ru, u: ru };
              upd++;
            }
          });
        });
        if (!add && !upd) { toast('没有新内容可导入（本地已是最新）'); e.target.value = ''; return; }
        nSave();
        syncMarks();
        renderPanel();
        toast('导入完成：新增 ' + add + ' 条，更新 ' + upd + ' 条');
        e.target.value = '';
      };
      fr.onerror = function () { toast('文件读取失败'); };
      fr.readAsText(f, 'utf-8');
    });

    document.getElementById('ndClear').addEventListener('click', function () {
      var n = totalCount();
      if (!n) { toast('现在没有任何笔记'); return; }
      if (!confirm('清空全部 ' + n + ' 条笔记？所有页面的笔记都会被删除，且不可恢复。\n\n建议先点「备份 JSON」。')) return;
      if (!confirm('再确认一次：确定清空？')) return;
      NSTORE = { v: 1, pages: {} };
      nSave();
      [].slice.call(document.querySelectorAll('.note-editor textarea')).forEach(function (t) { t.value = ''; });
      [].slice.call(document.querySelectorAll('.note-editor')).forEach(function (b) { b.classList.remove('open'); });
      syncMarks();
      renderPanel();
      toast('已清空全部笔记');
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeDrawer();
    });
  }

  /* ---------- Markdown 导出 ---------- */
  function buildMarkdown(pages, isAll) {
    var lines = [];
    var items = 0;
    var pageHit = 0;
    pages.forEach(function (p) {
      var P = NSTORE.pages[p];
      if (!P) return;
      var keys = Object.keys(P).filter(function (k) { return (P[k].text || '').trim(); });
      if (!keys.length) return;
      pageHit++;
      var meta = pageMeta(p);
      lines.push('---');
      lines.push('');
      lines.push('## ' + meta[0]);
      lines.push('');
      lines.push('`' + meta[1] + '`');
      lines.push('');
      keys.forEach(function (k) {
        var r = P[k];
        lines.push('### ' + (r.title || k));
        lines.push('');
        lines.push('> ' + (r.text || '').trim().split(/\r?\n/).join('  \n> '));
        lines.push('');
        var link = k === '_page' ? meta[1] : meta[1] + '#' + k;
        lines.push('_更新于 ' + fmtFull(r.u || r.t) + ' · [回到原文](' + link + ')_');
        lines.push('');
        items++;
      });
    });

    if (!items) return '';

    var head = [
      '# AI Engineer 转型 · 学习笔记',
      '',
      '> 导出时间 ' + fmtFull(Date.now()) + ' · 范围：' + (isAll ? '全站' : '当前页'),
      '> 共 ' + items + ' 条笔记，覆盖 ' + pageHit + ' 个页面。数据来自本机浏览器 localStorage，不含任何服务端内容。',
      ''
    ];
    return head.concat(lines).join('\n');
  }

  /* ---------- 初始化 ---------- */
  function initNotes() {
    buildPanel();
    syncMarks();

    var main = document.querySelector('main');
    if (!main) return;
    var blocks = [].slice.call(main.querySelectorAll('h2[id],h3[id],details.task[id]'));

    blocks.forEach(function (el) {
      var key = el.id;
      if (!key) return;
      var title = blockTitle(el);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'notebtn';
      btn.setAttribute('data-nid', key);
      btn.setAttribute('aria-label', '为「' + title + '」写笔记');
      btn.innerHTML = '<i></i><span>笔记</span>';
      var host = (el.tagName === 'DETAILS') ? el.querySelector('summary') : el;
      if (!host) return;
      host.appendChild(btn);
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openEditor(el, key, title);
      });
    });

    syncMarks();
  }

  /* ---------- bootstrap ---------- */
  function ready() {
    syncBtn();
    var tb = document.getElementById('themeBtn');
    if (tb) tb.addEventListener('click', function () {
      var next = currentTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('aip-theme', next); } catch (e) {}
      syncBtn();
    });

    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);

    initToc();
    initCopy();
    initMenu();
    initExpand();
    initNotes();

    /* 深链：若 URL 带 #id，展开其所属 task */
    if (location.hash) {
      var el = document.getElementById(location.hash.slice(1));
      if (el) {
        var d = el.closest('details.task');
        if (d) d.open = true;
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ready);
  } else { ready(); }
})();
