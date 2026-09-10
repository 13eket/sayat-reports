#!/usr/bin/env python3
"""Пересобирает все цифры сайта «Саят» из двух источников:

  1. otchet_photos_text.json  — расшифровка рукописных отчётов (выручка)
  2. expenses_2026_08.json    — рукописный лист расходов за август 2026

Пишет:
  klient/data.js  — данные для интерактивного виджета
  figures.json    — все агрегаты для index.html / months.html / klient/index.html

Запуск:  python3 rebuild.py /path/to/otchet_photos_text.json /path/to/expenses_2026_08.json
"""
import json, re, sys, os, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else "otchet_photos_text.json"
EXPSRC = sys.argv[2] if len(sys.argv) > 2 else "expenses_2026_08.json"

# ═══════════════════════════════════════════════════════════════════════════
# 1. Разбор листов → визиты
# ═══════════════════════════════════════════════════════════════════════════
raw = json.load(open(SRC))
O = [x for x in raw if x.get("type") == "otchet"]
O.sort(key=lambda x: int(re.match(r"photo_(\d+)@", x["file"]).group(1)))


def sheet_day(x):
    """Рабочий день листа: своя дата на листе, иначе дата отправки
    (снятое до 9 утра относится к прошедшему вечеру)."""
    sd = x.get("sheet_date") or ""
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", sd)
    if m:
        y = int(m.group(3))
        y = y + 2000 if y < 100 else y
        try:
            return datetime.date(y, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2})", x["sent_date"])
    d0 = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    if int(m.group(4)) < 9:
        d0 -= datetime.timedelta(days=1)
    return d0


# Границу рабочего дня задаёт дата самого листа, а не номер визита.
# (Старая версия ломалась на двух подряд днях по одному визиту с номером 1:
#  день не разрывался, записи сливались и вторая выручка терялась.)
G = collections.defaultdict(list)
for x in O:
    d = sheet_day(x)
    for e in x["entries"]:
        G[d].append(dict(e))

visits = []
for d in sorted(G):
    slot, order = {}, []
    for e in G[d]:
        num = e.get("num")
        k = num if num is not None else ("x", len(slot))
        # склеиваем только настоящее продолжение строки: у продолжения нет своего итога
        if k in slot and not (e.get("total") and slot[k].get("total")):
            a = slot[k]
            a["items"] = (a.get("items") or []) + (e.get("items") or [])
            for f in ("total", "people", "hours", "time_start", "time_end",
                      "payment", "phone", "cabin", "note", "name"):
                if not a.get(f) and e.get(f):
                    a[f] = e[f]
        else:
            if k in slot:
                k = ("dup", len(slot))
            slot[k] = dict(e)
            order.append(k)
    for k in order:
        v = slot[k]
        note = (v.get("note") or "").lower()
        if not v.get("items") and not v.get("name"):
            continue                       # итоговая страница дня — не визит
        items_sum = sum((i.get("sum") or 0) for i in (v.get("items") or []))
        total = v.get("total") or items_sum
        if not total and not re.search(r"беспл|подар|бонус", note):
            continue                       # цены не читаются — не считаем
        v["_d"] = d
        v["_total"] = total
        v["_items_sum"] = items_sum
        visits.append(v)

# ═══════════════════════════════════════════════════════════════════════════
# 2. Товарная номенклатура: 520 написаний → канонические позиции и 10 категорий
# ═══════════════════════════════════════════════════════════════════════════
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower().replace("ё", "е"))


CAB, PEEL, SERV, LIN, FOOD, TEA, SOFT, ALC, NODET, DISC = (
    "Кабина", "Пилинг", "Прочие услуги", "Бельё и расходники", "Еда и закуски",
    "Чай и кофе", "Напитки б/а", "Пиво и алкоголь", "Без детализации",
    "Скидки и корректировки")

# (каноническое имя, категория, regex).  Порядок важен — первое совпадение выигрывает.
RULES = [
    ("кабина",                  CAB,  r"^кабин|^каб\b|^каб\.|^баня$|^сауна$"),
    ("пилинг",                  PEEL, r"пилинг"),
    ("массаж",                  SERV, r"массаж"),
    ("веник",                   SERV, r"веник"),
    ("услуги банщика",          SERV, r"банщик"),
    ("простыня",                LIN,  r"простын"),
    ("полотенце",               LIN,  r"полотенц"),
    ("шапка банная",            LIN,  r"шапк"),
    ("мочалка / скраб",         LIN,  r"мочалк|скраб|перчат"),
    ("бритва одноразовая",      LIN,  r"бритв|станок"),
    ("шампунь / мыло / гель",   LIN,  r"шампун|мыло|гель|крем|тапочк|салфет|ухочист|палочк|спичк|освежит"),
    ("водка",                   ALC,  r"водка|коньяк|виски"),
    ("пиво разливное",          ALC,  r"пиво.*(разлив|л\)|литр)|разлив.*пиво"),
    ("пиво Carlsberg",          ALC,  r"carlsberg|карлсберг"),
    ("пиво Holsten",            ALC,  r"holsten|холстен"),
    ("пиво Жигулёвское",        ALC,  r"жигул"),
    ("пиво Дербес",             ALC,  r"дербес"),
    ("пиво Miller",             ALC,  r"миллер|miller"),
    ("пиво Прага",              ALC,  r"прага"),
    ("пиво прочее",             ALC,  r"пиво|efes|baltika|крига|брага"),
    ("квас",                    SOFT, r"квас"),
    ("кола",                    SOFT, r"кола|pepsi|пепси"),
    ("вода",                    SOFT, r"^вода|бонакв|боначе|тассай|tassay|bonaqua|сарыагаш|туран|duran|боржоми"),
    ("лимонад / мохито",        SOFT, r"лимонад|натахтар|нагахт|катахтар|казахтар|начахтар|ногахтар|мохито|лохито|коктейл|напиток"),
    ("сок",                     SOFT, r"сок|piko|pico|rico|riko|rich"),
    ("кымыз",                   SOFT, r"кымыз|молоко|айран|шубат"),
    ("лёд",                     SOFT, r"^лед|^лёд|^шар"),
    ("кальян",                  SERV, r"кальян|чилим"),
    ("чай",                     TEA,  r"чай|чайник|кофе"),
    ("куырдак",                 FOOD, r"куырдак|кудердак|курдак|бурдак|курдюк|жаркое"),
    ("сазан / торман",          FOOD, r"сазан|садан|торман|жорман|терман|чалагай"),
    ("рыбец / сушёная рыба",    FOOD, r"рыб|робец|вобла|жерех|осетр|ксерех"),
    ("пельмени",                FOOD, r"пельмен"),
    ("самса / чебурек",         FOOD, r"самса|чебурек|пирожк|млинец|блин"),
    ("хлеб / лепёшка",          FOOD, r"хлеб|боорсок|боорсак|лепешк"),
    ("салат",                   FOOD, r"салат|капуст|^лук|^лимон|кызанак"),
    ("фри / картофель",         FOOD, r"фри|картофел"),
    ("чипсы / сухарики / орешки", FOOD, r"чипс|лейс|кириешк|сухарик|семечк|курт|кростини|кериш|керим"),
    ("мясо / шашлык / крылья",  FOOD, r"мясо|ребра|колбас|шашлык|крыл|казан"),
    ("суп",                     FOOD, r"суп|борщ|ролтон"),
    ("соус / кетчуп",           FOOD, r"соус|кетчуп"),
    ("комбо-сет",               FOOD, r"комбо|колбо|^сет"),
    ("мёд / сладости",          FOOD, r"^мед|^мд |сладост|шоколад|рошен|шекеса"),
]


def classify(item):
    s = norm(item)
    for name, cat, rx in RULES:
        if re.search(rx, s):
            return name, cat
    return "прочее", NODET


# ═══════════════════════════════════════════════════════════════════════════
# 3. Модель себестоимости — выведена из листа расходов за август 2026
# ═══════════════════════════════════════════════════════════════════════════
EXP = json.load(open(EXPSRC))
E = {i["n"]: (i["amount"] or 0) for i in EXP["items"]}

WATER, ELEC, GAS, GASTO = E[1], E[2], E[3], E[4]
SEPTIC = E[9]
SALARY, ACCOUNTANT, TAXES_M, TAX_H1 = E[5], E[6], E[7], E[8]
PHONE, VENIKI, BEER, SOFTBUY = E[10], E[11], E[12], E[13]
FANS, CERTS, INVENTORY, WASHERS, CLEANING, FOODBUY = E[14], E[15], E[16], E[17], E[18], E[19]
CON, CONTRACTORS = E[20], E[21]

VENIK_UNIT = 1800          # 10 веников за 18 000 ₸
PEEL_CAP = 2000            # ваша доля с сеанса пилинга/массажа
CONS_MARGIN = 0.50         # мочалки, скрабы, шампуни, бритвы

# постоянные расходы месяца (всё, что не зависит от числа гостей)
FIXED_MONTH = (SALARY + ACCOUNTANT + TAXES_M + PHONE + CONTRACTORS
               + CLEANING + GASTO / 3)
# разовое и капитальное за август — вне месячной маржи
ONE_OFF_AUG = TAX_H1 + FANS + CERTS + INVENTORY + CON

# ═══════════════════════════════════════════════════════════════════════════
# 4. Помесячные агрегаты
# ═══════════════════════════════════════════════════════════════════════════
WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MNAME = {2: ("Февраль", "Фев"), 3: ("Март", "Мар"), 4: ("Апрель", "Апр"),
         5: ("Май", "Май"), 6: ("Июнь", "Июн"), 7: ("Июль", "Июл"),
         8: ("Август", "Авг"), 9: ("Сентябрь", "Сен")}


def hour_of(t):
    if not t:
        return None
    m = re.match(r"(\d{1,2})[:.](\d{2})", str(t)) or re.match(r"^(\d{1,2})$", str(t).strip())
    if not m:
        return None
    h = int(m.group(1))
    return h if 0 <= h <= 23 else None


def clean_phone(p):
    d = re.sub(r"\D", "", str(p or ""))
    return d[-10:] if len(d) >= 10 else None


for v in visits:
    v["_mo"] = v["_d"].strftime("%Y-%m")
    h = v.get("hours")
    v["_h"] = float(h) if isinstance(h, (int, float)) and 0 < h <= 12 else None
    p = v.get("people")
    v["_p"] = int(p) if isinstance(p, (int, float)) and 1 <= p <= 20 else None

MONTHS = sorted({v["_mo"] for v in visits})

# оценка числа гостей: где не записано — средний размер компании того же месяца
ppl_avg = {}
for mo in MONTHS:
    vs = [v for v in visits if v["_mo"] == mo and v["_p"]]
    ppl_avg[mo] = (sum(v["_p"] for v in vs) / len(vs)) if vs else 0
overall_avg = (sum(v["_p"] for v in visits if v["_p"])
               / max(1, sum(1 for v in visits if v["_p"])))
for mo in MONTHS:
    if ppl_avg[mo] == 0 or sum(1 for v in visits if v["_mo"] == mo and v["_p"]) < 3:
        ppl_avg[mo] = overall_avg
for v in visits:
    v["_pe"] = v["_p"] if v["_p"] else ppl_avg[v["_mo"]]

# то же для часов кабины
hrs_avg = {}
for mo in MONTHS:
    vs = [v for v in visits if v["_mo"] == mo and v["_h"]]
    hrs_avg[mo] = (sum(v["_h"] for v in vs) / len(vs)) if vs else 0
for v in visits:
    v["_he"] = v["_h"] if v["_h"] else hrs_avg[v["_mo"]]

import calendar
FIRST = min(v["_d"] for v in visits)
LAST = max(v["_d"] for v in visits)

M = {}
for mo in MONTHS:
    vs = [v for v in visits if v["_mo"] == mo]
    M[mo] = {
        "visits": len(vs),
        "days": len({v["_d"] for v in vs}),
        "rev": sum(v["_total"] for v in vs),
        "hours": round(sum(v["_he"] for v in vs), 1),
        "hours_rec": round(sum(v["_h"] for v in vs if v["_h"]), 1),
        "guests": round(sum(v["_pe"] for v in vs)),
        "guests_rec": sum(v["_p"] for v in vs if v["_p"]),
        "rec_n": sum(1 for v in vs if v["_p"]),
        "hours_rec_n": sum(1 for v in vs if v["_h"]),
        "ppl_avg": round(ppl_avg[mo], 2),
    }
    # неполные месяцы (первый и последний в наблюдении) получают долю постоянных расходов
    y, mm = int(mo[:4]), int(mo[5:])
    dim = calendar.monthrange(y, mm)[1]
    lo = max(FIRST, datetime.date(y, mm, 1))
    hi = min(LAST, datetime.date(y, mm, dim))
    M[mo]["cover"] = round((hi - lo).days + 1) / dim
    M[mo]["partial"] = M[mo]["cover"] < 0.95

AUG = "2026-08"
JUL = "2026-07"

# ── ставки переменных расходов ───────────────────────────────────────────────
# свет + вода + газ: счета за июль (пришли в августе) на июльское число гостей
UTIL_PER_GUEST = (WATER + ELEC + GAS) / M[JUL]["guests"]
# септик: августовский платёж на августовское число гостей
SEPTIC_PER_GUEST = SEPTIC / M[AUG]["guests"]
RESOURCE_PER_GUEST = UTIL_PER_GUEST + SEPTIC_PER_GUEST

# ── ставки себестоимости товара: калибруются так, чтобы август сошёлся с листом ─
cat_rev = collections.defaultdict(lambda: collections.Counter())
item_rev = collections.defaultdict(lambda: collections.Counter())
item_qty = collections.defaultdict(lambda: collections.Counter())
item_cat = {}
peel_share_mo = collections.Counter()
venik_qty_mo = collections.Counter()
linen_rev_mo = collections.Counter()
cons_rev_mo = collections.Counter()

for v in visits:
    mo = v["_mo"]
    for it in (v.get("items") or []):
        s = it.get("sum") or 0
        q = it.get("qty") or 1
        name, cat = classify(it.get("item"))
        cat_rev[mo][cat] += s
        item_rev[mo][name] += s
        item_qty[mo][name] += q
        item_cat[name] = cat
        if cat == PEEL or name in ("массаж", "услуги банщика"):
            peel_share_mo[mo] += min(s / q if q else s, PEEL_CAP) * q
        if name == "веник":
            venik_qty_mo[mo] += q
        if cat == LIN:
            if name in ("простыня", "полотенце", "шапка банная"):
                linen_rev_mo[mo] += s
            else:
                cons_rev_mo[mo] += s
    if not v["_items_sum"] and v["_total"]:
        # лист без построчной разбивки: записан только итог визита
        cat_rev[mo][NODET] += v["_total"]
        item_rev[mo]["без детализации (итог визита)"] += v["_total"]
        item_qty[mo]["без детализации (итог визита)"] += 1
        item_cat["без детализации (итог визита)"] = NODET
        continue
    d = v["_items_sum"] - v["_total"]
    if v["_items_sum"] and d > 0:
        # по позициям насчитано больше, чем получено: скидка по сертификату
        cat_rev[mo][DISC] -= d
        item_rev[mo]["скидка по сертификату"] -= d
        item_qty[mo]["скидка по сертификату"] += 1
        item_cat["скидка по сертификату"] = DISC
    elif v["_items_sum"] and d < 0:
        # получено больше, чем расписано: часть позиций на листе не указана
        cat_rev[mo][NODET] += -d
        item_rev[mo]["не расписано по позициям"] += -d
        item_qty[mo]["не расписано по позициям"] += 1
        item_cat["не расписано по позициям"] = NODET

COGS_FOOD = FOODBUY / (cat_rev[AUG][FOOD] + cat_rev[AUG][TEA])
COGS_SOFT = SOFTBUY / cat_rev[AUG][SOFT]
COGS_ALC = BEER / cat_rev[AUG][ALC]
# «без детализации»: неизвестно, что именно продали, поэтому на такую выручку
# начисляется средняя по бане доля закупки товара (считается ниже, после первого прохода)
NODET_COGS = 0.0

# ── помесячная P&L ───────────────────────────────────────────────────────────
for mo in MONTHS:
    m, cr = M[mo], cat_rev[mo]
    m["cat_rev"] = dict(cr)
    m["res_cost"] = round(RESOURCE_PER_GUEST * m["guests"])
    m["res_per_hour"] = round(m["res_cost"] / m["hours"]) if m["hours"] else 0
    m["cogs_food"] = round((cr[FOOD] + cr[TEA]) * COGS_FOOD)
    m["cogs_soft"] = round(cr[SOFT] * COGS_SOFT)
    m["cogs_alc"] = round(cr[ALC] * COGS_ALC)
    m["cogs_cons"] = round(cons_rev_mo[mo] * CONS_MARGIN)
    m["cogs_venik"] = round(venik_qty_mo[mo] * VENIK_UNIT)
    m["cogs_nodet"] = 0
    m["goods_cost"] = (m["cogs_food"] + m["cogs_soft"] + m["cogs_alc"]
                       + m["cogs_cons"] + m["cogs_venik"])
    m["peel_master"] = round((cr[PEEL] + cr[SERV] - item_rev[mo]["веник"]
                              - item_rev[mo]["кальян"]) - peel_share_mo[mo])
    m["disc"] = -round(cr[DISC])
    m["undetailed"] = round(cr[NODET])
    m["gross"] = round(m["rev"] - m["res_cost"] - m["goods_cost"] - m["peel_master"])
    m["fixed"] = round(FIXED_MONTH * m["cover"])
    m["net"] = m["gross"] - m["fixed"]
    m["cm_visit"] = round(m["gross"] / m["visits"]) if m["visits"] else 0
    m["breakeven_visits"] = round(m["fixed"] / m["cm_visit"]) if m["cm_visit"] > 0 else 0
    m["gross_pct"] = round(m["gross"] / m["rev"] * 100, 1) if m["rev"] else 0
    m["net_pct"] = round(m["net"] / m["rev"] * 100, 1) if m["rev"] else 0
    m["aov"] = round(m["rev"] / m["visits"]) if m["visits"] else 0
    m["rpd"] = round(m["rev"] / m["days"]) if m["days"] else 0
    m["ppd"] = round(m["net"] / m["days"]) if m["days"] else 0
    m["name"], m["short"] = MNAME[int(mo[5:])]
    m["k"] = mo

# второй проход: средняя доля закупки в выручке — её же применяем к «без детализации»
_detailed_rev = sum(M[mo]["rev"] - cat_rev[mo][NODET] for mo in MONTHS)
NODET_COGS = sum(M[mo]["goods_cost"] for mo in MONTHS) / _detailed_rev
for mo in MONTHS:
    m = M[mo]
    m["cogs_nodet"] = round(cat_rev[mo][NODET] * NODET_COGS)
    m["goods_cost"] += m["cogs_nodet"]
    m["gross"] = round(m["rev"] - m["res_cost"] - m["goods_cost"] - m["peel_master"])
    m["net"] = m["gross"] - m["fixed"]
    m["gross_pct"] = round(m["gross"] / m["rev"] * 100, 1) if m["rev"] else 0
    m["net_pct"] = round(m["net"] / m["rev"] * 100, 1) if m["rev"] else 0
    m["ppd"] = round(m["net"] / m["days"]) if m["days"] else 0
    m["cm_visit"] = round(m["gross"] / m["visits"]) if m["visits"] else 0
    m["breakeven_visits"] = round(m["fixed"] / m["cm_visit"]) if m["cm_visit"] > 0 else 0

# будни / выходные
for mo in MONTHS:
    wd = [v for v in visits if v["_mo"] == mo and v["_d"].weekday() < 5]
    we = [v for v in visits if v["_mo"] == mo and v["_d"].weekday() >= 5]
    M[mo]["wd_rpd"] = round(sum(v["_total"] for v in wd) / max(1, len({v["_d"] for v in wd})))
    M[mo]["we_rpd"] = round(sum(v["_total"] for v in we) / max(1, len({v["_d"] for v in we})))
    dish = {"куырдак", "сазан / торман", "рыбец / сушёная рыба", "пельмени",
            "самса / чебурек", "мясо / шашлык / крылья", "суп", "фри / картофель",
            "комбо-сет", "салат"}
    vs = [v for v in visits if v["_mo"] == mo]
    M[mo]["attach"] = round(100 * sum(
        1 for v in vs if any(classify(i.get("item"))[0] in dish for i in (v.get("items") or []))
    ) / max(1, len(vs)), 1)

# ═══════════════════════════════════════════════════════════════════════════
# 5. Позиции: выручка и валовая прибыль по каждой, по месяцам
# ═══════════════════════════════════════════════════════════════════════════
def item_profit(name, cat, mo, rev, qty):
    if cat == CAB:
        return rev - M[mo]["res_cost"]
    if cat == PEEL or name in ("массаж", "услуги банщика"):
        share = 0
        for v in visits:
            if v["_mo"] != mo:
                continue
            for it in (v.get("items") or []):
                if classify(it.get("item"))[0] == name:
                    q = it.get("qty") or 1
                    share += min((it.get("sum") or 0) / q, PEEL_CAP) * q
        return share
    if name == "веник":
        return rev - VENIK_UNIT * qty
    if cat == LIN:
        return rev if name in ("простыня", "полотенце", "шапка банная") else rev * (1 - CONS_MARGIN)
    if cat in (FOOD, TEA):
        return rev * (1 - COGS_FOOD)
    if cat == SOFT:
        return rev * (1 - COGS_SOFT)
    if cat == ALC:
        return rev * (1 - COGS_ALC)
    if cat == DISC:
        return rev
    if cat == NODET:
        return rev * (1 - NODET_COGS)
    return rev * 0.5


all_items = sorted({n for mo in MONTHS for n in item_rev[mo]},
                   key=lambda n: -sum(item_rev[mo][n] for mo in MONTHS))
ITEMS = []
for name in all_items:
    cat = item_cat[name]
    per = {}
    for mo in MONTHS:
        if item_rev[mo][name] or item_qty[mo][name]:
            r = item_rev[mo][name]
            q = round(item_qty[mo][name], 1)
            per[mo] = [q, round(r), round(item_profit(name, cat, mo, r, q))]
    R = sum(p[1] for p in per.values())
    P = sum(p[2] for p in per.values())
    Q = round(sum(p[0] for p in per.values()), 1)
    ITEMS.append({"n": name, "cat": cat, "q": Q, "r": R, "p": P,
                  "mp": round(P / R * 100) if R else 0, "m": per})

CATS = []
for cat in [CAB, FOOD, ALC, PEEL, LIN, SOFT, TEA, SERV, NODET, DISC]:
    sub = [i for i in ITEMS if i["cat"] == cat]
    if not sub:
        continue
    per = {}
    for mo in MONTHS:
        q = sum(i["m"].get(mo, [0, 0, 0])[0] for i in sub)
        r = sum(i["m"].get(mo, [0, 0, 0])[1] for i in sub)
        p = sum(i["m"].get(mo, [0, 0, 0])[2] for i in sub)
        if r or q:
            per[mo] = [round(q, 1), r, p]
    R = sum(i["r"] for i in sub)
    P = sum(i["p"] for i in sub)
    CATS.append({"n": cat, "r": R, "p": P, "mp": round(P / R * 100) if R else 0, "m": per,
                 "items": [i["n"] for i in sub]})

# ═══════════════════════════════════════════════════════════════════════════
# 6. data.js для интерактивного виджета
# ═══════════════════════════════════════════════════════════════════════════
CATKEY = {CAB: "cabin", PEEL: "serv", SERV: "serv", LIN: "cons", FOOD: "food",
          TEA: "drink", SOFT: "drink", ALC: "alc", NODET: "other", DISC: "other"}
items_dict, item_id = [], {}


def iid(nm):
    if nm not in item_id:
        item_id[nm] = len(items_dict)
        items_dict.append(nm)
    return item_id[nm]


DISH = {"куырдак", "сазан / торман", "рыбец / сушёная рыба", "пельмени",
        "самса / чебурек", "мясо / шашлык / крылья", "суп", "фри / картофель",
        "комбо-сет", "салат"}
recs = []
for v in visits:
    cats, il, iq = collections.Counter(), collections.Counter(), collections.Counter()
    for it in (v.get("items") or []):
        s = it.get("sum") or 0
        nm, cat = classify(it.get("item"))
        cats[CATKEY[cat]] += s
        il[nm] += s
        iq[nm] += (it.get("qty") or 1)
    note = (v.get("note") or "").lower()
    cab = str(v.get("cabin") or "").strip()
    pay = {"nal": "cash", "cash": "cash", "kaspi": "kaspi", "mixed": "mixed",
           "transfer": "kaspi", "remote": "kaspi"}.get(v.get("payment"))
    recs.append({
        "d": v["_d"].isoformat(), "mo": v["_d"].month, "wd": v["_d"].weekday(),
        "h": hour_of(v.get("time_start")), "dur": v["_h"],
        "cab": cab if re.fullmatch(r"[1-9]", cab) else "",
        "ppl": v["_p"], "sum": int(v["_total"]), "pay": pay,
        "gift": 1 if re.search(r"беспл|подар|бонус", note) else 0,
        "disc": 1 if re.search(r"скидк", note) else 0,
        "debt": 1 if re.search(r"долг", note) else 0,
        "dish": 1 if any(k in DISH for k in il) else 0,
        "c": {k: int(x) for k, x in cats.items() if x},
        "it": [[iid(k), int(il[k]), round(iq[k], 1)] for k in il],
        "n": (v.get("name") or "").strip(), "p": clean_phone(v.get("phone")),
    })

key_of = lambda r: ("p:" + r["p"]) if r["p"] else (("n:" + r["n"].lower()) if r["n"] else None)
counts = collections.Counter(k for k in map(key_of, recs) if k)
seen = set()
for r in sorted(recs, key=lambda r: r["d"]):
    k = key_of(r)
    r["rep"] = 0
    if k and counts[k] > 1:
        r["rep"] = 2 if k in seen else 1
        seen.add(k)
    r.pop("n", None)
    r.pop("p", None)
recs.sort(key=lambda r: (r["d"], r["h"] if r["h"] is not None else 99))

TOT = {
    "visits": len(recs),
    "revenue": sum(r["sum"] for r in recs),
    "days": len({r["d"] for r in recs}),
    "guests": sum(M[mo]["guests"] for mo in MONTHS),
    "hours": round(sum(M[mo]["hours"] for mo in MONTHS), 1),
    "gross": sum(M[mo]["gross"] for mo in MONTHS),
    "net": sum(M[mo]["net"] for mo in MONTHS),
    "from": min(r["d"] for r in recs), "to": max(r["d"] for r in recs),
}
TOT["gross_pct"] = round(TOT["gross"] / TOT["revenue"] * 100, 1)
TOT["net_pct"] = round(TOT["net"] / TOT["revenue"] * 100, 1)
TOT["aov"] = round(TOT["revenue"] / TOT["visits"])
TOT["avg_dur"] = round(TOT["hours"] / TOT["visits"], 2)
TOT["avg_ppl"] = round(sum(r["ppl"] for r in recs if r["ppl"])
                       / sum(1 for r in recs if r["ppl"]), 2)
TOT["one_off"] = ONE_OFF_AUG
TOT["net_after_oneoff"] = 0  # заполняется ниже
TOT["fixed"] = sum(M[mo]["fixed"] for mo in MONTHS)
TOT["res_cost"] = sum(M[mo]["res_cost"] for mo in MONTHS)
TOT["goods_cost"] = sum(M[mo]["goods_cost"] for mo in MONTHS)
TOT["peel_master"] = sum(M[mo]["peel_master"] for mo in MONTHS)
TOT["disc"] = sum(M[mo]["disc"] for mo in MONTHS)
TOT["cm_visit"] = round(TOT["gross"] / TOT["visits"])
TOT["breakeven_visits"] = round(FIXED_MONTH / TOT["cm_visit"])
TOT["res_per_hour"] = round(TOT["res_cost"] / TOT["hours"])
TOT["net_after_oneoff"] = TOT["net"] - ONE_OFF_AUG
TOT["net_after_oneoff_pct"] = round(TOT["net_after_oneoff"] / TOT["revenue"] * 100, 1)
TOT["uniq_guests"] = len(counts)
TOT["returning"] = sum(1 for x in counts.values() if x > 1)

meta = dict(TOT)
meta["items"] = items_dict
meta["cost"] = {
    "res_per_guest": round(RESOURCE_PER_GUEST),
    "cogs_food": round(COGS_FOOD, 4), "cogs_soft": round(COGS_SOFT, 4),
    "cogs_alc": round(COGS_ALC, 4), "peel_cap": PEEL_CAP,
    "venik": VENIK_UNIT, "fixed_month": round(FIXED_MONTH),
}
with open(os.path.join(HERE, "klient", "data.js"), "w") as f:
    f.write("window.SAYAT_DATA=")
    json.dump({"meta": meta, "rows": recs}, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")


# ═══════════════════════════════════════════════════════════════════════════
# 6b. Клиенты, повторные визиты, LTV
# ═══════════════════════════════════════════════════════════════════════════
GROSS_RATE = TOT["gross"] / TOT["revenue"]          # валовая маржа для LTV
byphone = collections.defaultdict(list)
for v in visits:
    ph = clean_phone(v.get("phone"))
    if ph:
        byphone[ph].append(v)

def ltv(sample):
    if not sample:
        return {}
    vis = [len({x["_d"] for x in vs}) for vs in sample]
    rev = [sum(x["_total"] for x in vs) for vs in sample]
    ret = sum(1 for x in vis if x > 1)
    return {
        "clients": len(sample),
        "visits_per": round(sum(vis) / len(sample), 2),
        "return_pct": round(ret / len(sample) * 100, 1),
        "ltv_rev": round(sum(rev) / len(sample)),
        "ltv_gross": round(sum(rev) / len(sample) * GROSS_RATE),
    }

allc = list(byphone.values())
first_mo = {ph: min(x["_mo"] for x in vs) for ph, vs in byphone.items()}
mature = [vs for ph, vs in byphone.items() if first_mo[ph] <= "2026-06"]
CLIENTS = {"all": ltv(allc), "mature": ltv(mature)}

once = [vs for vs in allc if len({x["_d"] for x in vs}) == 1]
rep = [vs for vs in allc if len({x["_d"] for x in vs}) > 1]
CLIENTS["once"] = {"clients": len(once),
                   "avg_rev": round(sum(sum(x["_total"] for x in vs) for vs in once) / max(1, len(once)))}
CLIENTS["repeat"] = {"clients": len(rep),
                     "avg_rev": round(sum(sum(x["_total"] for x in vs) for vs in rep) / max(1, len(rep))),
                     "avg_visits": round(sum(len({x["_d"] for x in vs}) for vs in rep) / max(1, len(rep)), 2)}
gaps = []
for vs in rep:
    ds = sorted({x["_d"] for x in vs})
    gaps += [(ds[i + 1] - ds[i]).days for i in range(len(ds) - 1)]
CLIENTS["avg_gap"] = round(sum(gaps) / len(gaps)) if gaps else 0

COHORT = []
for mo in MONTHS:
    ph = [p for p in byphone if first_mo[p] == mo]
    r = sum(1 for p in ph if len({x["_d"] for x in byphone[p]}) > 1)
    COHORT.append({"m": MNAME[int(mo[5:])][0], "n": len(ph), "r": r,
                   "days": (LAST - datetime.date(int(mo[:4]), int(mo[5:]), 1)).days})

# допродажи и пилинг
CLIENTS["peel_pct"] = round(100 * sum(
    1 for v in visits if any(classify(i.get("item"))[1] == PEEL for i in (v.get("items") or []))
) / len(visits), 1)
CLIENTS["upsell_pct"] = round(100 * sum(
    1 for v in visits if any(classify(i.get("item"))[1] != CAB for i in (v.get("items") or []))
) / len(visits), 1)
CLIENTS["rev_per_guest"] = round(TOT["revenue"] / TOT["guests"])
CLIENTS["gross_per_guest"] = round(TOT["gross"] / TOT["guests"])
CLIENTS["net_per_guest"] = round(TOT["net"] / TOT["guests"])

# кабины: визиты, часы, выручка, ₸/час
CABINS = {}
for v in visits:
    c = str(v.get("cabin") or "").strip()
    if not re.fullmatch(r"[1-9]", c):
        continue
    a = CABINS.setdefault(c, {"visits": 0, "hours": 0.0, "rev": 0})
    a["visits"] += 1
    a["hours"] += v["_he"]
    a["rev"] += v["_total"]
for c, a in CABINS.items():
    a["hours"] = round(a["hours"], 1)
    a["per_hour"] = round(a["rev"] / a["hours"]) if a["hours"] else 0


# ═══════════════════════════════════════════════════════════════════════════
# 6c. Находки для раздела «Неочевидное»
# ═══════════════════════════════════════════════════════════════════════════
DISHSET = DISH
def has(v, pred):
    return any(pred(i) for i in (v.get("items") or []))

with_dish = [v for v in visits if has(v, lambda i: classify(i.get("item"))[0] in DISHSET)]
wo_dish = [v for v in visits if v not in with_dish]
with_peel = [v for v in visits if has(v, lambda i: classify(i.get("item"))[1] == PEEL)]
wo_peel = [v for v in visits if v not in with_peel]
avg = lambda vs: round(sum(v["_total"] for v in vs) / len(vs)) if vs else 0

DUR = {}
for b in (1, 2, 3):
    vs = [v for v in visits if v["_h"] and (v["_h"] >= 3 if b == 3 else abs(v["_h"] - b) < 0.5)]
    if vs:
        DUR[b] = {"n": len(vs), "check": avg(vs),
                  "per_hour": round(sum(v["_total"] for v in vs) / sum(v["_h"] for v in vs))}

day_slot = [v for v in visits if (hour_of(v.get("time_start")) or -1) in range(11, 17)]
night = [v for v in visits if (hour_of(v.get("time_start")) or -1) in (23, 0, 1, 2)]
gift = [v for v in visits if re.search(r"беспл|подар|бонус", (v.get("note") or "").lower())]
cert = [v for v in visits if re.search(r"сертификат", (v.get("note") or "").lower())]
big = [v for v in visits if v["_p"] and v["_p"] >= 4]

INSIGHT = {
    "dish_pct": round(len(with_dish) / len(visits) * 100, 1),
    "dish_check": avg(with_dish), "nodish_check": avg(wo_dish),
    "peel_check": avg(with_peel), "nopeel_check": avg(wo_peel),
    "peel_by_month": {M[mo]["name"]: M[mo]["attach"] for mo in MONTHS},
    "peel_pct_by_month": {M[mo]["name"]: round(100 * sum(
        1 for v in visits if v["_mo"] == mo and has(v, lambda i: classify(i.get("item"))[1] == PEEL)
    ) / max(1, M[mo]["visits"]), 1) for mo in MONTHS},
    "dur": DUR,
    "day_slot_n": len(day_slot),
    "day_slot_pct": round(len(day_slot) / sum(1 for v in visits if hour_of(v.get("time_start")) is not None) * 100, 1),
    "night_n": len(night), "night_rev": sum(v["_total"] for v in night), "night_check": avg(night),
    "gift_n": len(gift), "gift_hours": round(sum(v["_he"] for v in gift), 1),
    "gift_res_cost": round(sum(v["_pe"] for v in gift) * RESOURCE_PER_GUEST),
    "cert_n": len(cert), "cert_pct": round(len(cert) / len(visits) * 100, 1),
    "big_n": len(big), "big_check": avg(big),
    "best_cabin": max(CABINS, key=lambda c: CABINS[c]["per_hour"]),
}

# ═══════════════════════════════════════════════════════════════════════════
# 7. figures.json
# ═══════════════════════════════════════════════════════════════════════════
hourhist = collections.Counter(r["h"] for r in recs if r["h"] is not None)
cabhist = collections.Counter(r["cab"] for r in recs if r["cab"])
payhist = collections.Counter()
for r in recs:
    if r["pay"]:
        payhist[r["pay"]] += r["sum"]
wdhist = collections.Counter()
wdd = collections.defaultdict(set)
for r in recs:
    wdhist[r["wd"]] += r["sum"]
    wdd[r["wd"]].add(r["d"])

FIG = {
    "total": TOT,
    "months": [M[mo] for mo in MONTHS],
    "items": ITEMS,
    "cats": CATS,
    "cost_model": {
        "util_per_guest": round(UTIL_PER_GUEST, 1),
        "septic_per_guest": round(SEPTIC_PER_GUEST, 1),
        "res_per_guest": round(RESOURCE_PER_GUEST, 1),
        "cogs_food_pct": round(COGS_FOOD * 100, 1),
        "cogs_soft_pct": round(COGS_SOFT * 100, 1),
        "cogs_alc_pct": round(COGS_ALC * 100, 1),
        "cons_pct": CONS_MARGIN * 100,
        "cogs_nodet_pct": round(NODET_COGS * 100, 1),
        "venik_unit": VENIK_UNIT, "peel_cap": PEEL_CAP,
        "fixed_month": round(FIXED_MONTH),
        "fixed_parts": {"зарплата администратора": SALARY, "бухгалтер": ACCOUNTANT,
                        "налоги и отчисления": TAXES_M, "телефон": PHONE,
                        "электрик, газовщик, техничка": CONTRACTORS,
                        "моющие средства": CLEANING, "газ — техобслуживание (1/3 кв.)": round(GASTO / 3)},
        "one_off_aug": ONE_OFF_AUG,
        "one_off_parts": {"ЦОН — оформление": CON, "инвентарь, светильники, термометры": INVENTORY,
                          "вентиляторы для кабин": FANS, "остаток налога за I полугодие": TAX_H1,
                          "сертификаты": CERTS},
        "aug_cash_expenses": round(sum(i["amount"] or 0 for i in EXP["items"]), 2),
        "aug_sheet_revenue": EXP["meta"]["stated_totals"]["revenue"],
    },
    "hour_hist": dict(sorted(hourhist.items())),
    "cabin_hist": dict(sorted(cabhist.items())),
    "pay_hist": dict(payhist),
    "wd_rpd": {WD[k]: round(v / len(wdd[k])) for k, v in sorted(wdhist.items())},
    "wd_visits": {WD[k]: round(sum(1 for r in recs if r["wd"] == k) / len(wdd[k]), 1) for k in sorted(wdd)},
    "clients": CLIENTS,
    "cohort": COHORT,
    "cabins": CABINS,
    "insight": INSIGHT,
}
json.dump(FIG, open(os.path.join(HERE, "figures.json"), "w"), ensure_ascii=False, indent=1)

# ═══════════════════════════════════════════════════════════════════════════
print(f"визитов {TOT['visits']}, дней {TOT['days']}, выручка {TOT['revenue']:,}")
print(f"гостей ≈{TOT['guests']}, кабино-часов {TOT['hours']}")
print(f"валовая {TOT['gross']:,} ({TOT['gross_pct']}%), чистая {TOT['net']:,} ({TOT['net_pct']}%)")
print(f"\nставки: ресурсы {RESOURCE_PER_GUEST:.0f} ₸/гость "
      f"(свет+вода+газ {UTIL_PER_GUEST:.0f} + септик {SEPTIC_PER_GUEST:.0f}); "
      f"еда {COGS_FOOD*100:.1f}%, б/а {COGS_SOFT*100:.1f}%, пиво {COGS_ALC*100:.1f}%; "
      f"постоянные {FIXED_MONTH:,.0f} ₸/мес")
print(f"точка безубыточности: {TOT['breakeven_visits']} визитов в месяц "
      f"(вклад {TOT['cm_visit']:,} ₸ с визита против {FIXED_MONTH:,.0f} ₸ постоянных)")
print(f"\n{'мес':4}{'дн':>4}{'виз':>5}{'гост':>6}{'часы':>7}{'выручка':>10}"
      f"{'ресурсы':>9}{'₸/час':>7}{'товар':>9}{'мастер':>8}{'валовая':>10}{'%':>6}{'чистая':>10}{'%':>7}")
for mo in MONTHS:
    m = M[mo]
    print(f"{m['short']:4}{m['days']:>4}{m['visits']:>5}{m['guests']:>6}{m['hours']:>7}"
          f"{m['rev']:>10,}{m['res_cost']:>9,}{m['res_per_hour']:>7}{m['goods_cost']:>9,}"
          f"{m['peel_master']:>8,}{m['gross']:>10,}{m['gross_pct']:>6}{m['net']:>10,}{m['net_pct']:>7}"
          + ("  *неполный" if m["partial"] else ""))
print(f"\nсверка августа с листом расходов:")
a = M[AUG]
model = a["res_cost"] + a["goods_cost"] + a["peel_master"] + round(FIXED_MONTH)
print(f"  модель: ресурсы {a['res_cost']:,} + товар {a['goods_cost']:,} + мастер {a['peel_master']:,}"
      f" + постоянные {FIXED_MONTH:,.0f} = {model:,}")
print(f"  лист (касса, без разовых): {sum(i['amount'] or 0 for i in EXP['items']) - ONE_OFF_AUG:,.2f}")
print(f"  разница = пересчёт июльских счетов на августовскую загрузку")
print(f"  разовые август: {ONE_OFF_AUG:,} → чистая с разовыми: {a['net'] - ONE_OFF_AUG:,}")
