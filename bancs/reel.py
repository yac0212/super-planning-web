# -*- coding: utf-8 -*-
"""Rejoue les journees REELLEMENT saisies (table sauvegarde_historique) et
compare le glouton seul a l'optimisation globale. Les horaires y sont bien plus
irreguliers que dans les scenarios synthetiques : c'est la que les defauts
signales par l'utilisateur apparaissent."""
import sys, os, shutil, sqlite3
SB = os.path.dirname(os.path.abspath(__file__))
PROJ = r"C:\Users\ayach\.gemini\antigravity\scratch\planning_app"
os.environ['DATA_DIR'] = SB
sys.path.insert(1, PROJ)
sys.path.insert(0, SB)

import database as db
import algo
import suite as SU

ESSAIS = int(os.environ.get("ESSAIS", "60000"))
NB_JOURS = int(os.environ.get("JOURS", "12"))
ORDRE = algo.ORDRE_CAISSES


def journees_reelles(limite):
    conn = sqlite3.connect(os.path.join(SB, "pristine.db"))
    dates = [r[0] for r in conn.execute(
        "select date_str, count(*) c from sauvegarde_historique "
        "group by date_str having c >= 12 order by c desc")][:limite]
    jours = []
    for d in dates:
        scen = {}
        for nom, ms, me, aes, aee in conn.execute(
                "select nom, ms, me, aes, aee from sauvegarde_historique where date_str=?", (d,)):
            scen[nom] = {"ms": ms or "", "me": me or "", "aes": aes or "", "aee": aee or ""}
        jours.append((d, scen))
    conn.close()
    return jours


def analyse(res, scen, cache):
    from datetime import datetime
    slots, noms, M = res['slots'], res['employes_presents'], res['matrice_planning']
    pres = {}
    for n in noms:
        t = scen[n]
        pres[n] = []
        for s in slots:
            h = datetime.strptime(s, "%H:%M")
            pres[n].append(any(
                a and b and datetime.strptime(a, "%H:%M") <= h < datetime.strptime(b, "%H:%M")
                for a, b in ((t['ms'], t['me']), (t['aes'], t['aee']))))
    cov = {k: 0 for k in ORDRE}
    gaspille = 0
    for i in range(len(slots)):
        occ, libres = set(), 0
        for c, n in enumerate(noms):
            k = SU.num_de(M[i][c])
            if k:
                occ.add(k)
                cov[k] += 1
            elif pres[n][i] and M[i][c] not in ("CLS", "PAUSE"):
                libres += 1
        gaspille += min(libres, len(ORDRE) - len(occ))
    ano, m = SU.verifier(res, cache, scen)
    return dict(gaspille=gaspille, cov=cov, rel=m['rel'], ano=len(ano),
                micro=m['micro'], mj=m['mj'], ano_list=ano)


def gen(date, scen, n):
    shutil.copy(os.path.join(SB, "pristine.db"), os.path.join(SB, "supermarche_dev.db"))
    cache = {e['nom']: e for e in db.get_employes()}
    return algo.run_algo(date, scen, cache, essais_optim=n), cache


jours = journees_reelles(NB_JOURS)
print(f"{len(jours)} journees reelles rejouees, {ESSAIS} essais d'optimisation\n")
print(f"{'date':12s} {'n':>3s} {'variante':9s} {'gasp':>5s} {'relev':>6s} {'C1C2':>5s} "
      f"{'C13C14':>7s} {'C5C6':>5s} {'bas':>5s} {'<1h30':>6s} {'ANO':>4s}")
print("-" * 82)

tot = {"glouton": [0] * 8, "optimise": [0] * 8}
anomalies_vues = []
for date, scen in jours:
    for tag, n in (("glouton", 0), ("optimise", ESSAIS)):
        res, cache = gen(date, scen, n)
        if "error" in res:
            print(f"{date:12s} ERREUR {res['error']}")
            break
        a = analyse(res, scen, cache)
        c = a['cov']
        vals = (a['gaspille'], a['rel'], c[1] + c[2], c[13] + c[14], c[5] + c[6],
                sum(v for k, v in c.items() if k not in (1, 2, 13, 14, 5, 6)),
                a['micro'], a['ano'])
        print(f"{date:12s} {len(scen):3d} {tag:9s} {vals[0]:5d} {vals[1]:6d} {vals[2]:5d} "
              f"{vals[3]:7d} {vals[4]:5d} {vals[5]:5d} {vals[6]:6d} {vals[7]:4d}")
        for j, v in enumerate(vals):
            tot[tag][j] += v
        if a['ano']:
            anomalies_vues += [f"{date} [{tag}] {x}" for x in a['ano_list'][:3]]
    print()

libelles = ["gaspille", "releves", "C1C2", "C13C14", "C5C6", "bas", "<1h30", "anomalies"]
print("TOTAUX")
for j, lib in enumerate(libelles):
    g, o = tot['glouton'][j], tot['optimise'][j]
    fleche = "" if g == o else ("  ameliore" if (o < g) == (j in (0, 1, 6, 7)) else "  DEGRADE")
    print(f"  {lib:12s} glouton={g:6d}   optimise={o:6d}{fleche}")

if anomalies_vues:
    print("\nANOMALIES :")
    for x in anomalies_vues[:15]:
        print("  ", x)
