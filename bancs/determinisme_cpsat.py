# -*- coding: utf-8 -*-
"""Le meme jour resolu plusieurs fois doit rendre exactement le meme planning.
On compare les matrices cellule par cellule, sous differents reglages de budget."""
import sys, os, shutil, sqlite3, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SB = os.path.dirname(os.path.abspath(__file__))
PROJ = r"C:\Users\ayach\.gemini\antigravity\scratch\planning_app"
os.environ['DATA_DIR'] = SB
sys.path.insert(1, PROJ)
sys.path.insert(0, SB)

import database as db
import algo
import solveur_cpsat as cps
from ortools.sat.python import cp_model

conn = sqlite3.connect(os.path.join(SB, "pristine.db"))
date = [r[0] for r in conn.execute(
    "select date_str, count(*) c from sauvegarde_historique "
    "group by date_str having c >= 12 order by c desc")][0]
scen = {}
for nom, ms, me, aes, aee in conn.execute(
        "select nom, ms, me, aes, aee from sauvegarde_historique where date_str=?", (date,)):
    scen[nom] = {"ms": ms or "", "me": me or "", "aes": aes or "", "aee": aee or ""}
conn.close()

shutil.copy(os.path.join(SB, "pristine.db"), os.path.join(SB, "supermarche_dev.db"))
cache = {e['nom']: e for e in db.get_employes()}
res_g = algo.run_algo(date, scen, cache, essais_optim=0)
figee = [[t if t in ("CLS", "PAUSE") else "" for t in ligne]
         for ligne in res_g['matrice_planning']]

from datetime import datetime
pres = {}
for n in res_g['employes_presents']:
    t = scen[n]
    pres[n] = [any(a and b and datetime.strptime(a, "%H:%M") <= datetime.strptime(s, "%H:%M")
                   < datetime.strptime(b, "%H:%M")
                   for a, b in ((t['ms'], t['me']), (t['aes'], t['aee'])))
               for s in res_g['slots']]

REGLAGES = [
    ("det=20  mur=300", 20, 300),
    ("det=40  mur=300", 40, 300),
    ("det=80  mur=300", 80, 300),
    ("det=300 mur=20 ", 300, 20),   # c'est le mur qui coupe : non reproductible
]

print(f"journee {date}, {len(scen)} employes, {cps.NB_FILS} fils\n")
for libelle, budget, mur in REGLAGES:
    matrices, details = [], []
    for k in range(3):
        t0 = time.time()
        M, infos = cps.resoudre(figee, res_g['slots'], res_g['employes_presents'],
                                pres, cache, temps_max=mur, budget=budget,
                                indice=res_g['matrice_planning'])
        matrices.append(M)
        details.append((infos['cout'], infos['temps_deterministe'], round(time.time() - t0, 1),
                        infos['statut']))
    diffs = [sum(1 for i in range(len(matrices[0])) for x in range(len(matrices[0][0]))
                 if matrices[0][i][x] != m[i][x]) for m in matrices[1:]]
    couts = sorted({d[0] for d in details})
    print(f"{libelle} : diff {diffs}  couts {[int(c) for c in couts]}  "
          f"det {[d[1] for d in details]}  sec {[d[2] for d in details]}  {details[0][3]}")
