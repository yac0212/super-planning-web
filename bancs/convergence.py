# -*- coding: utf-8 -*-
"""Mesure la CONVERGENCE du recuit : le budget d'essais actuel suffit-il ?
Rejoue les journees reelles avec des budgets croissants et compare le cout final.
Si le cout continue de baisser au-dela de 60000, le solveur est sous-dimensionne.
Si le garde-fou des 30 s coupe, le determinisme annonce est faux."""
import sys, os, shutil, sqlite3
SB = os.path.dirname(os.path.abspath(__file__))
PROJ = r"C:\Users\ayach\.gemini\antigravity\scratch\planning_app"
os.environ['DATA_DIR'] = SB
sys.path.insert(1, PROJ)
sys.path.insert(0, SB)

import database as db
import algo

BUDGETS = [0, 5000, 20000, 60000, 200000]
NB_JOURS = int(os.environ.get("JOURS", "4"))


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


def gen(date, scen, n):
    shutil.copy(os.path.join(SB, "pristine.db"), os.path.join(SB, "supermarche_dev.db"))
    cache = {e['nom']: e for e in db.get_employes()}
    return algo.run_algo(date, scen, cache, essais_optim=n)


jours = journees_reelles(NB_JOURS)
print(f"{len(jours)} journees reelles | budgets {BUDGETS}\n")
print(f"{'date':12s} {'n':>3s} {'budget':>8s} {'cout':>9s} {'gain%':>7s} {'sec':>6s} "
      f"{'accept%':>8s} {'coupe':>6s}")
print("-" * 68)

for date, scen in jours:
    ref = None
    for b in BUDGETS:
        gen(date, scen, b)
        st = getattr(algo.optimiser_planning, "dernieres_stats", None)
        if b == 0 or st is None:
            # budget 0 : pas d'optimisation, on relit le cout de depart au budget suivant
            print(f"{date:12s} {len(scen):3d} {b:8d} {'(glouton)':>9s}")
            continue
        if ref is None:
            ref = st['cout_depart']
        gain = 100.0 * (ref - st['cout_final']) / abs(ref) if ref else 0.0
        acc = 100.0 * st['acceptes'] / st['essais'] if st['essais'] else 0.0
        print(f"{date:12s} {len(scen):3d} {b:8d} {st['cout_final']:9d} {gain:7.1f} "
              f"{st['secondes']:6.1f} {acc:8.1f} "
              f"{'OUI' if st['interrompu_par_le_temps'] else '-':>6s}")
    print(f"{'':12s} {'':3s} {'depart':>8s} {ref:9d}\n")
