# -*- coding: utf-8 -*-
"""Affectation des caisses par programmation par contraintes (OR-Tools CP-SAT).

Remplace les etapes 3 et 4 de algo.py — le glouton chronologique et le recuit
simule qui le rattrape. Les missions (closer, CLS, pause) restent produites en
amont par algo.py et sont donnees ici comme des cases figees.

Pourquoi ce changement : le recuit ne convertissait que 1,2 % de ses essais et
n'evitait que 5 releves sur 99 mesurees sur quatre journees reelles. La qualite
venait du glouton, qui decide creneau par creneau sans jamais revenir en arriere.
Un solveur exact regarde la journee entiere d'un coup.

Regles appliquees : voir REGLES_METIER.md. Les identifiants D*, S* et N* cites
dans les commentaires renvoient a ce document.
"""

from ortools.sat.python import cp_model

# On reprend les constantes de algo.py plutot que de les redefinir : deux
# sources de verite finiraient par diverger.
from algo import (
    ORDRE_CAISSES, CAISSES_CRITIQUES, CAISSES_ININTERROMPUES,
    TROU_TOLERE, DUREE_MIN_CAISSE, DUREE_MIN_BLOC_CAISSE,
    PAIRES_ADJACENTES, sont_adjacentes, caisse_autorisee,
    caisses_evitees as algo_caisses_evitees,
)

VERSION_SOLVEUR = "cpsat-0.1"

# Budget de recherche, exprime en TEMPS DETERMINISTE et non en secondes.
# C'est l'unite de travail interne de CP-SAT : elle ne depend ni de la charge de
# la machine ni du nombre de fils, donc deux generations du meme jour donnent le
# meme planning, sur un poste de developpement comme sur l'hebergement mutualise.
# Un plafond en secondes rendrait le resultat dependant du materiel — c'est
# exactement le piege dans lequel etait tombee la version a recuit simule.
BUDGET_DETERMINISTE = float(__import__("os").environ.get("CPSAT_BUDGET", "60"))
# Garde-fou en temps reel, pour ne jamais bloquer l'interface. L'atteindre casse
# la reproductibilite : un avertissement est alors remonte.
TEMPS_MAX_S = float(__import__("os").environ.get("CPSAT_SECONDES", "45"))
# Le budget deterministe autorise le multi-fils sans perdre la reproductibilite.
NB_FILS = 8

# --- Couts. Meme echelle que POIDS dans algo.py, pour pouvoir comparer les deux
#     solveurs sur la meme fonction de cout.
COUT_RELEVE = 60           # S4, applique de facon progressive
COUT_RELEVE_NON_ALIGNEE = 150   # S5
COUT_BLOC_COURT = 300      # S6 : poste de moins de 1h30
# Cout progressif du morcellement de la journee d'un employe (2e poste 1x, 3e 2x,
# 6e 5x). Regle a part de COUT_BLOC_COURT : trop haut, le solveur prefere fermer
# une caisse du fond plutot que d'ajouter un poste a quelqu'un d'inoccupe.
COUT_POSTE_SUPP = int(__import__("os").environ.get("CPSAT_POSTE", "120"))
COUT_BLOC_ISOLE = 800      # S7 : poste de 15 min
COUT_MEME_CAISSE_JOUR = 300     # S8
COUT_TROU_C1C2 = 1000      # D12
COUT_TROU_CRITIQUE = 300   # S1, au-dela de TROU_TOLERE

GAIN_C1C2 = 800            # S3
GAIN_C13C14 = 400
GAIN_BASE = 40
GAIN_PRIORITE = 12

# Preference : un interimaire est mieux place sur C1 ou C2 (decision du 31/07,
# auparavant les quatre caisses critiques).
GAIN_INTERIMAIRE_C1C2 = 100


def gain_couverture(num_caisse):
    """S3 — recompense graduee. Une recompense uniforme faisait ouvrir C10, C11
    et C12 pendant que C5 et C6 restaient fermees."""
    if num_caisse in CAISSES_ININTERROMPUES:
        return GAIN_C1C2
    if num_caisse in CAISSES_CRITIQUES:
        return GAIN_C13C14
    rang = ORDRE_CAISSES.index(num_caisse)
    return GAIN_BASE + GAIN_PRIORITE * (len(ORDRE_CAISSES) - rang)


def cout_progressif(cout_unitaire, nb_blocs):
    """S4 — la k-ieme transition coute k fois le cout unitaire. Pour nb_blocs
    blocs successifs il y a nb_blocs - 1 transitions, donc
    cout * (1 + 2 + ... + (nb_blocs - 1)).

    Sans cette progression, un cout fixe pousse le solveur a supprimer TOUTES les
    transitions en figeant tout le monde sur une seule caisse toute la journee —
    le defaut signale a la version 2."""
    n = max(0, nb_blocs - 1)
    return cout_unitaire * n * (n + 1) // 2


def infos_de(cache_emp, nom):
    return cache_emp.get(nom, {'statut': 'CDI', 'restriction_cls': False,
                               'restriction_handicap': 'Aucun'})


def penalites_nominatives(nom, cache_emp):
    """Caisses que la personne prefere eviter, avec leur poids.

    Lues depuis la colonne `caisses_evitees` de la table employes, au format
    "1:5000,2:3000". Les dictionnaires en dur de algo.py qui servaient de repli
    ont ete supprimes le 2026-08-01 : plus aucun nom de personne dans le code.
    """
    return algo_caisses_evitees(infos_de(cache_emp, nom))


def resoudre(matrice_figee, slots, employes_presents, presence, cache_emp,
             temps_max=None, journal=None, indice=None, budget=None):
    """Remplit les cases vides de `matrice_figee` avec des affectations caisse.

    matrice_figee : matrice[creneau][employe] telle que produite par les etapes
        0 a 1 de algo.py. Les cases "CLS" et "PAUSE" sont intouchables ; tout le
        reste est remis en jeu, y compris ce que le glouton avait deja pose.
    presence : presence[nom][creneau] -> bool.
    indice : planning glouton complet, propose au solveur comme point de depart.
        Sans lui, CP-SAT part de zero et n'a pas fini d'ouvrir les caisses au
        bout de 20 s. Avec lui, il commence a la qualite du glouton et ne peut
        qu'ameliorer.

    Renvoie (matrice, infos) ou infos porte le statut du solveur.
    """
    nb_slots = len(slots)
    nb_emp = len(employes_presents)
    if nb_emp == 0:
        return matrice_figee, {"statut": "VIDE"}

    modele = cp_model.CpModel()
    caisses = list(ORDRE_CAISSES)

    # --- disponibilite reelle : present, et pas deja pris par une mission ---
    # D3 : on n'affecte personne hors de ses heures.
    dispo = [[bool(presence[employes_presents[e]][i])
              and matrice_figee[i][e] not in ("CLS", "PAUSE")
              for e in range(nb_emp)] for i in range(nb_slots)]

    # --- variables : a[i][e][c] = l'employe e tient la caisse c au creneau i ---
    a = {}
    for i in range(nb_slots):
        for e in range(nb_emp):
            infos = infos_de(cache_emp, employes_presents[e])
            for c in caisses:
                # D4, D5 : la restriction handicap est un filtre, pas un cout.
                # La variable n'existe simplement pas.
                if dispo[i][e] and caisse_autorisee(c, infos):
                    a[i, e, c] = modele.NewBoolVar(f"a_{i}_{e}_{c}")

    def var(i, e, c):
        return a.get((i, e, c))

    # D1 : une seule tache a la fois pour un employe.
    for i in range(nb_slots):
        for e in range(nb_emp):
            actives = [v for c in caisses if (v := var(i, e, c)) is not None]
            if actives:
                modele.AddAtMostOne(actives)

    # D2 : une caisse est tenue par au plus une personne.
    tenue = {}
    for i in range(nb_slots):
        for c in caisses:
            actives = [v for e in range(nb_emp) if (v := var(i, e, c)) is not None]
            t = modele.NewBoolVar(f"tenue_{i}_{c}")
            if actives:
                modele.AddAtMostOne(actives)
                modele.Add(sum(actives) == 1).OnlyEnforceIf(t)
                modele.Add(sum(actives) == 0).OnlyEnforceIf(t.Not())
            else:
                modele.Add(t == 0)
            tenue[i, c] = t

    # --- travaille[e][c] : l'employe touche cette caisse au moins une fois ---
    travaille = {}
    for e in range(nb_emp):
        for c in caisses:
            actives = [v for i in range(nb_slots) if (v := var(i, e, c)) is not None]
            t = modele.NewBoolVar(f"trav_{e}_{c}")
            if actives:
                modele.AddMaxEquality(t, actives)
            else:
                modele.Add(t == 0)
            travaille[e, c] = t

    # D7 : jamais de glissement d'une caisse vers sa mitoyenne.
    #
    # La version gloutonne compare la caisse d'arrivee a la derniere caisse
    # tenue, en traversant les pauses. Reproduire cet etat exigeait un
    # attachement propage creneau par creneau : 14000 variables booleennes et
    # autant de contraintes de canalisation, pour un solveur qui n'atteignait
    # meme plus une solution correcte en 20 s.
    #
    # On applique donc la regle a l'echelle de la JOURNEE : un employe ne touche
    # jamais deux caisses mitoyennes le meme jour. C'est plus strict que la
    # regle d'origine — elle autorisait C1 puis C5 puis C2 — mais c'est la
    # lecture metier la plus simple, et elle coute 7 contraintes par employe au
    # lieu de 600.
    if __import__("os").environ.get("CPSAT_MITOYENNES", "1") == "1":
        for e in range(nb_emp):
            for c1, c2 in PAIRES_ADJACENTES:
                modele.AddAtMostOne([travaille[e, c1], travaille[e, c2]])

    # --- creneau precedent PERTINENT, calcule une fois pour toutes ---
    # Une PAUSE ne rompt pas la continuite : reprendre sa caisse apres la pause
    # n'est ni un nouveau poste ni une releve. Une absence ou un CLS rompent.
    # Tout cela est connu avant la resolution — les missions sont figees — donc
    # c'est une table statique, pas des variables.
    precedent_de = {}
    for e in range(nb_emp):
        nom = employes_presents[e]
        for i in range(nb_slots):
            j = i - 1
            while j >= 0 and matrice_figee[j][e] == "PAUSE" and presence[nom][j]:
                j -= 1
            if j < 0 or not presence[nom][j] or matrice_figee[j][e] == "CLS":
                precedent_de[i, e] = None     # le bloc repart de zero
            else:
                precedent_de[i, e] = j

    suivant_de = {}
    for e in range(nb_emp):
        nom = employes_presents[e]
        for i in range(nb_slots):
            j = i + 1
            while j < nb_slots and matrice_figee[j][e] == "PAUSE" and presence[nom][j]:
                j += 1
            if j >= nb_slots or not presence[nom][j] or matrice_figee[j][e] == "CLS":
                suivant_de[i, e] = None       # le bloc s'arrete la
            else:
                suivant_de[i, e] = j

    # --- debuts de bloc : sert au comptage des releves et des postes ---
    debut = {}
    for e in range(nb_emp):
        for c in caisses:
            for i in range(nb_slots):
                v = var(i, e, c)
                if v is None:
                    continue
                j = precedent_de[i, e]
                precedent = var(j, e, c) if j is not None else None
                d = modele.NewBoolVar(f"debut_{i}_{e}_{c}")
                if precedent is None:
                    modele.Add(d == v)
                else:
                    # d = v ET NON precedent
                    modele.AddBoolAnd([d]).OnlyEnforceIf([v, precedent.Not()])
                    modele.AddImplication(d, v)
                    modele.AddImplication(d, precedent.Not())
                debut[i, e, c] = d

    objectif = []

    # --- S3 : recompense de couverture ---
    for i in range(nb_slots):
        for c in caisses:
            objectif.append(-gain_couverture(c) * tenue[i, c])

    # --- S4 : cout progressif des releves, par caisse ---
    #
    # Une releve, c'est un CHANGEMENT DE TITULAIRE dans le temps. Ni un nombre de
    # blocs, ni un nombre de personnes distinctes — j'ai essaye les deux et les
    # deux sont faux :
    #   - compter les blocs facture une releve fantome quand une caisse est
    #     laissee vide un moment puis reprise par la MEME personne ;
    #   - compter les personnes distinctes rate A -> B -> A, qui fait bien deux
    #     releves avec deux personnes seulement.
    #
    # On suit donc le titulaire de chaque caisse au fil de la journee. titulaire
    # vaut 0 tant que personne n'y est passe, puis e+1, et il PERSISTE quand la
    # caisse se vide : c'est ce qui fait qu'un creux ne compte pas comme une
    # releve, exactement comme dans evaluer_planning().
    #
    # Cout : une variable entiere par caisse et par creneau, soit 616 — contre
    # 14000 booleens pour la version par blocs.
    titulaire = {}
    for c in caisses:
        for i in range(nb_slots):
            t = modele.NewIntVar(0, nb_emp, f"titulaire_{i}_{c}")
            titulaire[i, c] = t
            for e in range(nb_emp):
                v = var(i, e, c)
                if v is not None:
                    modele.Add(t == e + 1).OnlyEnforceIf(v)
            if i == 0:
                modele.Add(t == 0).OnlyEnforceIf(tenue[i, c].Not())
            else:
                # la caisse est vide : on garde en memoire qui la tenait
                modele.Add(t == titulaire[i - 1, c]).OnlyEnforceIf(tenue[i, c].Not())

    for c in caisses:
        changements = []
        for i in range(1, nb_slots):
            # releve = le titulaire change ET il y avait quelqu'un avant
            differe = modele.NewBoolVar(f"diff_{i}_{c}")
            modele.Add(titulaire[i, c] != titulaire[i - 1, c]).OnlyEnforceIf(differe)
            modele.Add(titulaire[i, c] == titulaire[i - 1, c]).OnlyEnforceIf(differe.Not())
            precedent_non_vide = modele.NewBoolVar(f"pnv_{i}_{c}")
            modele.Add(titulaire[i - 1, c] != 0).OnlyEnforceIf(precedent_non_vide)
            modele.Add(titulaire[i - 1, c] == 0).OnlyEnforceIf(precedent_non_vide.Not())
            chg = modele.NewBoolVar(f"chg_{i}_{c}")
            modele.AddBoolAnd([chg]).OnlyEnforceIf([differe, precedent_non_vide])
            modele.AddImplication(chg, differe)
            modele.AddImplication(chg, precedent_non_vide)
            changements.append(chg)

        nb_releves = modele.NewIntVar(0, len(changements), f"nb_releves_{c}")
        modele.Add(nb_releves == sum(changements))
        # progressif : la 1re releve coute 1x, la 2e 2x, la 5e 5x. Un cout fixe
        # pousse le solveur a figer tout le monde ; c'etait le defaut de la v2.
        table = [COUT_RELEVE * n * (n + 1) // 2 for n in range(len(changements) + 1)]
        cout_c = modele.NewIntVar(0, max(table), f"cout_releves_{c}")
        modele.AddElement(nb_releves, table, cout_c)
        objectif.append(cout_c)

    # --- S7 : pas de bloc isole, en CONTRAINTE DURE ---
    # Un poste qui demarre doit tenir au moins DUREE_MIN_BLOC_CAISSE creneaux.
    # C'etait une penalite de 800 dans la version precedente : 14000 variables
    # booleennes supplementaires, pour une regle que l'utilisateur formule comme
    # un interdit. C1 et C2 restent exemptees — un bloc court y vaut mieux qu'une
    # fermeture.
    for e in range(nb_emp):
        for c in caisses:
            if c in CAISSES_ININTERROMPUES:
                continue
            for i in range(nb_slots):
                d = debut.get((i, e, c))
                if d is None:
                    continue
                curseur = i
                for _ in range(DUREE_MIN_BLOC_CAISSE - 1):
                    j = suivant_de[curseur, e]
                    suivant = var(j, e, c) if j is not None else None
                    if suivant is None:
                        # l'employe n'est plus disponible : ne pas l'installer
                        modele.Add(d == 0)
                        break
                    modele.AddImplication(d, suivant)
                    curseur = j

    # --- S6 : changements de caisse d'un employe dans sa journee ---
    # "Je prefere un employe qui reste toute la journee a sa caisse plutot que
    # six changements, mais il faut un juste milieu."
    #
    # Meme construction, cote employe : on suit la caisse a laquelle il est
    # rattache. Elle persiste pendant une pause ou un creux — y revenir n'est pas
    # un changement — et se remet a zero quand il quitte le site ou part en CLS.
    for e in range(nb_emp):
        nom = employes_presents[e]
        poste = {}
        changements = []
        for i in range(nb_slots):
            p = modele.NewIntVar(0, len(caisses), f"poste_{i}_{e}")
            poste[i] = p
            assis = [v for c in caisses if (v := var(i, e, c)) is not None]
            for rang, c in enumerate(caisses):
                v = var(i, e, c)
                if v is not None:
                    modele.Add(p == rang + 1).OnlyEnforceIf(v)
            # rupture connue d'avance : hors site, ou parti en mission CLS
            if not presence[nom][i] or matrice_figee[i][e] == "CLS":
                modele.Add(p == 0)
            elif not assis:
                modele.Add(p == (poste[i - 1] if i > 0 else 0))
            else:
                # libre ou en pause : il reste rattache a sa caisse
                libre = modele.NewBoolVar(f"libre_{i}_{e}")
                modele.Add(sum(assis) == 0).OnlyEnforceIf(libre)
                modele.Add(sum(assis) == 1).OnlyEnforceIf(libre.Not())
                if i > 0:
                    modele.Add(p == poste[i - 1]).OnlyEnforceIf(libre)
                else:
                    modele.Add(p == 0).OnlyEnforceIf(libre)

            if i > 0:
                differe = modele.NewBoolVar(f"ediff_{i}_{e}")
                modele.Add(poste[i] != poste[i - 1]).OnlyEnforceIf(differe)
                modele.Add(poste[i] == poste[i - 1]).OnlyEnforceIf(differe.Not())
                # un changement, c'est passer d'une caisse a une AUTRE caisse.
                # Prendre son premier poste ou rentrer chez soi n'en est pas un.
                avant_non_vide = modele.NewBoolVar(f"eanv_{i}_{e}")
                modele.Add(poste[i - 1] != 0).OnlyEnforceIf(avant_non_vide)
                modele.Add(poste[i - 1] == 0).OnlyEnforceIf(avant_non_vide.Not())
                apres_non_vide = modele.NewBoolVar(f"eapv_{i}_{e}")
                modele.Add(poste[i] != 0).OnlyEnforceIf(apres_non_vide)
                modele.Add(poste[i] == 0).OnlyEnforceIf(apres_non_vide.Not())
                chg = modele.NewBoolVar(f"echg_{i}_{e}")
                modele.AddBoolAnd([chg]).OnlyEnforceIf(
                    [differe, avant_non_vide, apres_non_vide])
                modele.AddImplication(chg, differe)
                modele.AddImplication(chg, avant_non_vide)
                modele.AddImplication(chg, apres_non_vide)
                changements.append(chg)

        if changements:
            nb_chg = modele.NewIntVar(0, len(changements), f"nb_chg_{e}")
            modele.Add(nb_chg == sum(changements))
            table = [COUT_POSTE_SUPP * n * (n + 1) // 2
                     for n in range(len(changements) + 1)]
            cout_e = modele.NewIntVar(0, max(table), f"cout_chg_{e}")
            modele.AddElement(nb_chg, table, cout_e)
            objectif.append(cout_e)

    # --- D12, S1 : caisses fermees ---
    # C1 et C2 ne doivent jamais fermer ; C13 et C14 tolerent 1h30 de trou. Le
    # cout ne s'applique que si quelqu'un etait disponible, sinon on penaliserait
    # une situation que le planning ne peut pas resoudre.
    for c in CAISSES_CRITIQUES:
        cout_trou = COUT_TROU_C1C2 if c in CAISSES_ININTERROMPUES else COUT_TROU_CRITIQUE
        for i in range(nb_slots):
            quelqu_un_dispo = any(var(i, e, c) is not None for e in range(nb_emp))
            if quelqu_un_dispo:
                objectif.append(cout_trou * tenue[i, c].Not())

        # S1 : au-dela de TROU_TOLERE creneaux consecutifs, surcout.
        if c not in CAISSES_ININTERROMPUES:
            for i in range(nb_slots - TROU_TOLERE):
                fenetre = [tenue[j, c] for j in range(i, i + TROU_TOLERE + 1)]
                trop_long = modele.NewBoolVar(f"trou_long_{i}_{c}")
                modele.AddBoolAnd([t.Not() for t in fenetre]).OnlyEnforceIf(trop_long)
                modele.AddBoolOr(fenetre).OnlyEnforceIf(trop_long.Not())
                objectif.append(COUT_TROU_CRITIQUE * trop_long)

    # --- N3, N4 : caisses evitees par certaines personnes ---
    for e in range(nb_emp):
        penalites = penalites_nominatives(employes_presents[e], cache_emp)
        for c, poids in penalites.items():
            for i in range(nb_slots):
                v = var(i, e, c)
                if v is not None:
                    # divise par le nombre de creneaux : la penalite porte sur le
                    # fait d'y etre, pas sur chaque quart d'heure
                    objectif.append((poids // nb_slots) * v)

    # --- interimaire prefere sur C1 et C2 (decision du 31/07) ---
    for e in range(nb_emp):
        if infos_de(cache_emp, employes_presents[e]).get('statut') == "Interimaire":
            for c in CAISSES_ININTERROMPUES:
                for i in range(nb_slots):
                    v = var(i, e, c)
                    if v is not None:
                        objectif.append(-GAIN_INTERIMAIRE_C1C2 * v)

    # --- S8 : meme caisse avant et apres la coupure ---
    # Seuls les employes qui ont reellement une coupure sont concernes.
    for e in range(nb_emp):
        nom = employes_presents[e]
        creneaux_presents = [i for i in range(nb_slots) if presence[nom][i]]
        if not creneaux_presents:
            continue
        coupures = [i for i in range(creneaux_presents[0], creneaux_presents[-1])
                    if not presence[nom][i]]
        if not coupures:
            continue
        bascule = coupures[-1]
        for c in caisses:
            avant = [v for i in range(bascule) if (v := var(i, e, c)) is not None]
            apres = [v for i in range(bascule, nb_slots)
                     if (v := var(i, e, c)) is not None]
            if not avant or not apres:
                continue
            # C1, C2, C13 et C14 exceptees : l'usage y accepte le meme poste.
            if c in CAISSES_CRITIQUES:
                continue
            b_avant = modele.NewBoolVar(f"av_{e}_{c}")
            b_apres = modele.NewBoolVar(f"ap_{e}_{c}")
            modele.AddMaxEquality(b_avant, avant)
            modele.AddMaxEquality(b_apres, apres)
            les_deux = modele.NewBoolVar(f"deux_{e}_{c}")
            modele.AddBoolAnd([les_deux]).OnlyEnforceIf([b_avant, b_apres])
            modele.AddImplication(les_deux, b_avant)
            modele.AddImplication(les_deux, b_apres)
            objectif.append(COUT_MEME_CAISSE_JOUR * les_deux)

    modele.Minimize(sum(objectif))

    # --- point de depart : le planning glouton ---
    # Une contrainte du modele peut interdire ce que le glouton avait pose (la
    # regle des caisses mitoyennes est plus stricte ici). Un indice invalide est
    # ignore par CP-SAT sans faire echouer la resolution, mais on ne pose que les
    # variables coherentes pour lui laisser le plus de matiere possible.
    if indice is not None:
        touchees = set()
        for i in range(nb_slots):
            for e in range(nb_emp):
                tache = indice[i][e]
                if not tache.startswith("C") or tache == "CLS":
                    continue
                try:
                    c = int(tache[1:])
                except ValueError:
                    continue
                v = var(i, e, c)
                if v is not None:
                    modele.AddHint(v, 1)
                    touchees.add((i, e, c))
        for cle, v in a.items():
            if cle not in touchees:
                modele.AddHint(v, 0)

    solveur = cp_model.CpSolver()
    solveur.parameters.max_deterministic_time = budget or BUDGET_DETERMINISTE
    solveur.parameters.max_time_in_seconds = temps_max or TEMPS_MAX_S
    solveur.parameters.num_workers = NB_FILS
    solveur.parameters.random_seed = 1
    statut = solveur.Solve(modele)

    trouve = statut in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    infos = {
        "statut": solveur.StatusName(statut),
        "cout": solveur.ObjectiveValue() if trouve else None,
        "borne": solveur.BestObjectiveBound() if trouve else None,
        "secondes": round(solveur.WallTime(), 2),
        "temps_deterministe": round(solveur.ResponseProto().deterministic_time, 2),
        "variables": len(a) + len(debut) + len(travaille) + len(tenue),
        # vrai si le garde-fou en secondes a coupe avant le budget deterministe :
        # le planning reste valide mais n'est plus reproductible a l'identique
        "coupe_par_le_temps": (solveur.WallTime() >= (temps_max or TEMPS_MAX_S) * 0.98),
    }
    if journal is not None:
        journal.update(infos)

    if statut not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # aucune solution : on rend le planning d'entree plutot que rien
        return matrice_figee, infos

    matrice = [ligne[:] for ligne in matrice_figee]
    for i in range(nb_slots):
        for e in range(nb_emp):
            if matrice[i][e] in ("CLS", "PAUSE"):
                continue
            matrice[i][e] = ""
            for c in caisses:
                v = var(i, e, c)
                if v is not None and solveur.Value(v):
                    matrice[i][e] = f"C{c}"
                    break
    return matrice, infos
