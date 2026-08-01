# -*- coding: utf-8 -*-
"""Combien reste-t-il reellement a gagner ?

On reduit l'instance jusqu'a ce que CP-SAT prouve l'optimalite, puis on compare
l'optimum PROUVE au resultat du glouton et du recuit sur la meme instance.

Si l'optimum est proche du glouton, il n'y a rien a gagner et aucun solveur au
monde n'y changera quoi que ce soit. S'il est nettement meilleur, le probleme
est la formulation ou le moteur, et l'investissement se justifie.
"""
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
from datetime import datetime
# suite.py n'est volontairement PAS importe : il execute ses 11 scenarios des
# l'import, ce qui coute une minute et n'apporte rien ici.

# Fenetres testees, de la plus petite a la plus grande. On s'arrete de reduire
# des qu'une taille se resout a l'optimum prouve.
FENETRES = [(0, 12), (0, 20), (0, 28), (0, 44)]
TEMPS = float(os.environ.get("PLAFOND_SECONDES", "300"))


def journee(rang=0):
    conn = sqlite3.connect(os.path.join(SB, "pristine.db"))
    d = [r[0] for r in conn.execute(
        "select date_str, count(*) c from sauvegarde_historique "
        "group by date_str having c >= 12 order by c desc")][rang]
    scen = {}
    for nom, ms, me, aes, aee in conn.execute(
            "select nom, ms, me, aes, aee from sauvegarde_historique where date_str=?", (d,)):
        scen[nom] = {"ms": ms or "", "me": me or "", "aes": aes or "", "aee": aee or ""}
    conn.close()
    return d, scen


def presence_de(slots, noms, scen):
    pres = {}
    for n in noms:
        t = scen[n]
        pres[n] = [any(a and b and datetime.strptime(a, "%H:%M")
                       <= datetime.strptime(s, "%H:%M") < datetime.strptime(b, "%H:%M")
                       for a, b in ((t['ms'], t['me']), (t['aes'], t['aee'])))
                   for s in slots]
    return pres


def nb_releves(M, slots, noms):
    """Titulaires successifs sur chaque caisse, pauses traversees."""
    total = 0
    for c in algo.ORDRE_CAISSES:
        suite = []
        for i in range(len(slots)):
            qui = next((x for x in range(len(noms)) if M[i][x] == f"C{c}"), None)
            if qui is not None and (not suite or suite[-1] != qui):
                suite.append(qui)
        total += max(0, len(suite) - 1)
    return total


date, scen = journee()
shutil.copy(os.path.join(SB, "pristine.db"), os.path.join(SB, "supermarche_dev.db"))
cache = {e['nom']: e for e in db.get_employes()}
complet = algo.run_algo(date, scen, cache, essais_optim=0)
noms = complet['employes_presents']

print(f"journee {date}, {len(noms)} employes | limite {TEMPS} s par instance\n")
entete = f"{'fenetre':16s} {'creneaux':>9s} {'glouton':>8s} {'cpsat':>7s} {'statut':>10s} {'sec':>7s} {'ecart':>7s}"
print(entete); print("-" * len(entete))

for debut_i, fin_i in FENETRES:
    slots = complet['slots'][debut_i:fin_i]
    M_glouton = [ligne[:] for ligne in complet['matrice_planning'][debut_i:fin_i]]
    figee = [[t if t in ("CLS", "PAUSE") else "" for t in ligne] for ligne in M_glouton]
    pres = presence_de(slots, noms, scen)

    t0 = time.time()
    M, infos = cps.resoudre(figee, slots, noms, pres, cache,
                            temps_max=TEMPS, budget=1e9,
                            indice=M_glouton)
    dt = time.time() - t0

    rg = nb_releves(M_glouton, slots, noms)
    rc = nb_releves(M, slots, noms)
    ecart = ""
    if infos.get('cout') is not None and infos.get('borne') is not None:
        ecart = f"{abs(infos['cout'] - infos['borne']) / max(1, abs(infos['cout'])) * 100:.1f}%"
    libelle = f"{slots[0]}-{slots[-1]}"
    print(f"{libelle:16s} {len(slots):9d} {rg:8d} {rc:7d} {infos['statut']:>10s} "
          f"{dt:7.1f} {ecart:>7s}")
    sys.stdout.flush()
    if infos['statut'] == "OPTIMAL":
        print(f"\n  -> OPTIMUM PROUVE sur cette fenetre : {rc} releves contre {rg} au glouton")
        if rc >= rg:
            print("     le glouton est deja optimal ou tres proche : rien a gagner ici")
        else:
            print(f"     marge reelle : {rg - rc} releves ({(rg - rc) / max(1, rg) * 100:.0f} %)")
