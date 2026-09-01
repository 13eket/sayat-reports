/* Саят — «Покрутите цифры сами».
   Интерактивный разбор визитов. Данные подставляются в DATA сборщиком (prep.py). */
(function () {
  "use strict";
  var D = window.SAYAT_DATA;
  if (!D) return;
  var ROWS = D.rows, META = D.meta, ITEMS = META.items;

  /* ---------- палитра (проверена на цветовую слепоту) ---------- */
  var CAT = [
    { k: "cabin", t: "кабина", c: "#0f7a34" },
    { k: "serv",  t: "пилинг и услуги", c: "#8a63d2" },
    { k: "food",  t: "еда", c: "#b8531c" },
    { k: "drink", t: "напитки", c: "#2563c9" },
    { k: "cons",  t: "простыни, шапки, мыло", c: "#a6761d" }
  ];
  var RAMP = ["#eef3ee", "#d3e7d9", "#a8d0b6", "#6fb287", "#2f8f52", "#0f6b2d"];

  /* ---------- состояние фильтров ---------- */
  var S = { mo: "all", wd: "all", tm: "all", ppl: "all", cab: "all",
            food: false, alc: false, serv: false, hmap: "n" };

  var MONTHS = { 2: "февраль", 3: "март", 4: "апрель", 5: "май",
                 6: "июнь", 7: "июль", 8: "август" };
  var MOSHORT = { 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн", 7: "июл", 8: "авг" };
  var WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];

  /* ---------- вспомогательное ---------- */
  function money(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " ₸";
  }
  function num(n) { return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function sum(a, f) { var s = 0; for (var i = 0; i < a.length; i++) s += f(a[i]); return s; }
  function pct(a, b) { return b ? Math.round(a / b * 100) : 0; }

  /* «5 визитов», «2 визита», «1 визит» */
  function plural(n, one, few, many) {
    var a = Math.abs(n) % 100, b = a % 10;
    if (a > 10 && a < 20) return many;
    if (b > 1 && b < 5) return few;
    if (b === 1) return one;
    return many;
  }
  function visitsN(n) { return num(n) + " " + plural(n, "визит", "визита", "визитов"); }

  /* «стол» — настоящее блюдо, а не хлеб или соус к чаю */
  function hasFood(r) { return r.dish === 1; }
  function hasAlc(r) { return (r.c.alc || 0) > 0; }
  function hasServ(r) { return (r.c.serv || 0) > 0; }

  /* напитки в графике = безалкогольные + алкоголь (для гостя это просто «напитки») */
  function catSum(r, k) {
    if (k === "drink") return (r.c.drink || 0) + (r.c.alc || 0) + (r.c.other || 0);
    return r.c[k] || 0;
  }

  function timeBlock(h) {
    if (h == null) return null;
    if (h >= 10 && h <= 16) return "day";
    if (h >= 17 && h <= 21) return "eve";
    return "night";
  }
  function pplBucket(p) {
    if (p == null) return null;
    if (p <= 1) return "1";
    if (p <= 2) return "2";
    if (p <= 4) return "34";
    return "5";
  }

  function filtered() {
    return ROWS.filter(function (r) {
      if (S.mo !== "all" && r.mo !== +S.mo) return false;
      if (S.wd === "week" && r.wd > 4) return false;
      if (S.wd === "end" && r.wd < 5) return false;
      if (S.tm !== "all" && timeBlock(r.h) !== S.tm) return false;
      if (S.ppl !== "all" && pplBucket(r.ppl) !== S.ppl) return false;
      if (S.cab !== "all" && r.cab !== S.cab) return false;
      if (S.food && !hasFood(r)) return false;
      if (S.alc && !hasAlc(r)) return false;
      if (S.serv && !hasServ(r)) return false;
      return true;
    });
  }

  /* ---------- подсказка ---------- */
  var tip = el("div", "ex-tip");
  tip.style.display = "none";
  document.body.appendChild(tip);
  function bindTip(node, html) {
    node.setAttribute("tabindex", "0");
    function show(e) {
      tip.innerHTML = html;
      tip.style.display = "block";
      var b = node.getBoundingClientRect();
      var w = tip.offsetWidth, x = b.left + b.width / 2 - w / 2;
      x = Math.max(8, Math.min(x, window.innerWidth - w - 8));
      var y = b.top + window.scrollY - tip.offsetHeight - 9;
      if (y < window.scrollY + 4) y = b.bottom + window.scrollY + 9;
      tip.style.left = x + "px";
      tip.style.top = y + "px";
    }
    function hide() { tip.style.display = "none"; }
    node.addEventListener("mouseenter", show);
    node.addEventListener("focus", show);
    node.addEventListener("mouseleave", hide);
    node.addEventListener("blur", hide);
    node.addEventListener("click", function (e) { show(e); e.stopPropagation(); });
  }
  document.addEventListener("click", function () { tip.style.display = "none"; });

  /* ---------- панель фильтров ---------- */
  function chipRow(label, key, opts) {
    var row = el("div", "ex-frow");
    row.appendChild(el("span", "ex-flab", label));
    var box = el("div", "ex-chips");
    opts.forEach(function (o) {
      var b = el("button", "ex-chip" + (S[key] === o.v ? " on" : ""), o.t);
      b.type = "button";
      b.onclick = function () { S[key] = o.v; render(); };
      box.appendChild(b);
    });
    row.appendChild(box);
    return row;
  }

  function toggleRow() {
    var row = el("div", "ex-frow");
    row.appendChild(el("span", "ex-flab", "Что брал"));
    var box = el("div", "ex-chips");
    [["food", "стол"], ["alc", "пиво"], ["serv", "пилинг"]].forEach(function (p) {
      var b = el("button", "ex-chip" + (S[p[0]] ? " on" : ""), p[1]);
      b.type = "button";
      b.onclick = function () { S[p[0]] = !S[p[0]]; render(); };
      box.appendChild(b);
    });
    var r = el("button", "ex-chip ex-reset", "сбросить всё");
    r.type = "button";
    r.onclick = function () {
      S = { mo: "all", wd: "all", tm: "all", ppl: "all", cab: "all",
            food: false, alc: false, serv: false, hmap: S.hmap };
      render();
    };
    box.appendChild(r);
    row.appendChild(box);
    return row;
  }

  function filters() {
    var w = el("div", "ex-filters");
    var mo = [{ v: "all", t: "все" }];
    [2, 3, 4, 5, 6, 7, 8].forEach(function (m) { mo.push({ v: String(m), t: MOSHORT[m] }); });
    w.appendChild(chipRow("Месяц", "mo", mo));
    w.appendChild(chipRow("Дни", "wd", [
      { v: "all", t: "все" }, { v: "week", t: "будни" }, { v: "end", t: "выходные" }]));
    w.appendChild(chipRow("Время прихода", "tm", [
      { v: "all", t: "любое" }, { v: "day", t: "днём 10–16" },
      { v: "eve", t: "вечером 17–21" }, { v: "night", t: "ночью 22–04" }]));
    w.appendChild(chipRow("Сколько человек", "ppl", [
      { v: "all", t: "любая" }, { v: "1", t: "один" }, { v: "2", t: "двое" },
      { v: "34", t: "3–4" }, { v: "5", t: "5 и больше" }]));
    w.appendChild(chipRow("Кабина", "cab", [
      { v: "all", t: "любая" }, { v: "1", t: "№1 VIP" }, { v: "2", t: "№2" },
      { v: "3", t: "№3" }, { v: "4", t: "№4" }, { v: "5", t: "№5" }, { v: "6", t: "№6" }]));
    w.appendChild(toggleRow());
    return w;
  }

  /* ---------- плитки ---------- */
  function tiles(F) {
    var box = el("div", "ex-tiles");
    var rev = sum(F, function (r) { return r.sum; });
    var withPpl = F.filter(function (r) { return r.ppl != null; });
    var withDur = F.filter(function (r) { return r.dur; });
    var t = [
      ["Визитов", num(F.length), F.length === ROWS.length ? "всё, что разобрали" : "из " + num(ROWS.length)],
      ["Выручка", money(rev), "по этим визитам"],
      ["Средний чек", F.length ? money(rev / F.length) : "—", "за один визит"],
      ["Сидят в среднем", withDur.length ? (sum(withDur, function (r) { return r.dur; }) / withDur.length).toFixed(1).replace(".", ",") + " ч" : "—",
        "по " + num(withDur.length) + " визитам"],
      ["В компании", withPpl.length ? (sum(withPpl, function (r) { return r.ppl; }) / withPpl.length).toFixed(1).replace(".", ",") + " чел." : "—",
        "по " + num(withPpl.length) + " визитам"],
      ["Заказали стол", F.length ? pct(F.filter(hasFood).length, F.length) + "%" : "—", "горячее, рыба, салат"]
    ];
    t.forEach(function (x) {
      var c = el("div", "ex-tile");
      c.appendChild(el("div", "ex-tk", x[0]));
      c.appendChild(el("div", "ex-tv", x[1]));
      c.appendChild(el("div", "ex-ts", x[2]));
      box.appendChild(c);
    });
    return box;
  }

  /* ---------- тепловая карта: день недели × час ---------- */
  function heatmap(F) {
    var wrap = el("div", "ex-block");
    var head = el("div", "ex-bh");
    head.appendChild(el("h3", null, "Когда к нам приходят"));
    var sw = el("div", "ex-switch");
    [["n", "сколько визитов"], ["avg", "средний чек"]].forEach(function (p) {
      var b = el("button", "ex-chip sm" + (S.hmap === p[0] ? " on" : ""), p[1]);
      b.type = "button";
      b.onclick = function () { S.hmap = p[0]; render(); };
      sw.appendChild(b);
    });
    head.appendChild(sw);
    wrap.appendChild(head);

    var hrs = [];
    for (var h = 9; h <= 23; h++) hrs.push(h);
    for (h = 0; h <= 4; h++) hrs.push(h);

    var cell = {};
    var out = 0;
    F.forEach(function (r) {
      if (r.h == null) { out++; return; }
      var k = r.wd + "_" + r.h;
      if (!cell[k]) cell[k] = { n: 0, s: 0 };
      cell[k].n++; cell[k].s += r.sum;
    });
    var maxv = 0;
    Object.keys(cell).forEach(function (k) {
      var v = S.hmap === "n" ? cell[k].n : cell[k].s / cell[k].n;
      if (v > maxv) maxv = v;
    });

    var scroll = el("div", "ex-scroll");
    var grid = el("div", "ex-hm");
    grid.style.gridTemplateColumns = "28px repeat(" + hrs.length + ", minmax(26px,1fr))";
    grid.appendChild(el("div", "ex-hc"));
    hrs.forEach(function (h) {
      grid.appendChild(el("div", "ex-hc", h === 0 ? "0" : String(h)));
    });
    WD.forEach(function (w, wi) {
      grid.appendChild(el("div", "ex-hr", w));
      hrs.forEach(function (h) {
        var c = cell[wi + "_" + h];
        var d = el("div", "ex-cell");
        if (c) {
          var v = S.hmap === "n" ? c.n : c.s / c.n;
          var step = Math.min(RAMP.length - 1, Math.max(1, Math.ceil(v / maxv * (RAMP.length - 1))));
          d.style.background = RAMP[step];
          if (step >= 4) d.style.color = "#fff";
          d.textContent = S.hmap === "n" ? c.n : Math.round(c.s / c.n / 1000) + "т";
          bindTip(d, "<b>" + w + ", " + h + ":00</b><br>визитов: " + c.n +
            "<br>средний чек: " + money(c.s / c.n) + "<br>всего: " + money(c.s));
        }
        grid.appendChild(d);
      });
    });
    scroll.appendChild(grid);
    wrap.appendChild(scroll);
    var legend = el("div", "ex-note");
    legend.innerHTML = "Чем темнее клетка — тем " +
      (S.hmap === "n" ? "больше визитов" : "больше средний чек") +
      ". В клетках " + (S.hmap === "n" ? "число визитов" : "средний чек, тысяч ₸") +
      ". Время начала записано у " + num(F.length - out) + " визитов из " + num(F.length) + ". " +
      "Час прихода взят прямо из тетради и точен; день недели восстановлен по дате листа — " +
      "если админ фотографировал несколько листов пачкой, день мог сдвинуться на сутки." +
      (S.hmap === "avg" ? " В редких клетках чек скачет — смотрите на число визитов в подсказке." : "");
    wrap.appendChild(legend);
    return wrap;
  }

  /* ---------- простые горизонтальные столбики ---------- */
  function barChart(title, rows, opt) {
    opt = opt || {};
    var wrap = el("div", "ex-block");
    if (title) wrap.appendChild(el("h3", null, title));
    var max = 0;
    rows.forEach(function (r) { if (r.v > max) max = r.v; });
    var list = el("div", "ex-bars");
    rows.forEach(function (r) {
      var line = el("div", "ex-bar");
      line.appendChild(el("div", "ex-blab", r.t));
      var track = el("div", "ex-btrack");
      var fill = el("div", "ex-bfill");
      fill.style.width = (max ? Math.max(r.v / max * 100, r.v > 0 ? 1.5 : 0) : 0) + "%";
      fill.style.background = r.c || opt.color || "#0f7a34";
      track.appendChild(fill);
      line.appendChild(track);
      line.appendChild(el("div", "ex-bval", r.l));
      if (r.tip) bindTip(line, r.tip);
      list.appendChild(line);
    });
    wrap.appendChild(list);
    if (opt.note) wrap.appendChild(el("div", "ex-note", opt.note));
    return wrap;
  }

  /* средний чек по размеру компании */
  function byPeople(F) {
    var groups = [["1", "один"], ["2", "двое"], ["34", "3–4 человека"], ["5", "5 и больше"]];
    var rows = groups.map(function (g) {
      var sel = F.filter(function (r) { return pplBucket(r.ppl) === g[0]; });
      var rev = sum(sel, function (r) { return r.sum; });
      var avg = sel.length ? rev / sel.length : 0;
      return {
        t: g[1], v: avg, l: sel.length ? money(avg) : "нет данных",
        tip: "<b>" + g[1] + "</b><br>визитов: " + sel.length + "<br>средний чек: " +
             (sel.length ? money(avg) : "—") + "<br>стол брали: " + pct(sel.filter(hasFood).length, sel.length) + "%"
      };
    });
    var known = F.filter(function (r) { return r.ppl != null; }).length;
    return barChart("Средний чек: чем больше компания, тем больше счёт", rows, {
      note: "Число людей администраторы записывали не всегда — здесь " + num(known) +
            " визитов из " + num(F.length) + ". Наведите на строку, чтобы увидеть, сколько это визитов."
    });
  }

  /* доля визитов с едой / пивом / пилингом по времени прихода */
  function attach(F) {
    var blocks = [["day", "днём 10–16"], ["eve", "вечером 17–21"], ["night", "ночью 22–04"]];
    var wrap = el("div", "ex-block");
    wrap.appendChild(el("h3", null, "Что заказывают сверх кабины"));
    wrap.appendChild(legendBox([
      { t: "стол (горячее, рыба, салат)", c: "#b8531c" }, { t: "пиво", c: "#2563c9" }, { t: "пилинг", c: "#8a63d2" }]));
    var list = el("div", "ex-bars");
    blocks.forEach(function (b) {
      var sel = F.filter(function (r) { return timeBlock(r.h) === b[0]; });
      var head = el("div", "ex-gt", b[1] + " — " + visitsN(sel.length));
      list.appendChild(head);
      [["стол", hasFood, "#b8531c"], ["пиво", hasAlc, "#2563c9"], ["пилинг", hasServ, "#8a63d2"]]
        .forEach(function (p) {
          var n = sel.filter(p[1]).length;
          var line = el("div", "ex-bar");
          line.appendChild(el("div", "ex-blab", p[0]));
          var track = el("div", "ex-btrack");
          var fill = el("div", "ex-bfill");
          fill.style.width = pct(n, sel.length) + "%";
          fill.style.background = p[2];
          track.appendChild(fill);
          line.appendChild(track);
          line.appendChild(el("div", "ex-bval", sel.length ? pct(n, sel.length) + "%" : "—"));
          bindTip(line, "<b>" + b[1] + " · " + p[0] + "</b><br>" + n + " из " + visitsN(sel.length));
          list.appendChild(line);
        });
    });
    wrap.appendChild(list);
    wrap.appendChild(el("div", "ex-note",
      "Шкала — доля визитов, а не деньги. Это и есть место для роста: там, где доля низкая, гостю просто не предложили."));
    return wrap;
  }

  function legendBox(items) {
    var l = el("div", "ex-legend");
    items.forEach(function (i) {
      var s = el("span", "ex-li");
      var sq = el("i");
      sq.style.background = i.c;
      s.appendChild(sq);
      s.appendChild(document.createTextNode(i.t));
      l.appendChild(s);
    });
    return l;
  }

  /* из чего складывается выручка — по месяцам */
  function basket(F) {
    var wrap = el("div", "ex-block");
    wrap.appendChild(el("h3", null, "Из чего складываются деньги"));
    wrap.appendChild(legendBox(CAT.map(function (c) { return { t: c.t, c: c.c }; })));
    var months = [2, 3, 4, 5, 6, 7, 8].filter(function (m) {
      return F.some(function (r) { return r.mo === m; });
    });
    var scroll = el("div", "ex-scroll");
    var cols = el("div", "ex-cols");
    var totals = months.map(function (m) {
      var sel = F.filter(function (r) { return r.mo === m; });
      return { m: m, sel: sel, tot: sum(sel, function (r) { return r.sum; }) };
    });
    var max = Math.max.apply(null, totals.map(function (t) { return t.tot; }).concat([1]));
    totals.forEach(function (t) {
      var col = el("div", "ex-col");
      var stack = el("div", "ex-stack");
      var h = Math.max(t.tot / max * 100, 1);
      stack.style.height = h + "%";
      CAT.forEach(function (c) {
        var v = sum(t.sel, function (r) { return catSum(r, c.k); });
        if (!v) return;
        var seg = el("div", "ex-seg");
        seg.style.height = (v / t.tot * 100) + "%";
        seg.style.background = c.c;
        bindTip(seg, "<b>" + MONTHS[t.m] + " · " + c.t + "</b><br>" + money(v) +
          "<br>" + pct(v, t.tot) + "% выручки месяца");
        stack.appendChild(seg);
      });
      var holder = el("div", "ex-colh");
      holder.appendChild(stack);
      col.appendChild(holder);
      col.appendChild(el("div", "ex-cval", Math.round(t.tot / 1000) + "т"));
      col.appendChild(el("div", "ex-clab", MOSHORT[t.m]));
      bindTip(col, "<b>" + MONTHS[t.m] + "</b><br>визитов: " + t.sel.length +
        "<br>выручка: " + money(t.tot));
      cols.appendChild(col);
    });
    scroll.appendChild(cols);
    wrap.appendChild(scroll);

    var all = sum(F, function (r) { return r.sum; });
    var shareRows = CAT.map(function (c) {
      var v = sum(F, function (r) { return catSum(r, c.k); });
      return { t: c.t, v: v, l: money(v) + " · " + pct(v, all) + "%", c: c.c };
    });
    wrap.appendChild(el("div", "ex-sub", "За выбранный период целиком"));
    var bars = barChart("", shareRows, {});
    bars.className = "ex-inline";
    wrap.appendChild(bars);
    wrap.appendChild(el("div", "ex-note",
      "Кабина — это то, что мы получаем просто за то, что открылись. Всё остальное появляется только тогда, когда администратор что-то предложил."));
    return wrap;
  }

  /* кабины */
  function cabins(F) {
    var list = ["1", "2", "3", "4", "5", "6"];
    var rows = [];
    list.forEach(function (c) {
      var sel = F.filter(function (r) { return r.cab === c; });
      if (!sel.length) return;
      var avg = sum(sel, function (r) { return r.sum; }) / sel.length;
      rows.push({
        t: "№" + c + (c === "1" ? " (VIP)" : ""), v: avg, l: money(avg),
        tip: "<b>Кабина №" + c + "</b><br>визитов: " + sel.length +
             "<br>средний чек: " + money(avg) +
             "<br>всего: " + money(sum(sel, function (r) { return r.sum; }))
      });
    });
    var known = F.filter(function (r) { return r.cab; }).length;
    return barChart("Средний чек по кабинам", rows, {
      note: "Номер кабины записан у " + num(known) + " визитов из " + num(F.length) +
            ". Наведите на строку — там число визитов: у редких кабин средний чек считается по единицам."
    });
  }

  /* что заказывают — таблица */
  function itemTable(F) {
    var wrap = el("div", "ex-block");
    wrap.appendChild(el("h3", null, "Что заказывают чаще всего"));
    var agg = {};
    F.forEach(function (r) {
      (r.it || []).forEach(function (t) {
        var a = agg[t[0]] || (agg[t[0]] = { s: 0, v: 0, q: 0 });
        a.s += t[1]; a.v++; a.q += t[2];
      });
    });
    var keys = Object.keys(agg).sort(function (a, b) { return agg[b].s - agg[a].s; });
    var scroll = el("div", "ex-scroll");
    var tb = el("table", "ex-table");
    tb.innerHTML = "<thead><tr><th>Позиция</th><th class='num'>В скольких визитах</th>" +
      "<th class='num'>Доля визитов</th><th class='num'>Денег</th></tr></thead>";
    var body = el("tbody");
    keys.forEach(function (k) {
      var a = agg[k];
      var tr = el("tr");
      tr.innerHTML = "<td>" + ITEMS[k] + "</td><td class='num'>" + num(a.v) +
        "</td><td class='num'>" + pct(a.v, F.length) + "%</td><td class='num'>" + money(a.s) + "</td>";
      body.appendChild(tr);
    });
    tb.appendChild(body);
    scroll.appendChild(tb);
    wrap.appendChild(scroll);
    wrap.appendChild(el("div", "ex-note",
      "Названия из тетрадей сведены в группы: например «садан», «торман», «сазан жареный» — это одна строка. " +
      "Таблица считается по тем же визитам, что и всё выше."));
    return wrap;
  }

  /* возвращаемость */
  function repeat(F) {
    var wrap = el("div", "ex-block");
    wrap.appendChild(el("h3", null, "Кто пришёл второй раз"));
    var first = F.filter(function (r) { return r.rep === 1; });
    var again = F.filter(function (r) { return r.rep === 2; });
    var once = F.filter(function (r) { return r.rep === 0; });
    var rows = [
      { t: "были один раз", v: once.length, l: visitsN(once.length),
        tip: "Гость, которого мы больше не видели.<br>средний чек: " +
             (once.length ? money(sum(once, function (r) { return r.sum; }) / once.length) : "—") },
      { t: "первый визит тех, кто вернулся", v: first.length, l: visitsN(first.length),
        tip: "Стол в этот вечер брали: " + pct(first.filter(hasFood).length, first.length) + "%" },
      { t: "повторные визиты", v: again.length, l: visitsN(again.length),
        tip: "Стол брали: " + pct(again.filter(hasFood).length, again.length) + "%" }
    ];
    var bars = barChart("", rows, {});
    bars.className = "ex-inline";
    wrap.appendChild(bars);
    wrap.appendChild(el("div", "ex-note",
      "Всего из " + num(META.guests) + " гостей, чьё имя или телефон записаны, второй раз пришли " +
      num(META.returning) + ". В первый вечер стол брали " +
      pct(first.filter(hasFood).length, first.length || 1) + "% тех, кто потом вернулся, против " +
      pct(once.filter(hasFood).length, once.length || 1) + "% тех, кто не вернулся. " +
      "Гостя без записанного телефона и имени мы посчитать не можем — он попадает в «были один раз»."));
    return wrap;
  }

  /* ---------- сборка ---------- */
  var root;
  function render() {
    if (!root) return;
    var F = filtered();
    root.innerHTML = "";
    root.appendChild(filters());
    if (!F.length) {
      root.appendChild(el("div", "ex-empty",
        "Под такие условия не попал ни один визит. Снимите часть фильтров."));
      return;
    }
    root.appendChild(tiles(F));
    root.appendChild(heatmap(F));
    root.appendChild(byPeople(F));
    root.appendChild(attach(F));
    root.appendChild(basket(F));
    root.appendChild(cabins(F));
    root.appendChild(repeat(F));
    root.appendChild(itemTable(F));
  }

  document.addEventListener("DOMContentLoaded", function () {
    root = document.getElementById("ex-root");
    render();
  });
})();
