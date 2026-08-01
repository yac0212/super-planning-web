# -*- coding: utf-8 -*-
"""Reconstitue les horaires saisis a partir d'un planning genere.
Dans la grille, bg-ABS = absent ; toute autre case = present. La reconstruction
est donc EXACTE, contrairement a une lecture de capture d'ecran."""
import re, sys, os, json

PLANNINGS = r"C:\Users\ayach\.gemini\antigravity\scratch\planning_app\static\plannings"
SLOTS = [f"{9 + i // 4:02d}:{(i % 4) * 15:02d}" for i in range(44)]


def lire(chemin):
    html = open(chemin, encoding="utf-8").read()
    corps = html[html.find("<tbody"):]
    # le fichier telecharge par le navigateur normalise les apostrophes en
    # guillemets doubles : on accepte les deux
    lignes = re.findall(r"<tr><td class=[\"']name[\"']>(.*?)</td>(.*?)</tr>", corps, re.S)
    grille = {}
    for nom, reste in lignes:
        blocs = re.findall(r"<div class=[\"']sub-block bg-([A-Z0-9_]+)[\"'][^>]*>(.*?)</div>", reste, re.S)
        cases = []
        for classe, contenu in blocs:
            # Une cellule retapee a la main dans le navigateur conserve la mise
            # en forme : <span style="font-size: 9px;">C2</span>. Sans ce
            # nettoyage, le libelle lu vaut le HTML complet et l'affectation
            # passe pour inexistante — la couverture mesuree devient fausse.
            texte = re.sub(r"<[^>]+>", "", contenu)
            texte = texte.replace("&nbsp;", " ").strip().upper()
            cases.append(None if classe == "ABS" else (texte or "POLY"))
        grille[nom.strip()] = cases
    return grille


def horaires(cases):
    """Plages de presence : suites de cases non absentes."""
    plages, debut = [], None
    for i, c in enumerate(cases + [None]):
        if c is not None and debut is None:
            debut = i
        elif c is None and debut is not None:
            plages.append((debut, i))
            debut = None
    return plages


def noms_reels(grille, chemin_db):
    """Le planning affiche nom.title() : "GEAY Emilie" devient "Geay Emilie".
    Sans remise en correspondance, cache_emp.get() echoue et TOUS les employes
    heritent des valeurs par defaut — ni restriction_cls, ni restriction handicap.
    Les reproductions etaient donc fausses."""
    import sqlite3
    conn = sqlite3.connect(chemin_db)
    reels = [r[0] for r in conn.execute("select nom from employes")]
    conn.close()
    index = {n.lower(): n for n in reels}
    corrige, inconnus = {}, []
    for affiche, cases in grille.items():
        vrai = index.get(affiche.lower())
        if vrai is None:
            inconnus.append(affiche)
            vrai = affiche
        corrige[vrai] = cases
    return corrige, inconnus


def en_scenario(grille):
    scen, souci = {}, []
    for nom, cases in grille.items():
        p = horaires(cases)
        if not p:
            continue
        def h(i):
            return SLOTS[i] if i < len(SLOTS) else "20:00"
        if len(p) == 1:
            a, b = p[0]
            scen[nom] = {"ms": h(a), "me": h(b), "aes": "", "aee": ""}
        elif len(p) == 2:
            a, b = p[0]; c, d = p[1]
            scen[nom] = {"ms": h(a), "me": h(b), "aes": h(c), "aee": h(d)}
        else:
            a = p[0][0]; d = p[-1][1]
            scen[nom] = {"ms": h(a), "me": h(p[0][1]), "aes": h(p[1][0]), "aee": h(d)}
            souci.append(f"{nom} : {len(p)} plages de presence, fusionnees")
    return scen, souci


if __name__ == "__main__":
    cible = sys.argv[1] if len(sys.argv) > 1 else "Planning_A4_01-08-2026.html"
    chemin = os.path.join(PLANNINGS, cible)
    grille = lire(chemin)
    scen, souci = en_scenario(grille)
    print(f"{cible} : {len(grille)} employes\n")
    for nom, t in sorted(scen.items()):
        m = f"{t['ms']}-{t['me']}" if t['ms'] else "--"
        a = f"{t['aes']}-{t['aee']}" if t['aes'] else "--"
        print(f"  {nom:24s} matin {m:12s} aprem {a:12s}")
    for s in souci:
        print("  ! " + s)
    # nombre de titulaires par caisse dans le planning genere
    print("\ntitulaires successifs par caisse :")
    for k in [1, 2, 13, 14, 5, 6, 3, 4, 7, 8, 9, 10, 11, 12]:
        su = []
        for i in range(44):
            qui = next((n for n, c in grille.items() if i < len(c) and c[i] == f"C{k}"), None)
            if qui and (not su or su[-1] != qui):
                su.append(qui)
        if su:
            print(f"  C{k:<3} {len(su)} titulaire(s) : " + " > ".join(n.split()[0][:9] for n in su))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenario_reel.json")
    json.dump(scen, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nhoraires ecrits dans {out}")
