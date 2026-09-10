#!/usr/bin/env python3
"""Подставляет цифры из figures.json в блоки данных index.html и months.html.
Текстовые пояснения правятся руками — здесь только JS-массивы."""
import json, re, os

HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "figures.json")))
M = {m["k"]: m for m in F["months"]}
KS = list(M)
T = F["total"]
C = F["cost_model"]
CL = F["clients"]


def js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def replace_block(src, start_marker, text, end=";"):
    """Заменяет `start_marker ... end` (по балансу скобок) на text."""
    i = src.index(start_marker)
    j = i + len(start_marker)
    depth, opener = 0, None
    while j < len(src):
        ch = src[j]
        if ch in "[{":
            depth += 1
            opener = opener or ch
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                j += 1
                break
        j += 1
    while src[j] not in ";\n":
        j += 1
    return src[:i] + text + src[j:]


# ─────────────────────────────────────────────────────────── index.html ──
p = os.path.join(HERE, "index.html")
s = open(p).read()

PPL = [{"m": M[k]["name"] + (" *" if M[k]["partial"] else ""),
        "v": M[k]["visits"],
        "rec": M[k].get("rec_n", 0),
        "avg": M[k]["ppl_avg"],
        "est": M[k]["guests"]} for k in KS]
s = replace_block(s, "const PPL=", "const PPL=" + js(PPL))

COH = [{"m": c["m"], "n": c["n"], "r": c["r"], "d": c["days"]} for c in F["cohort"]]
s = replace_block(s, "const COH=", "const COH=" + js(COH))

wf = [
    {"l": "Выручка от гостей", "v": T["revenue"], "c": "--s1",
     "tip": "Все деньги, полученные от гостей за 169 рабочих дней, уже за вычетом скидок по сертификатам"},
    {"l": "− газ, вода, свет, септик", "v": T["res_cost"], "c": "--s2",
     "tip": f"{C['res_per_guest']:.0f} ₸ на гостя × {T['guests']} гостей. Ставка выведена из июльских счетов и августовского платежа за септик"},
    {"l": "− закупка еды и напитков", "v": T["goods_cost"], "c": "--s2",
     "tip": f"Еда и чай {C['cogs_food_pct']}% от выручки позиции, б/а напитки {C['cogs_soft_pct']}%, пиво {C['cogs_alc_pct']}%, веник 1800 ₸/шт, мочалки и скрабы 50%"},
    {"l": "− доля мастера (пилинг)", "v": T["peel_master"], "c": "--s2",
     "tip": "Всё, что стоило дороже 2000 ₸ за сеанс, уходило мастеру. С мая пилинг стоит ровно 2000 ₸ — доля мастера обнулилась"},
    {"l": "= валовая прибыль", "v": T["gross"], "c": "--s4",
     "tip": f"{T['gross_pct']}% от выручки. Это ещё не ваши деньги — дальше постоянные расходы"},
    {"l": "− зарплаты, налоги, обслуживание", "v": T["fixed"], "c": "--s2",
     "tip": f"{C['fixed_month']:,} ₸ в месяц: администратор, бухгалтер, налоги, телефон, электрик с газовщиком и техничкой, моющие. По августовскому листу расходов".replace(",", " ")},
    {"l": "= чистая прибыль", "v": T["net"], "c": "--good",
     "tip": f"{T['net_pct']}% от выручки. Без разовых трат августа (ЦОН, инвентарь) — их {C['one_off_aug']:,} ₸, с ними остаётся {T['net_after_oneoff']:,} ₸".replace(",", " ")},
]
s = replace_block(s, "const wf=", "const wf=" + js(wf))

items = [{"name": i["n"], "rev": i["r"], "mar": i["p"]}
         for i in sorted(F["items"], key=lambda i: -i["p"])[:20]]
s = replace_block(s, "const items=", "const items=" + js(items))

HC = {int(k): v for k, v in F["hour_hist"].items()}
s = replace_block(s, "const HC=", "const HC=" + js(HC))

cab = sorted(F["cabins"].items(), key=lambda kv: -kv[1]["visits"])
cab = [c for c in cab if c[1]["visits"] >= 3]
cabjs = []
for num, a in cab:
    vip = a["per_hour"] > 10000
    tip = f"{a['hours']:.0f} ч работы, {a['rev']:,} ₸ выручки, {a['per_hour']:,} ₸ за час".replace(",", " ")
    cabjs.append("{l:'Кабина %s%s', v:%d%s, tip:'%s'}" %
                 (num, " (VIP)" if vip else "", a["visits"],
                  ", c:css('--s7')" if vip else "", tip))
s = replace_block(s, "bars('cabin-bars',", "bars('cabin-bars',[\n " + ",\n ".join(cabjs) + "\n], v=>v+' визитов')")

PAYN = {"kaspi": "Kaspi", "mixed": "Смешанная оплата", "cash": "Наличные"}
pay = [{"l": PAYN[k], "v": v} for k, v in sorted(F["pay_hist"].items(), key=lambda kv: -kv[1])]
paysrc = "bars('pay-bars',[\n " + ",\n ".join(
    "{l:'%s', v:%d, c:css('--s7')}" % (x["l"], x["v"]) for x in pay) + "\n], v=>n(v)+' ₸')"
s = replace_block(s, "bars('pay-bars',", paysrc)

IT = {"months": [{"k": m["k"], "name": m["name"], "short": m["short"], "days": m["days"],
                  "visits": m["visits"], "rev": m["rev"], "profit": m["gross"],
                  "mpct": m["gross_pct"], "net": m["net"], "npct": m["net_pct"],
                  "aov": m["aov"], "ppd": m["ppd"], "hours": m["hours"],
                  "attach": m["attach"], "wd_rpd": m["wd_rpd"], "we_rpd": m["we_rpd"],
                  "disc": m["disc"], "guests": m["guests"], "rph": m["res_per_hour"],
                  "partial": m["partial"]} for m in F["months"]],
      "items": F["items"], "cats": F["cats"]}
s = replace_block(s, "const IT = ", "const IT = " + js(IT))
open(p, "w").write(s)
print("index.html patched")

# ────────────────────────────────────────────────────────── months.html ──
p = os.path.join(HERE, "months.html")
s = open(p).read()
MM = {m["k"]: {"days": m["days"], "visits": m["visits"], "revenue": m["rev"],
               "margin": m["gross"], "margin_pct": m["gross_pct"],
               "net": m["net"], "net_pct": m["net_pct"], "aov": m["aov"],
               "ppd": m["ppd"], "cab_hours": m["hours"], "attach": m["attach"],
               "wd_rpd": m["wd_rpd"], "we_rpd": m["we_rpd"], "guests": m["guests"],
               "rph": m["res_per_hour"], "partial": m["partial"]} for m in F["months"]}
s = replace_block(s, "const M = ", "const M = " + js(MM))
s = re.sub(r'const LBL=\{[^}]*\};',
           "const LBL=" + js({m["k"]: m["short"] for m in F["months"]}) + ";", s)
s = re.sub(r'const FULL=\{[^}]*\};',
           "const FULL=" + js({m["k"]: m["name"] for m in F["months"]}) + ";", s)
s = replace_block(s, "const IT = ", "const IT = " + js(IT))
open(p, "w").write(s)
print("months.html patched")
