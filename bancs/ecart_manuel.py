# -*- coding: utf-8 -*-
"""Confronte un planning GENERE a la version CORRIGEE A LA MAIN.

Raison d'etre : l'optimalite demontree le 2026-08-01 porte sur la fonction de
cout du module, pas sur le jugement de l'utilisateur. Or celui-ci trouve
regulierement, a la main, une solution qu'il estime meilleure. La recherche
etant saturee — c'est prouve — l'ecart ne peut venir que de la fonction de cout.

Chaque correction manuelle est donc un contre-exemple etiquete : elle designe
une regle absente ou mal ponderee. Ce script isole laquelle.

    python ecart_manuel.py genere.html corrige.html

Les deux fichiers doivent etre des plannings du MEME jour, avec les memes
horaires de presence. Seules les affectations doivent differer.
"""
import sys, os, io, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SB = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(SB)
os.environ.setdefault('DATA_DIR', SB)
os.environ.setdefault('DB_NAME', "supermarche_dev.db")
sys.path.insert(1, PROJ)
sys.path.insert(0, SB)

import algo
import extraire

BASE = os.path.join(SB, "pristine.db")


def charger(chemin):
    grille = extraire.lire(chemin)
    grille, inconnus = extraire.noms_reels(grille, BASE)
    if inconnus:
        print(f"  ! noms non retrouves en base : {inconnus}")
    return grille


def matrice_de(grille, noms, nb_slots):
    """grille[nom][creneau] -> matrice[creneau][colonne]. POLY et None deviennent
    une case vide : ce sont des non-affectations, pas des taches."""
    M = [["" for _ in noms] for _ in range(nb_slots)]
    for x, nom in enumerate(noms):
        for i, case in enumerate(grille[nom][:nb_slots]):
            if case in (None, "POLY"):
                continue
            M[i][x] = case
    return M


def presence_de(grille, noms, nb_slots):
    return {nom: [grille[nom][i] is not None for i in range(nb_slots)] for nom in noms}


def mesures(M, slots, noms, presence):
    """Les criteres tels que l'utilisateur les lit, independamment du cout."""
    releves = 0
    couverture = {}
    for c in algo.ORDRE_CAISSES:
        suite, tenu = [], 0
        for i in range(len(slots)):
            qui = next((x for x in range(len(noms)) if M[i][x] == f"C{c}"), None)
            if qui is not None:
                tenu += 1
                if not suite or suite[-1] != qui:
                    suite.append(qui)
        releves += max(0, len(suite) - 1)
        couverture[c] = tenu

    courts = inoccupes = 0
    for x, nom in enumerate(noms):
        blocs, courant, longueur = [], None, 0
        for i in range(len(slots)):
            if M[i][x] == "PAUSE":
                continue
            n = algo._num_caisse(M[i][x])
            if n is not None and n == courant:
                longueur += 1
            else:
                if courant is not None:
                    blocs.append(longueur)
                courant, longueur = n, (1 if n is not None else 0)
            if presence[nom][i] and M[i][x] == "":
                inoccupes += 1
        if courant is not None:
            blocs.append(longueur)
        courts += sum(1 for l in blocs if l < algo.DUREE_MIN_CAISSE)

    return {
        "releves": releves,
        "postes_courts": courts,
        "creneaux_inoccupes": inoccupes,
        "C1+C2": couverture[1] + couverture[2],
        "C13+C14": couverture[13] + couverture[14],
        "C5+C6": couverture[5] + couverture[6],
        "caisses_du_fond": sum(v for k, v in couverture.items()
                               if k not in (1, 2, 13, 14, 5, 6)),
        "couverture_totale": sum(couverture.values()),
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    chemin_g, chemin_c = sys.argv[1], sys.argv[2]

    print(f"genere  : {os.path.basename(chemin_g)}")
    print(f"corrige : {os.path.basename(chemin_c)}\n")
    g, c = charger(chemin_g), charger(chemin_c)

    communs = [n for n in g if n in c]
    absents = set(g) ^ set(c)
    if absents:
        print(f"  ! presents dans un seul fichier, ignores : {sorted(absents)}\n")
    slots = [f"{9 + i // 4:02d}:{(i % 4) * 15:02d}" for i in range(44)]
    nb = len(slots)

    Mg, Mc = matrice_de(g, communs, nb), matrice_de(c, communs, nb)
    pres = presence_de(g, communs, nb)

    # --- les horaires doivent etre identiques, sinon on ne compare pas la meme chose
    presc = presence_de(c, communs, nb)
    ecarts_presence = [n for n in communs if pres[n] != presc[n]]
    if ecarts_presence:
        print(f"  ! ATTENTION : horaires de presence differents pour {ecarts_presence}")
        print("    La comparaison porte alors sur deux journees distinctes.\n")

    conn = sqlite3.connect(BASE)
    cache = {r[0]: dict(zip([d[0] for d in conn.execute("select * from employes limit 1").description], r))
             for r in conn.execute("select * from employes")}
    conn.close()
    map_emp = {n: i for i, n in enumerate(communs)}

    # --- ce qui a change ---
    diffs = [(i, x) for i in range(nb) for x in range(len(communs)) if Mg[i][x] != Mc[i][x]]
    print(f"{len(diffs)} cellule(s) modifiee(s) a la main\n")
    par_employe = {}
    for i, x in diffs:
        par_employe.setdefault(communs[x], []).append(
            (slots[i], Mg[i][x] or "-", Mc[i][x] or "-"))
    for nom, changements in sorted(par_employe.items()):
        d, f = changements[0][0], changements[-1][0]
        avant = sorted({a for _, a, _ in changements})
        apres = sorted({b for _, _, b in changements})
        print(f"  {nom:26s} {d}-{f}  {'/'.join(avant):12s} -> {'/'.join(apres)}")

    # --- les criteres metier ---
    mg, mc = mesures(Mg, slots, communs, pres), mesures(Mc, slots, communs, pres)
    print(f"\n{'critere':22s} {'genere':>8s} {'corrige':>8s} {'ecart':>8s}")
    print("-" * 50)
    for cle in mg:
        delta = mc[cle] - mg[cle]
        print(f"  {cle:20s} {mg[cle]:8d} {mc[cle]:8d} {delta:+8d}")

    # --- le verdict qui compte ---
    cg = algo.evaluer_planning(Mg, slots, communs, map_emp, pres, cache)
    cc = algo.evaluer_planning(Mc, slots, communs, map_emp, pres, cache)
    print(f"\ncout selon la fonction actuelle : genere {cg}, corrige {cc}")
    if cc > cg:
        print(f"\n  >>> La version corrigee est jugee PIRE de {cc - cg} points par la")
        print("      fonction de cout, alors qu'elle est meilleure en pratique.")
        print("      C'est donc bien la fonction de cout qui se trompe. Regarder")
        print("      dans le tableau ci-dessus quel critere s'ameliore : le poids")
        print("      correspondant dans POIDS est trop faible, ou la regle manque.")
    elif cc < cg:
        print(f"\n  >>> La version corrigee est jugee MEILLEURE de {cg - cc} points.")
        print("      La fonction de cout est donc d'accord avec vous : c'est la")
        print("      RECHERCHE qui n'a pas trouve cette solution. Verifier qu'aucune")
        print("      contrainte dure ne l'interdit (mitoyennes, handicap, bloc mini).")
    else:
        print("\n  >>> Cout identique : les deux plannings se valent pour la fonction")
        print("      de cout. Le critere qui vous fait preferer l'un des deux n'est")
        print("      pas represente du tout dans POIDS.")


if __name__ == "__main__":
    main()
