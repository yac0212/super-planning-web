# -*- coding: utf-8 -*-
"""Repere, parmi les plannings REELLEMENT sauvegardes, ceux qui different de ce
que l'algorithme actuel produirait a partir des memes horaires de presence.

Chaque case d'un planning genere est modifiable directement dans le navigateur
(contenteditable), et "Enregistrer en ligne" ecrase le fichier original avec la
version corrigee. Un seul fichier existe par date : impossible de savoir depuis
le disque seul si son contenu est la sortie brute de l'algorithme ou une
correction manuelle.

Ce script ne tranche donc PAS automatiquement. Il isole les journees ou un
ecart existe et les classe par importance, pour que l'utilisateur confirme
lesquelles sont de vraies corrections.

    python trouver_corrections.py

Sortie : un tableau trie par nombre de cellules differentes, decroissant.
"""
import sys, os, io, shutil, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SB = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(SB)
os.environ.setdefault('DATA_DIR', SB)
os.environ.setdefault('DB_NAME', "supermarche_dev.db")
sys.path.insert(1, PROJ)
sys.path.insert(0, SB)

import extraire
import algo
import database as db

BASE = os.path.join(SB, "pristine.db")
PLANNINGS_DIR = os.path.join(PROJ, "static", "plannings")


def date_iso_vers_saisie(nom_fichier):
    """Planning_A4_04-08-2026.html -> 04/08/2026"""
    base = nom_fichier.replace("Planning_A4_", "").replace(".html", "")
    j, m, a = base.split("-")
    return f"{j}/{m}/{a}"


def presence_saisie(date_saisie, conn):
    lignes = conn.execute(
        "SELECT nom, ms, me, aes, aee FROM sauvegarde_historique WHERE date_str=?",
        (date_saisie,)).fetchall()
    if not lignes:
        return None
    return {nom: {"ms": ms or "", "me": me or "", "aes": aes or "", "aee": aee or ""}
            for nom, ms, me, aes, aee in lignes}


def matrice_de_grille(grille, noms, nb_slots):
    M = [["" for _ in noms] for _ in range(nb_slots)]
    for x, nom in enumerate(noms):
        for i, case in enumerate(grille.get(nom, [])[:nb_slots]):
            if case in (None, "POLY"):
                continue
            M[i][x] = case
    return M


def main():
    if not os.path.isdir(PLANNINGS_DIR):
        print(f"introuvable : {PLANNINGS_DIR}")
        return

    shutil.copy(BASE, os.path.join(SB, "supermarche_dev.db"))
    conn_hist = sqlite3.connect(BASE)
    cache = {e['nom']: e for e in db.get_employes()}

    resultats = []
    fichiers = sorted(f for f in os.listdir(PLANNINGS_DIR) if f.endswith(".html"))
    print(f"{len(fichiers)} planning(s) sauvegarde(s) trouve(s)\n")

    for nom_fichier in fichiers:
        date_saisie = date_iso_vers_saisie(nom_fichier)
        scen = presence_saisie(date_saisie, conn_hist)
        if scen is None:
            print(f"  {nom_fichier:34s} pas d'horaires en base pour cette date, ignore")
            continue

        res = algo.run_algo(date_saisie, scen, cache, essais_optim=60000)
        if "error" in res:
            print(f"  {nom_fichier:34s} erreur de generation : {res['error']}")
            continue

        chemin = os.path.join(PLANNINGS_DIR, nom_fichier)
        grille_sauvee = extraire.lire(chemin)
        grille_sauvee, inconnus = extraire.noms_reels(grille_sauvee, BASE)

        communs = [n for n in res['employes_presents'] if n in grille_sauvee]
        if not communs:
            print(f"  {nom_fichier:34s} aucun nom en commun, ignore"
                  + (f" (non retrouves : {inconnus})" if inconnus else ""))
            continue

        slots = res['slots']
        nb = len(slots)
        M_genere = res['matrice_planning']
        M_sauve = matrice_de_grille(grille_sauvee, res['employes_presents'], nb)

        idx = {n: i for i, n in enumerate(res['employes_presents'])}
        diffs = sum(1 for i in range(nb) for n in communs
                    if M_genere[i][idx[n]] != M_sauve[i][idx[n]])

        resultats.append((diffs, nom_fichier, date_saisie, len(communs)))

    conn_hist.close()

    print(f"\n{'fichier':34s} {'date':11s} {'employes':>9s} {'cellules diff':>14s}")
    print("-" * 72)
    for diffs, nom_fichier, date_saisie, n in sorted(resultats, reverse=True):
        marque = "  <-- a verifier" if diffs > 0 else "  identique"
        print(f"{nom_fichier:34s} {date_saisie:11s} {n:9d} {diffs:14d}{marque}")

    avec_ecart = [r for r in resultats if r[0] > 0]
    print(f"\n{len(avec_ecart)} journee(s) sur {len(resultats)} different du planning actuel.")
    print("Un ecart signifie l'UNE de ces deux choses, indiscernables depuis le disque :")
    print("  1. le fichier a ete corrige a la main puis re-enregistre")
    print("  2. le fichier a ete genere par une version anterieure de l'algorithme")
    print("\nPour les journees les plus recentes (generees apres la mise a jour du")
    print("2026-08-01), un ecart est plus probablement une vraie correction manuelle.")
    print("Confirmer au cas par cas avec : python ecart_manuel.py <fichier_genere> "
          f"{PLANNINGS_DIR}\\<fichier>")


if __name__ == "__main__":
    main()
