import math
from datetime import datetime, timedelta
import os
import database as db

TIME_STEP = 15
MARGE_MISSION_PAUSE_MIN = 30
BLACKLIST_CLS_PERMANENT = ["jean marc", "jessica", "emmanuel"]

# --- STABILITE DES AFFECTATIONS CAISSE ---
# Ordre d'ouverture des caisses. Seules CAISSES_CRITIQUES declenchent un
# reequilibrage quand elles se vident ; les autres sont interchangeables.
ORDRE_CAISSES = [1, 2, 13, 14, 5, 6, 3, 4, 7, 8, 9, 10, 11, 12]
CAISSES_CRITIQUES = {1, 2, 13, 14}
# C1 et C2 doivent rester ouvertes sans la moindre interruption : des qu'elles se
# vident, on les recomble au creneau suivant, quitte a fermer une caisse du fond.
CAISSES_ININTERROMPUES = {1, 2}
# Sur les autres caisses (C13 et C14 comprises) on accepte un trou plutot que de
# creer de l'instabilite. Au-dela, on comble meme si le remplacant vient de
# s'installer ailleurs.
TROU_TOLERE = 6  # 1h30
# Duree minimale d'un poste avant qu'un deplacement soit autorise (en creneaux de 15 min).
DUREE_MIN_CAISSE = 6  # 1h30
# Caisses adjacentes : un employe ne doit pas glisser de l'une a l'autre.
PAIRES_ADJACENTES = [[1, 2], [13, 14], [5, 6], [3, 4], [7, 8], [9, 10], [11, 12]]
# On n'installe personne sur une caisse pour un bloc isole de 15 min : mieux vaut
# laisser la caisse libre et faire commencer le suivant plus tot.
DUREE_MIN_BLOC_CAISSE = 2  # 30 min
# Quand le titulaire de la mission pause part en coupure ou termine sa journee,
# on ne mobilise pas quelqu'un d'autre pour un reliquat trop court.
RELAI_PAUSE_MIN = 3  # 45 min

HIERARCHIE_PENALITE_C1_C2 = {
    "léandre": 1000, 
    "dalya": 2000, 
    "ethan": 3000, 
    "yacine": 5000 
}

HIERARCHIE_PENALITE_C13_C14 = {
    "yacine": 3000, 
    "ethan": 3000, 
    "nathalie": 500
}

def get_time(string_time):
    try: 
        return datetime.strptime(string_time, "%H:%M")
    except ValueError: 
        return None

def calc_duration(start_str, end_str):
    try:
        t_start = datetime.strptime(start_str, "%H:%M")
        t_end = datetime.strptime(end_str, "%H:%M")
        return (t_end - t_start).seconds / 3600, t_end
    except ValueError: 
        return 0, None

def _tokens(nom):
    """Decoupe un nom en mots normalises. Evite les faux positifs de la
    recherche par sous-chaine ('emmanuel' matchait 'CADEAU Emmanuelle')."""
    return set(m for m in (nom or "").lower().replace("-", " ").split() if m)

def _cle_matche(cle, nom):
    """Vrai si tous les mots de la cle sont des mots entiers du nom."""
    return _tokens(cle).issubset(_tokens(nom)) if cle else False

def is_same_person(nom1, nom2):
    if not nom1 or not nom2:
        return False
    t1, t2 = _tokens(nom1), _tokens(nom2)
    if t1 == t2:
        return True
    # Inclusion acceptee seulement si le nom le plus court a au moins 2 mots,
    # sinon un simple prenom identifierait plusieurs personnes.
    court, long_ = (t1, t2) if len(t1) <= len(t2) else (t2, t1)
    return len(court) >= 2 and court.issubset(long_)

def is_blacklisted(nom):
    return any(_cle_matche(b, nom) for b in BLACKLIST_CLS_PERMANENT)

def get_penalite(nom, dictionnaire_hierarchie):
    for nom_cle, valeur in dictionnaire_hierarchie.items():
        if _cle_matche(nom_cle, nom):
            return valeur
    return 0

def caisse_autorisee(num_caisse, infos):
    """Filtre dur : une restriction handicap ne doit jamais etre contournable
    par un bonus de score (bug du seuil 900000)."""
    restriction = infos.get('restriction_handicap', 'Aucun')
    if restriction == "Aucun" or not restriction:
        return True
    est_pair = (num_caisse % 2 == 0)
    if restriction == "Caisse Impaire Uniq.":
        return not est_pair
    if restriction == "Caisse Paire Uniq.":
        return est_pair
    return True

def sont_adjacentes(num_a, num_b):
    # une caisse n'est pas mitoyenne d'elle-meme : y revenir doit rester possible
    if num_a == num_b:
        return False
    return any(num_a in p and num_b in p for p in PAIRES_ADJACENTES)

def generate_timeline():
    start_time = datetime.strptime("09:00", "%H:%M")
    end_time = datetime.strptime("20:00", "%H:%M")
    timeline = []
    current_time = start_time
    while current_time < end_time: 
        timeline.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=TIME_STEP)
    return timeline

def build_presence(plan_data, slots, employes_presents):
    """presence[nom][i] = l'employe est sur site au creneau i.

    Calcule une seule fois pour la journee. L'ancienne version recalculait la
    presence a chaque appel, depuis la boucle la plus interne de l'etape 3."""
    heures = [datetime.strptime(s, "%H:%M") for s in slots]
    presence = {nom: [False] * len(slots) for nom in employes_presents}
    for p in plan_data:
        colonne = presence.get(p['nom'])
        if colonne is None:
            continue
        for i, heure_obj in enumerate(heures):
            matin_ok = p['matin'][0] and p['matin'][1] and p['matin'][0] <= heure_obj < p['matin'][1]
            aprem_ok = p['aprem'][0] and p['aprem'][1] and p['aprem'][0] <= heure_obj < p['aprem'][1]
            if matin_ok or aprem_ok:
                colonne[i] = True
    return presence

def get_available_slots_indices(nom, presence, matrice, map_employes):
    colonne = map_employes[nom]
    dispo = presence[nom]
    return [i for i in range(len(matrice)) if dispo[i] and not matrice[i][colonne]]

def get_continuous_block(indices_libres, start_idx):
    compteur = 0
    curseur = start_idx
    while curseur in indices_libres: 
        compteur += 1
        curseur += 1
    return compteur

def run_algo(date_saisie, inputs_dict, cache_emp):
    try: 
        date_obj = datetime.strptime(date_saisie, "%d/%m/%Y")
    except ValueError: 
        date_obj = datetime.now()
        
    date_hier = (date_obj - timedelta(days=1)).strftime("%d/%m/%Y")
    est_dimanche = (date_obj.weekday() == 6)
    
    closer_veille = db.get_historique_fermeture(date_hier)

    plan_data = []
    employes_presents = []
    minutes_matin = 0
    minutes_aprem = 0
    
    # 1. Collecte des données
    for nom, times in inputs_dict.items():
        e_m1, e_m2, e_a1, e_a2 = times.get('ms', ''), times.get('me', ''), times.get('aes', ''), times.get('aee', '')
        start_m, end_m = get_time(e_m1), get_time(e_m2)
        start_a, end_a = get_time(e_a1), get_time(e_a2)
        
        if start_m and end_m: 
            minutes_matin += ((end_m - start_m).seconds / 3600) * 3
        if start_a and end_a: 
            minutes_aprem += ((end_a - start_a).seconds / 3600) * 3
            
        if start_m or start_a: 
            plan_data.append({"nom": nom, "matin": (start_m, end_m), "aprem": (start_a, end_a)})
            employes_presents.append(nom)
    
    if not employes_presents: 
        return {"error": "Aucun employé n'est planifié aujourd'hui."}

    slots = generate_timeline()
    matrice_planning = [["" for _ in employes_presents] for _ in slots]
    map_employes = {nom: index for index, nom in enumerate(employes_presents)}
    presence = build_presence(plan_data, slots, employes_presents)

    def assigner_tache(nom, tache, start_idx, length):
        colonne = map_employes[nom]
        for k in range(start_idx, start_idx + length): 
            if k < len(slots): 
                matrice_planning[k][colonne] = tache

    compteur_cls = {nom: 0 for nom in employes_presents}
    closer_assigne = None

    # --- ÉTAPE : PRIORITÉ ABSOLUE CLS LE DIMANCHE ---
    if est_dimanche:
        # Le dimanche, on commence à 09h30 (index 2) jusqu'à 13h00 (index 16).
        # On divise en deux shifts égaux de 1h45 (7 créneaux de 15min chacun).
        # Shift 1 : 09h30 -> 11h30 (Index 2, longueur 7)
        # Shift 2 : 11h30 -> 13h15 (Index 9, longueur 7)
        for index_depart, nb_creneaux in [(2, 8), (9, 8)]:
            candidats_cls = []
            for nom in employes_presents:
                # Vérifier si l'employé est autorisé et disponible
                infos = cache_emp.get(nom, {'statut': 'CDI', 'restriction_cls': False, 'restriction_handicap': 'Aucun'})
                if infos.get('restriction_cls') or is_blacklisted(nom) or compteur_cls[nom] >= 1: 
                    continue
                
                indices_libres = get_available_slots_indices(nom, presence, matrice_planning, map_employes)
                if index_depart in indices_libres:
                    longueur_dispo = get_continuous_block(indices_libres, index_depart)
                    candidats_cls.append((nom, longueur_dispo))
                    
            # On évite Yacine si possible, sinon on prend la plus grande disponibilité.
            # x[0] en dernier critère : départage déterministe, indépendant de
            # l'ordre de saisie des employés.
            candidats_cls.sort(key=lambda x: (1 if _cle_matche("yacine", x[0]) else 0, -x[1], x[0]))
            
            if candidats_cls: 
                elu = candidats_cls[0][0]
                longueur_reelle = min(candidats_cls[0][1], nb_creneaux)
                assigner_tache(elu, "CLS", index_depart, longueur_reelle)
                compteur_cls[elu] += 1

    # --- ETAPE 0 : LE CLOSER ---
    if not est_dimanche:
        start_soir_idx = next((i for i, s in enumerate(slots) if s.startswith("17:00")), None)
        if start_soir_idx is not None:
            candidats_disponibles = []
            for nom in employes_presents:
                infos = cache_emp.get(nom, {'statut': 'CDI', 'restriction_cls': False, 'restriction_handicap': 'Aucun'})
                if infos['restriction_cls'] or infos['statut'] == "Interimaire" or is_blacklisted(nom) or is_same_person(nom, closer_veille): 
                    continue
                    
                indices_libres = get_available_slots_indices(nom, presence, matrice_planning, map_employes)
                if start_soir_idx in indices_libres:
                    longueur = get_continuous_block(indices_libres, start_soir_idx)
                    if longueur >= 8: 
                        candidats_disponibles.append((nom, longueur))
                        
            candidats_disponibles.sort(key=lambda x: (1 if _cle_matche("yacine", x[0]) else 0, -x[1], x[0]))

            if not candidats_disponibles:
                for nom in employes_presents:
                    infos = cache_emp.get(nom, {'statut': 'CDI', 'restriction_cls': False, 'restriction_handicap': 'Aucun'})
                    if not infos['restriction_cls']:
                        indices_libres = get_available_slots_indices(nom, presence, matrice_planning, map_employes)
                        if start_soir_idx in indices_libres: 
                            candidats_disponibles.append((nom, get_continuous_block(indices_libres, start_soir_idx)))
                candidats_disponibles.sort(key=lambda x: (-x[1], x[0]))
                
            if candidats_disponibles:
                gagnant, longueur_bloc = candidats_disponibles[0]
                assigner_tache(gagnant, "CLS", start_soir_idx, longueur_bloc)
                compteur_cls[gagnant] += 1
                closer_assigne = gagnant
                db.save_historique_fermeture(date_saisie, gagnant)

    # --- ETAPE 0.5 : CLS JOURNÉE (SEMAINE) ---
    if not est_dimanche:
        for i, ts in enumerate(slots):
            if int(ts.split(':')[0]) >= 17: break
            
            if not any(matrice_planning[i][x] == "CLS" for x in range(len(employes_presents))):
                candidats_disponibles = []
                for nom in employes_presents:
                    infos = cache_emp.get(nom, {'statut': 'CDI', 'restriction_cls': False, 'restriction_handicap': 'Aucun'})
                    if nom == closer_assigne or infos['restriction_cls'] or is_blacklisted(nom) or compteur_cls[nom] >= 1: 
                        continue
                    indices_libres = get_available_slots_indices(nom, presence, matrice_planning, map_employes)
                    if i in indices_libres: 
                        candidats_disponibles.append((nom, get_continuous_block(indices_libres, i)))
                        
                candidats_disponibles.sort(key=lambda x: (1 if x[1] < 8 else 0,
                                                          5000 if _cle_matche("yacine", x[0]) else 0,
                                                          x[0]))
                if candidats_disponibles: 
                    assigner_tache(candidats_disponibles[0][0], "CLS", i, min(candidats_disponibles[0][1], 8))
                    compteur_cls[candidats_disponibles[0][0]] += 1

    # --- ETAPE 1 : LES PAUSES ---
    slots_pause_matin = math.ceil((minutes_matin + MARGE_MISSION_PAUSE_MIN) / 15)
    if slots_pause_matin > 0:
        cur_idx = 6
        restant = slots_pause_matin
        premier_titulaire = True
        while restant > 0 and cur_idx < 20:
            # Le titulaire precedent est parti en coupure ou a fini sa journee :
            # on ne mobilise pas quelqu'un d'autre pour un reliquat de moins de 45 min.
            if not premier_titulaire and restant < RELAI_PAUSE_MIN:
                break
            candidats_disponibles = []
            for nom in employes_presents:
                if _cle_matche("andré", nom): continue


                indices_libres = get_available_slots_indices(nom, presence, matrice_planning, map_employes)
                if cur_idx in indices_libres: 
                    candidats_disponibles.append({"nom": nom, "longueur": get_continuous_block(indices_libres, cur_idx)})
                    
            if not candidats_disponibles: 
                cur_idx += 1
                continue
                
            def score_pause(c):
                infos = cache_emp.get(c['nom'], {'statut': 'CDI', 'restriction_cls': False, 'restriction_handicap': 'Aucun'})
                score = 1000 if infos['statut'] != "Interimaire" else 0
                if c['nom'] == closer_assigne: score -= 5000
                return score + min(c['longueur'], restant) * 10 - db.get_mission_score(c['nom']) * 5
                
            # tri decroissant sur le score, puis nom : departage deterministe
            candidats_disponibles.sort(key=lambda c: (-score_pause(c), c['nom']))
            gagnant = candidats_disponibles[0]
            
            if gagnant["nom"] == closer_assigne and score_pause(gagnant) < 0: 
                cur_idx += 1
                continue
                
            longueur_assignee = min(gagnant['longueur'], restant)
            assigner_tache(gagnant['nom'], "PAUSE", cur_idx, longueur_assignee)
            db.inc_mission_score(gagnant['nom'])
            cur_idx += longueur_assignee
            restant -= longueur_assignee
            premier_titulaire = False

    slots_pause_aprem = math.ceil((minutes_aprem + MARGE_MISSION_PAUSE_MIN) / 15)
    if slots_pause_aprem > 0 and not est_dimanche:
        restant = slots_pause_aprem
        cur_idx = max(24, 40 - restant)
        premier_titulaire = True
        while restant > 0 and cur_idx < 44:
            if not premier_titulaire and restant < RELAI_PAUSE_MIN:
                break
            candidats_disponibles = []
            for nom in employes_presents:
                if _cle_matche("andré", nom): continue


                indices_libres = get_available_slots_indices(nom, presence, matrice_planning, map_employes)
                if cur_idx in indices_libres: 
                    candidats_disponibles.append({"nom": nom, "longueur": get_continuous_block(indices_libres, cur_idx)})
                    
            if not candidats_disponibles: 
                cur_idx += 1
                continue
                
            def score_pause_a(c):
                infos = cache_emp.get(c['nom'], {'statut': 'CDI', 'restriction_cls': False, 'restriction_handicap': 'Aucun'})
                score = 1000 if infos['statut'] != "Interimaire" else 0
                if c['nom'] == closer_assigne: score -= 5000
                return score + min(c['longueur'], restant) * 10 - db.get_mission_score(c['nom']) * 5
                
            candidats_disponibles.sort(key=lambda c: (-score_pause_a(c), c['nom']))
            gagnant = candidats_disponibles[0]
            
            if gagnant["nom"] == closer_assigne and score_pause_a(gagnant) < 0: 
                cur_idx += 1
                continue
                
            longueur_assignee = min(gagnant['longueur'], restant)
            assigner_tache(gagnant['nom'], "PAUSE", cur_idx, longueur_assignee)
            db.inc_mission_score(gagnant['nom'])
            cur_idx += longueur_assignee
            restant -= longueur_assignee
            premier_titulaire = False

    # --- ETAPE 3 : ASSIGNATION CHRONOLOGIQUE DES CAISSES ---
    # Trois phases par creneau. L'ancienne version remettait les 14 caisses en
    # concurrence toutes les 15 min : le depart d'une seule personne provoquait
    # une cascade de 2 a 3 deplacements. Ici la cascade est impossible par
    # construction.
    #   A. RECONDUCTION  - le titulaire garde sa caisse, sans mise en concurrence
    #   B. COMBLEMENT    - seules les caisses libres sont pourvues, et seulement
    #                      par des employes qui ne sont pas deja assis
    #   C. REEQUILIBRAGE - au plus UN deplacement par creneau, vers une caisse
    #                      critique uniquement ; la caisse liberee est fermee
    def infos_de(nom_c):
        return cache_emp.get(nom_c, {'statut': 'CDI', 'restriction_cls': False,
                                     'restriction_handicap': 'Aucun'})

    def derniere_caisse(nom_c, courant_i):
        """Numero de la derniere caisse tenue juste avant courant_i. Une PAUSE ne
        rompt pas la continuite ; une absence ou un CLS si."""
        colonne = map_employes[nom_c]
        for j in range(courant_i - 1, -1, -1):
            tache = matrice_planning[j][colonne]
            if not tache:
                return None
            if tache == "PAUSE":
                continue
            if tache.startswith("C") and tache != "CLS":
                return int(tache[1:])
            return None
        return None

    def presence_restante(nom_c, depart_i):
        """Nombre de creneaux consecutifs ou l'employe est encore sur site."""
        compteur = 0
        curseur = depart_i
        while curseur < len(slots) and presence[nom_c][curseur]:
            compteur += 1
            curseur += 1
        return compteur

    def penalite_hierarchie(nom_c, num_caisse):
        if num_caisse in (1, 2):
            return get_penalite(nom_c, HIERARCHIE_PENALITE_C1_C2)
        if num_caisse in (13, 14):
            return get_penalite(nom_c, HIERARCHIE_PENALITE_C13_C14)
        return 0

    titulaire = {}     # num_caisse -> nom du titulaire (conserve pendant sa pause)
    depuis_slot = {}   # nom -> creneau d'installation sur sa caisse actuelle
    poste_habituel = {}  # nom -> derniere caisse occupee, survit a un CLS / une coupure
    vide_depuis = {}   # num_caisse critique -> premier creneau ou elle est restee vide

    for i, ts in enumerate(slots):
        # --- Purge : un titulaire parti ou reaffecte ailleurs (CLS) libere sa caisse.
        #     Un titulaire en pause la conserve : la caisse reste reservee.
        for num_caisse in list(titulaire):
            nom = titulaire[num_caisse]
            tache_courante = matrice_planning[i][map_employes[nom]]
            if not presence[nom][i]:
                del titulaire[num_caisse]
            elif tache_courante and tache_courante != "PAUSE":
                del titulaire[num_caisse]

        libres = {}
        for nom in employes_presents:
            indices_libres = get_available_slots_indices(nom, presence, matrice_planning, map_employes)
            if i in indices_libres:
                libres[nom] = get_continuous_block(indices_libres, i)

        # --- A. RECONDUCTION ---
        for num_caisse, nom in titulaire.items():
            if nom in libres:
                assigner_tache(nom, f"C{num_caisse}", i, 1)
                del libres[nom]

        # --- B. COMBLEMENT ---
        for num_caisse in ORDRE_CAISSES:
            if num_caisse in titulaire:
                continue
            candidats = []
            trop_courts = []
            for nom, bloc in libres.items():
                if not caisse_autorisee(num_caisse, infos_de(nom)):
                    continue
                # jamais de glissement vers la caisse mitoyenne
                precedente = derniere_caisse(nom, i)
                if precedente is not None and sont_adjacentes(precedente, num_caisse):
                    continue
                # pas de bloc isole : si l'employe part en pause ou en coupure au
                # creneau suivant, on ne l'installe pas pour 15 min. La caisse reste
                # libre et le titulaire suivant la prend plus tot.
                if bloc < DUREE_MIN_BLOC_CAISSE:
                    trop_courts.append((nom, bloc))
                    continue
                candidats.append((nom, bloc))
            # C1 et C2 ne ferment jamais : en dernier recours on accepte un bloc court
            if not candidats and num_caisse in CAISSES_ININTERROMPUES:
                candidats = trop_courts
            if not candidats:
                continue

            def score_comblement(candidat):
                nom_c, longueur_c = candidat
                penalite = penalite_hierarchie(nom_c, num_caisse)
                # Retour au poste : apres une pause longue, un CLS ou une coupure
                # midi, on remet l'employe sur la caisse qu'il tenait avant.
                ancien_poste = poste_habituel.get(nom_c)
                if ancien_poste == num_caisse:
                    penalite -= 300000
                elif ancien_poste is not None and ancien_poste not in titulaire:
                    # sa caisse habituelle est libre : ne pas le detourner ici,
                    # elle sera pourvue plus loin dans la boucle
                    penalite += 150000
                if num_caisse in CAISSES_CRITIQUES and infos_de(nom_c).get('statut') == "Interimaire":
                    penalite -= 100000
                if _cle_matche("alicia", nom_c) and num_caisse == 1:
                    penalite -= 50000
                if longueur_c < DUREE_MIN_CAISSE:
                    penalite += 200000
                # nom_c en dernier critere : resultat deterministe, insensible a
                # l'ordre de saisie des employes
                return (penalite, -longueur_c, nom_c)

            candidats.sort(key=score_comblement)
            elu = candidats[0][0]
            assigner_tache(elu, f"C{num_caisse}", i, 1)
            titulaire[num_caisse] = elu
            depuis_slot[elu] = i
            poste_habituel[elu] = num_caisse
            del libres[elu]

        # --- C. REEQUILIBRAGE ---
        # Aucun employe n'est libre a ce stade (sinon la phase B aurait pourvu) :
        # on prend donc le titulaire de la caisse ouverte la moins prioritaire, et
        # on FERME celle-ci. La caisse source n'etant pas recomblee, aucune cascade
        # n'est possible.
        #   - C1 et C2 : aucune tolerance, on comble des le premier creneau vide,
        #     y compris pendant la pause du titulaire.
        #   - C13 et C14 : on ne comble que si une solution stable existe. Sinon on
        #     laisse le trou, jusqu'a TROU_TOLERE au maximum.
        def caisse_tenue(num):
            return any(matrice_planning[i][x] == f"C{num}" for x in range(len(employes_presents)))

        for num_caisse in CAISSES_CRITIQUES:
            if caisse_tenue(num_caisse):
                vide_depuis.pop(num_caisse, None)
            else:
                vide_depuis.setdefault(num_caisse, i)

        for num_caisse in ORDRE_CAISSES:
            if num_caisse not in CAISSES_CRITIQUES or caisse_tenue(num_caisse):
                continue
            # Un repli deplace quelqu'un qui vient de s'installer : on ne se l'autorise
            # que sur C1/C2, ou une fois le trou tolere epuise.
            repli_autorise = (num_caisse in CAISSES_ININTERROMPUES
                              or i - vide_depuis.get(num_caisse, i) >= TROU_TOLERE)
            # En fin de journee on accepte un poste plus court que DUREE_MIN_CAISSE
            # plutot que de fermer la caisse.
            duree_utile = min(DUREE_MIN_CAISSE, len(slots) - i)

            def trouver_source(niveau):
                """niveau 0 = solution stable, 1 = repli, 2 = urgence (C1/C2, qui
                ne doivent jamais fermer : on accepte alors un poste court)."""
                candidats = []
                rang_cible = ORDRE_CAISSES.index(num_caisse)
                for autre in reversed(ORDRE_CAISSES):
                    # la source doit etre strictement moins prioritaire que la cible.
                    # On ne puise dans les autres caisses critiques que pour C1/C2 :
                    # ailleurs, echanger C13 contre C14 ne ferait que deplacer le trou.
                    if ORDRE_CAISSES.index(autre) <= rang_cible:
                        continue
                    if autre in CAISSES_CRITIQUES and num_caisse not in CAISSES_ININTERROMPUES:
                        continue
                    nom_s = titulaire.get(autre)
                    if nom_s is None or matrice_planning[i][map_employes[nom_s]] != f"C{autre}":
                        continue
                    # contraintes dures, jamais relachees
                    if not caisse_autorisee(num_caisse, infos_de(nom_s)):
                        continue
                    if sont_adjacentes(autre, num_caisse):
                        continue
                    # la phase B a pu l'installer ailleurs a ce creneau : on compare
                    # aussi a la caisse qu'il tenait avant, sinon il glisse vers la
                    # caisse mitoyenne en deux temps (C2 -> C13 -> C1)
                    precedente = derniere_caisse(nom_s, i)
                    if precedente is not None and sont_adjacentes(precedente, num_caisse):
                        continue
                    restante = presence_restante(nom_s, i)
                    # un poste doit tenir au moins 1h... sauf urgence sur C1/C2
                    if niveau < 2 and restante < min(4, len(slots) - i):
                        continue
                    # le deplacer alors qu'il vient de s'asseoir laisserait un bloc
                    # isole de 15 min sur la caisse qu'il quitte
                    if niveau < 2 and i - depuis_slot.get(nom_s, i) < DUREE_MIN_BLOC_CAISSE:
                        continue
                    # confort : ne pas deplacer quelqu'un qui vient de s'installer,
                    # ni pour un poste plus court que DUREE_MIN_CAISSE
                    if niveau < 1:
                        if i - depuis_slot.get(nom_s, i) < duree_utile:
                            continue
                        if restante < duree_utile:
                            continue
                    candidats.append((autre, restante))
                if not candidats:
                    return None
                # a niveau egal, on prend celui qui tiendra le poste le plus longtemps,
                # puis la caisse la moins prioritaire (fin de ORDRE_CAISSES).
                candidats.sort(key=lambda c: (-c[1], -ORDRE_CAISSES.index(c[0])))
                return candidats[0][0]

            source = trouver_source(0)
            if source is None and repli_autorise:
                source = trouver_source(1)
            if source is None and num_caisse in CAISSES_ININTERROMPUES:
                source = trouver_source(2)
            if source is None:
                continue
            nom = titulaire.pop(source)
            matrice_planning[i][map_employes[nom]] = f"C{num_caisse}"
            titulaire[num_caisse] = nom   # remplace le titulaire en pause longue
            depuis_slot[nom] = i
            poste_habituel[nom] = num_caisse
            vide_depuis.pop(num_caisse, None)


    # --- ETAPE 6 : POLYVALENT ---
    for nom in employes_presents:
        indices_libres = get_available_slots_indices(nom, presence, matrice_planning, map_employes)
        if indices_libres:
            blocs_continus = [[indices_libres[0]]]
            for k in range(1, len(indices_libres)):
                if indices_libres[k] == indices_libres[k-1] + 1: 
                    blocs_continus[-1].append(indices_libres[k])
                else: 
                    blocs_continus.append([indices_libres[k]])
                    
            for bloc in blocs_continus: 
                assigner_tache(nom, "POLY", bloc[0], len(bloc))

    infos_pauses = f"Mission Pause Matin : {math.ceil((minutes_matin + MARGE_MISSION_PAUSE_MIN)/15)*15} min | Aprem : {math.ceil((minutes_aprem + MARGE_MISSION_PAUSE_MIN)/15)*15} min"
    
    return {
        "slots": slots,
        "employes_presents": employes_presents,
        "matrice_planning": matrice_planning,
        "plan_data": plan_data,
        "infos_pauses": infos_pauses,
        "closer_veille": closer_veille,
        "emp_map": map_employes
    }
# --- PHASE 2 : SOLVEUR WFM (OR-Tools) --- 
def generer_horaires_mensuels(employes, jours_du_mois):
    # Implémentation future du solveur OR-Tools
    # model = cp_model.CpModel()
    # work_vars = ...

    # Contrainte stricte : Jours de repos fixes
    # for employe in employes:
    #     repos = employe.get('repos_fixes', '').split(',')
    #     for jour_idx, jour_nom in jours_du_mois:
    #         if jour_nom in repos:
    #             # Le solveur doit forcer toutes ses variables de travail de la journée à 0
    #             # for t in tranches:
    #             #     model.Add(work_vars[(employe['id'], jour_idx, t)] == 0)
    pass
