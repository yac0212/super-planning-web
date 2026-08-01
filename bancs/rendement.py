# -*- coding: utf-8 -*-
"""Ou part le budget d'essais ? On compte les appels a evaluer_planning : il n'y
en a un que lorsque le mouvement tire a produit une proposition valide. Le reste
des essais est brule sur des mouvements qui retournent None."""
import sys, os, shutil, sqlite3
SB = os.path.dirname(os.path.abspath(__file__))
PROJ = r"C:\Users\ayach\.gemini\antigravity\scratch\planning_app"
os.environ['DATA_DIR'] = SB
sys.path.insert(1, PROJ)
sys.path.insert(0, SB)

import database as db
import algo

compteur = {"n": 0}
_vrai = algo.evaluer_planning


def espion(*a, **k):
    compteur["n"] += 1
    return _vrai(*a, **k)


algo.evaluer_planning = espion

conn = sqlite3.connect(os.path.join(SB, "pristine.db"))
dates = [r[0] for r in conn.execute(
    "select date_str, count(*) c from sauvegarde_historique "
    "group by date_str having c >= 12 order by c desc")][:4]
jours = []
for d in dates:
    scen = {}
    for nom, ms, me, aes, aee in conn.execute(
            "select nom, ms, me, aes, aee from sauvegarde_historique where date_str=?", (d,)):
        scen[nom] = {"ms": ms or "", "me": me or "", "aes": aes or "", "aee": aee or ""}
    jours.append((d, scen))
conn.close()

N = 60000
print(f"budget = {N} essais par journee\n")
print(f"{'date':12s} {'propose':>9s} {'%util':>7s} {'accepte':>8s} {'%acc/prop':>10s}")
print("-" * 50)
for date, scen in jours:
    compteur["n"] = 0
    shutil.copy(os.path.join(SB, "pristine.db"), os.path.join(SB, "supermarche_dev.db"))
    cache = {e['nom']: e for e in db.get_employes()}
    algo.run_algo(date, scen, cache, essais_optim=N)
    st = algo.optimiser_planning.dernieres_stats
    prop = compteur["n"] - 2          # les 2 evaluations de stats
    util = 100.0 * prop / st['essais']
    accprop = 100.0 * st['acceptes'] / prop if prop else 0
    print(f"{date:12s} {prop:9d} {util:7.1f} {st['acceptes']:8d} {accprop:10.1f}")
