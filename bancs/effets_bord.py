# -*- coding: utf-8 -*-
"""run_algo ECRIT en base pendant qu'il calcule (compteur_missions,
historique_fermeture). Deux generations successives du meme jour partent donc
d'un etat different. Ce test ne remet PAS la base a zero entre les deux."""
import sys, os, shutil, sqlite3, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SB = os.path.dirname(os.path.abspath(__file__))
PROJ = r"C:\Users\ayach\.gemini\antigravity\scratch\planning_app"
os.environ['DATA_DIR'] = SB
sys.path.insert(1, PROJ)
sys.path.insert(0, SB)

import database as db
import algo

shutil.copy(os.path.join(SB, "pristine.db"), os.path.join(SB, "supermarche_dev.db"))
conn = sqlite3.connect(os.path.join(SB, "pristine.db"))
date = [r[0] for r in conn.execute(
    "select date_str, count(*) c from sauvegarde_historique "
    "group by date_str having c >= 12 order by c desc")][0]
scen = {}
for nom, ms, me, aes, aee in conn.execute(
        "select nom, ms, me, aes, aee from sauvegarde_historique where date_str=?", (date,)):
    scen[nom] = {"ms": ms or "", "me": me or "", "aes": aes or "", "aee": aee or ""}
conn.close()

runs = []
for k in range(3):
    cache = {e['nom']: e for e in db.get_employes()}
    r = algo.run_algo(date, scen, cache, essais_optim=20000)
    runs.append(r)
    print(f"run {k+1} : compteur de 3 employes ->",
          {n: db.get_mission_score(n) for n in list(scen)[:3]})

print(f"\njournee {date}, {len(scen)} employes, base NON reinitialisee entre les runs")
for k in (1, 2):
    a, b = runs[0]['matrice_planning'], runs[k]['matrice_planning']
    diff = sum(1 for i in range(len(a)) for x in range(len(a[0])) if a[i][x] != b[i][x])
    pauses_a = sum(1 for i in range(len(a)) for x in range(len(a[0])) if a[i][x] == "PAUSE")
    pauses_b = sum(1 for i in range(len(b)) for x in range(len(b[0])) if b[i][x] == "PAUSE")
    print(f"  run 1 vs run {k+1} : {diff} cellules differentes   "
          f"(creneaux PAUSE {pauses_a} vs {pauses_b})")
