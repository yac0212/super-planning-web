# -*- coding: utf-8 -*-
"""Compare trois solveurs sur les memes journees reelles :
   glouton   = algo.py etapes 0-3, sans optimisation
   recuit    = algo.py complet, version 3.0 en production
   cpsat     = missions de algo.py + caisses par CP-SAT

Les missions (CLS, PAUSE) sont identiques dans les trois cas : on isole ainsi
l'effet du solveur sur l'affectation des caisses, qui est le sujet.
"""
import sys, os, shutil, sqlite3, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SB = os.path.dirname(os.path.abspath(__file__))
PROJ = r"C:\Users\ayach\.gemini\antigravity\scratch\planning_app"
os.environ['DATA_DIR'] = SB
sys.path.insert(1, PROJ)
sys.path.insert(0, SB)

import importlib
import database as db
import algo
# Le module de solveur est choisi par CPSAT_MODULE : cela permet de comparer
# plusieurs formulations sans les faire se marcher dessus.
cps = importlib.import_module(os.environ.get("CPSAT_MODULE", "solveur_cpsat"))
import suite as SU

NB_JOURS = int(os.environ.get("JOURS", "4"))
SECONDES = float(os.environ.get("CPSAT_SECONDES", "45"))
BUDGET = float(os.environ.get("CPSAT_BUDGET", "60"))
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


def presence_de(res, scen):
    from datetime import datetime
    pres = {}
    for n in res['employes_presents']:
        t = scen[n]
        pres[n] = []
        for s in res['slots']:
            h = datetime.strptime(s, "%H:%M")
            pres[n].append(any(
                a and b and datetime.strptime(a, "%H:%M") <= h < datetime.strptime(b, "%H:%M")
                for a, b in ((t['ms'], t['me']), (t['aes'], t['aee']))))
    return pres


def analyse(res, scen, cache):
    slots, noms, M = res['slots'], res['employes_presents'], res['matrice_planning']
    pres = presence_de(res, scen)
    cov = {k: 0 for k in ORDRE}
    gaspille = 0
    for i in range(len(slots)):
        occ, libres = set(), 0
        for c, n in enumerate(noms):
            k = SU.num_de(M[i][c])
            if k:
                occ.add(k); cov[k] += 1
            elif pres[n][i] and M[i][c] not in ("CLS", "PAUSE"):
                libres += 1
        gaspille += min(libres, len(ORDRE) - len(occ))
    ano, m = SU.verifier(res, cache, scen)
    return dict(gaspille=gaspille, cov=cov, rel=m['rel'], ano=len(ano),
                micro=m['micro'], ano_list=ano)


def gen(date, scen, n):
    shutil.copy(os.path.join(SB, "pristine.db"), os.path.join(SB, "supermarche_dev.db"))
    cache = {e['nom']: e for e in db.get_employes()}
    return algo.run_algo(date, scen, cache, essais_optim=n), cache


print(f"{NB_JOURS} journees reelles | CP-SAT {SECONDES} s, {cps.NB_FILS} fil\n")
entete = (f"{'date':12s} {'n':>3s} {'solveur':9s} {'gasp':>5s} {'relev':>6s} {'C1C2':>5s} "
          f"{'C13C14':>7s} {'C5C6':>5s} {'bas':>5s} {'<1h30':>6s} {'ANO':>4s} {'sec':>6s} {'statut':>10s}")
print(entete); print("-" * len(entete))

tot = {k: [0] * 8 for k in ("glouton", "recuit", "cpsat")}
anomalies = []
temps_cpsat = []

for date, scen in journees_reelles(NB_JOURS):
    resultats = {}
    res_g, cache = gen(date, scen, 0)
    if "error" in res_g:
        print(f"{date} ERREUR {res_g['error']}"); continue
    resultats["glouton"] = (res_g, 0.0, "-")

    res_r, _ = gen(date, scen, 60000)
    resultats["recuit"] = (res_r, algo.optimiser_planning.dernieres_stats['secondes'], "-")

    # missions du glouton, caisses remises a zero, puis CP-SAT
    figee = [[t if t in ("CLS", "PAUSE") else "" for t in ligne]
             for ligne in res_g['matrice_planning']]
    pres = presence_de(res_g, scen)
    t0 = time.time()
    M, infos = cps.resoudre(figee, res_g['slots'], res_g['employes_presents'],
                            pres, cache, temps_max=SECONDES, budget=BUDGET,
                            indice=res_g['matrice_planning'])
    dt = time.time() - t0
    ecart = ""
    if infos.get('cout') is not None and infos.get('borne') is not None:
        c0, b0 = infos['cout'], infos['borne']
        ecart = f"  cout={c0:.0f} borne={b0:.0f} ecart={abs(c0 - b0) / max(1, abs(c0)) * 100:.1f}%"
    print(f"   -> CP-SAT {infos['statut']} {infos['variables']} vars  "
          f"det={infos['temps_deterministe']}{ecart}"
          f"{'  COUPE PAR LE TEMPS' if infos['coupe_par_le_temps'] else ''}")
    temps_cpsat.append((infos['statut'], dt, infos.get('variables')))
    res_c = dict(res_g); res_c['matrice_planning'] = M
    resultats["cpsat"] = (res_c, dt, infos['statut'])

    for tag in ("glouton", "recuit", "cpsat"):
        res, sec, statut = resultats[tag]
        a = analyse(res, scen, cache)
        c = a['cov']
        vals = (a['gaspille'], a['rel'], c[1] + c[2], c[13] + c[14], c[5] + c[6],
                sum(v for k, v in c.items() if k not in (1, 2, 13, 14, 5, 6)),
                a['micro'], a['ano'])
        print(f"{date:12s} {len(scen):3d} {tag:9s} {vals[0]:5d} {vals[1]:6d} {vals[2]:5d} "
              f"{vals[3]:7d} {vals[4]:5d} {vals[5]:5d} {vals[6]:6d} {vals[7]:4d} "
              f"{sec:6.1f} {statut:>10s}")
        for j, v in enumerate(vals):
            tot[tag][j] += v
        if a['ano']:
            anomalies += [f"{date} [{tag}] {x}" for x in a['ano_list'][:4]]
    print()

libelles = ["gaspille", "releves", "C1C2", "C13C14", "C5C6", "bas", "<1h30", "anomalies"]
print("TOTAUX")
print(f"  {'':12s} {'glouton':>9s} {'recuit':>9s} {'cpsat':>9s}")
for j, lib in enumerate(libelles):
    print(f"  {lib:12s} {tot['glouton'][j]:9d} {tot['recuit'][j]:9d} {tot['cpsat'][j]:9d}")

print("\nCP-SAT :", ", ".join(f"{s} {d:.1f}s" for s, d, _ in temps_cpsat))
if temps_cpsat:
    print("variables :", temps_cpsat[0][2])
if anomalies:
    print("\nANOMALIES :")
    for x in anomalies[:20]:
        print("  ", x)
