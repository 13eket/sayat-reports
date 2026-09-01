#!/usr/bin/env python3
"""Собирает data.js для виджета «Покрутите цифры сами».

    python3 build_data.py путь/к/otchet_photos_text.json

Исходник — расшифровка 266 листов рукописных отчётов бани «Саят»
(Telegram-экспорт). Результат кладётся рядом: klient/data.js."""
import json, re, collections, os, sys, datetime

SRC = sys.argv[1] if len(sys.argv) > 1 else "otchet_photos_text.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")

raw = json.load(open(SRC))
O = [x for x in raw if x.get("type") == "otchet"]
O.sort(key=lambda x: int(re.match(r"photo_(\d+)@", x["file"]).group(1)))

def sheet_day(x):
    """Рабочий день листа. Если лист есть на самом листе — берём его.
    Иначе дата отправки фото; снятое до 9 утра относится к прошедшему вечеру."""
    sd = x.get("sheet_date") or ""
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", sd)
    if m:
        y = int(m.group(3))
        y = y + 2000 if y < 100 else y
        try:
            return datetime.date(y, int(m.group(2)), int(m.group(1))).strftime("%d.%m.%Y")
        except ValueError:
            pass
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2})", x["sent_date"])
    d0 = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    if int(m.group(4)) < 9:
        d0 -= datetime.timedelta(days=1)
    return d0.strftime("%d.%m.%Y")


# ---- 1. split the photo stream into business days (num resets to 1) ----------
days, cur, prev = [], None, None
for x in O:
    for e in x["entries"]:
        n = e.get("num")
        if cur is None or (n is not None and prev is not None and n < prev) or (n == 1 and prev != 1):
            cur = {"date": sheet_day(x), "ent": []}
            days.append(cur)
        cur["ent"].append(e)
        if n is not None:
            prev = n

# ---- 1b. развести листы, снятые пачкой ---------------------------------------
# Иногда админ фотографировал несколько листов сразу: тогда на одну дату отправки
# приходится несколько рабочих дней. Даты идут строго по возрастанию в порядке
# съёмки, поэтому более ранние листы пачки отодвигаем назад по одному дню.
_d = [datetime.datetime.strptime(dd["date"], "%d.%m.%Y").date() for dd in days]
for i in range(len(_d) - 2, -1, -1):
    if _d[i] >= _d[i + 1]:
        _d[i] = _d[i + 1] - datetime.timedelta(days=1)
for dd, dv in zip(days, _d):
    dd["date"] = dv.strftime("%d.%m.%Y")

# ---- 2. merge continuation rows (same day + same num) -----------------------
visits = []
for dd in days:
    m, order = {}, []
    for e in dd["ent"]:
        n = e.get("num")
        k = n if n is not None else ("x", len(m))
        if k in m:
            m[k]["items"] = (m[k].get("items") or []) + (e.get("items") or [])
            for f in ("total", "people", "hours", "time_start", "time_end",
                      "payment", "net", "phone", "cabin", "note", "name"):
                if not m[k].get(f) and e.get(f):
                    m[k][f] = e[f]
            m[k]["uncertain"] = m[k].get("uncertain") or e.get("uncertain")
        else:
            m[k] = dict(e)
            order.append(k)
    for k in order:
        v = m[k]
        v["_date"] = dd["date"]
        visits.append(v)

# ---- 3. drop day-summary rows (they double-count the whole day) -------------
def is_summary(e):
    note = (e.get("note") or "").lower()
    if not e.get("items") and not e.get("name"):
        return True
    if "итог" in note and not e.get("items"):
        return True
    return False

visits = [v for v in visits if not is_summary(v)]

# ---- 4. item categorisation --------------------------------------------------
def norm(s):
    s = (s or "").strip().lower().replace("ё", "е")
    return re.sub(r"\s+", " ", s)

CAT_RULES = [
    ("cabin",  r"кабин|^каб\b|^каб\.|^баня$|^сауна$|^казан$"),
    ("serv",   r"пилинг|массаж|веник|банщик"),
    ("alc",    r"пиво|водка|carlsberg|holsten|жигул|дербес|миллер|efes|baltika|крига|разлив"),
    ("cons",   r"простын|полотенц|шапк|мочалк|скраб|перчат|станок|бритв|шампун|мыло|тапочк|гель|крем|палочк|ухочист|салфет|спичк|освежит"),
    ("drink",  r"кола|вода|бонакв|боначе|бонакв|тассай|tassay|квас|чай|сок|лимонад|натахтар|нагахт|катахтар|казахтар|начахтар|ногахтар|мохито|лохито|боржоми|кымыз|молоко|напиток|коктейл|лед|лёд|шар|сарыагаш|туран|duran|bonaqua|piko|pico|rico|riko|rich|кальян|чилим|zigi|бокал"),
    ("food",   r"куырдак|кудердак|курдак|бурдак|курдюк|жаркое|сазан|садан|торман|жорман|терман|рыб|робец|рыбец|вобла|жерех|осетр|ксерех|хлеб|боорсок|боорсак|самса|лепешк|чипс|лейс|кириешк|сухарик|семечк|салат|соус|суп|борщ|пельмен|чебурек|крыл|мясо|ребра|колбас|шашлык|фри|картофел|курт|мед|мд |сладост|шоколад|рошен|пирожк|млинец|кростини|комбо|колбо|сет|лук|лимон|капуст|кетчуп|бор жарма|ролтон|торман|чалагай|шекеса|кызанак|кериш|керим|млинец"),
]
def category(item):
    s = norm(item)
    for cat, rx in CAT_RULES:
        if re.search(rx, s):
            return cat
    return "other"

# canonical item names for the item table (collapse OCR variants)
CANON = [
    ("кабина",        r"кабин|^каб\b|^каб\."),
    ("пилинг",        r"пилинг"),
    ("массаж",        r"массаж"),
    ("веник",         r"веник"),
    ("простыня",      r"простын"),
    ("полотенце",     r"полотенц"),
    ("шапка",         r"шапк"),
    ("мочалка/скраб", r"мочалк|скраб|перчат"),
    ("бритва/станок", r"бритв|станок"),
    ("шампунь/мыло",  r"шампун|мыло|гель|крем"),
    ("пиво",          r"пиво|carlsberg|holsten|жигул|дербес|миллер|efes|baltika|крига"),
    ("водка",         r"водка"),
    ("квас",          r"квас"),
    ("кола",          r"кола"),
    ("вода",          r"вода|бонакв|боначе|тассай|tassay|bonaqua|сарыагаш|туран|duran|боржоми"),
    ("чай",           r"чай"),
    ("сок",           r"сок|piko|pico|rico|riko|rich"),
    ("лимонад",       r"лимонад|натахтар|нагахт|катахтар|казахтар|начахтар|ногахтар|мохито|лохито|коктейл|напиток"),
    ("кымыз",         r"кымыз"),
    ("лёд",           r"^лед|^лёд|шар"),
    ("куырдак",       r"куырдак|кудердак|курдак|бурдак|курдюк|жаркое"),
    ("сазан/торман",  r"сазан|садан|торман|жорман|терман|чалагай"),
    ("рыбец/сушёная рыба", r"рыб|робец|вобла|жерех|осетр|ксерех"),
    ("хлеб/лепёшка",  r"хлеб|боорсок|боорсак|лепешк"),
    ("самса/чебурек/пельмени", r"самса|чебурек|пельмен|пирожк|млинец"),
    ("чипсы/сухарики/орешки", r"чипс|лейс|кириешк|сухарик|семечк|курт|кростини"),
    ("салат",         r"салат|капуст|лук|лимон"),
    ("соус",          r"соус|кетчуп"),
    ("мясо/шашлык/крылья", r"мясо|ребра|колбас|шашлык|крыл|казан"),
    ("суп",           r"суп|борщ|ролтон"),
    ("фри",           r"фри|картофел"),
    ("мёд/сладости",  r"^мед|^мёд|^мд |сладост|шоколад|рошен"),
    ("комбо-сет",     r"комбо|колбо|^сет"),
    ("кальян",        r"кальян|чилим"),
]
def canon(item):
    s = norm(item)
    for name, rx in CANON:
        if re.search(rx, s):
            return name
    return "прочее"

# ---- 5. build the flat records ----------------------------------------------
WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS = {2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь", 7: "июль", 8: "август"}

def hour_of(t):
    if not t:
        return None
    m = re.match(r"(\d{1,2})[:.](\d{2})", str(t))
    if not m:
        m = re.match(r"^(\d{1,2})$", str(t).strip())
        return int(m.group(1)) if m else None
    h = int(m.group(1))
    return h if 0 <= h <= 23 else None

def clean_phone(p):
    if not p:
        return None
    d = re.sub(r"\D", "", str(p))
    if len(d) < 10:
        return None
    return d[-10:]

items_dict, item_id = [], {}
def iid(name):
    if name not in item_id:
        item_id[name] = len(items_dict)
        items_dict.append(name)
    return item_id[name]

recs = []
for v in visits:
    dparts = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", v["_date"])
    dt = datetime.date(int(dparts.group(3)), int(dparts.group(2)), int(dparts.group(1)))
    cats = collections.Counter()
    ilist = collections.Counter()
    iqty = collections.Counter()
    for it in (v.get("items") or []):
        s = it.get("sum") or 0
        c = category(it.get("item"))
        cats[c] += s
        cn = canon(it.get("item"))
        ilist[cn] += s
        iqty[cn] += (it.get("qty") or 1)
    # «заказал стол» = взял настоящее блюдо, а не хлеб, соус или конфету к чаю
    DISH = {"куырдак", "сазан/торман", "рыбец/сушёная рыба", "самса/чебурек/пельмени",
            "мясо/шашлык/крылья", "суп", "фри", "комбо-сет", "салат"}
    dish = 1 if any(k in DISH for k in ilist) else 0
    note_l = (v.get("note") or "").lower()
    total = v.get("total") or sum(cats.values())
    if not total:
        # keep zero-revenue visits only when the sheet says they were free
        # (the giveaway evenings); drop rows whose prices were simply unreadable
        if not re.search(r"беспл|подар|бонус", note_l):
            continue
    cab = str(v.get("cabin") or "").strip()
    cab = cab if re.fullmatch(r"[1-9]", cab) else ""
    ppl = v.get("people")
    ppl = int(ppl) if isinstance(ppl, (int, float)) and 1 <= ppl <= 20 else None
    hrs = v.get("hours")
    hrs = float(hrs) if isinstance(hrs, (int, float)) and 0 < hrs <= 12 else None
    note = note_l
    gift = 1 if re.search(r"беспл|подар|бонус|в подарок", note) else 0
    disc = 1 if re.search(r"скидк", note) else 0
    debt = 1 if re.search(r"долг", note) else 0
    pay = v.get("payment")
    pay = {"nal": "cash", "cash": "cash", "kaspi": "kaspi", "mixed": "mixed",
           "transfer": "kaspi", "remote": "kaspi"}.get(pay)
    phone = clean_phone(v.get("phone"))
    name = (v.get("name") or "").strip()
    recs.append({
        "d": dt.isoformat(),
        "mo": dt.month,
        "wd": dt.weekday(),
        "h": hour_of(v.get("time_start")),
        "dur": hrs,
        "cab": cab,
        "ppl": ppl,
        "sum": int(total),
        "pay": pay,
        "gift": gift, "disc": disc, "debt": debt, "dish": dish,
        "c": {k: int(val) for k, val in cats.items() if val},
        "it": [[iid(k), int(val), round(q, 1)] for k, (val, q) in
               ((k, (ilist[k], iqty[k])) for k in ilist)],
        "n": name,
        "p": phone,
    })

# ---- 6. guest identity + repeat flag ----------------------------------------
key_of = lambda r: ("p:" + r["p"]) if r["p"] else (("n:" + r["n"].lower()) if r["n"] else None)
counts = collections.Counter(k for k in map(key_of, recs) if k)
firstseen = {}
for r in sorted(recs, key=lambda r: r["d"]):
    k = key_of(r)
    r["rep"] = 0
    if k and counts[k] > 1:
        if k in firstseen:
            r["rep"] = 2          # a return visit
        else:
            firstseen[k] = r["d"]
            r["rep"] = 1          # first visit of a guest who came back
    r.pop("n", None)
    r.pop("p", None)

recs.sort(key=lambda r: (r["d"], r["h"] if r["h"] is not None else 99))

meta = {
    "visits": len(recs),
    "revenue": sum(r["sum"] for r in recs),
    "days": len(set(r["d"] for r in recs)),
    "from": min(r["d"] for r in recs),
    "to": max(r["d"] for r in recs),
    "items": items_dict,
    "guests": len(counts),
    "returning": sum(1 for v in counts.values() if v > 1),
}
with open(OUT, "w") as f:
    f.write("window.SAYAT_DATA=")
    json.dump({"meta": meta, "rows": recs}, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")

print(json.dumps(meta, ensure_ascii=False, indent=1)[:900])
print("bytes", len(open(OUT).read()))
print("cat totals", collections.Counter({k: sum(r["c"].get(k, 0) for r in recs)
                                         for k in ["cabin", "serv", "food", "drink", "alc", "cons", "other"]}))
unc = [i for i in items_dict]
print("canon buckets", len(items_dict))
print("with hour", sum(1 for r in recs if r["h"] is not None),
      "with dur", sum(1 for r in recs if r["dur"]),
      "with ppl", sum(1 for r in recs if r["ppl"]),
      "with cab", sum(1 for r in recs if r["cab"]),
      "gift", sum(r["gift"] for r in recs), "disc", sum(r["disc"] for r in recs))
