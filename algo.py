import math
from datetime import datetime, timedelta
import os
import database as db

TIME_STEP = 15  
MARGE_MISSION_PAUSE_MIN = 30 
BLACKLIST_CLS_PERMANENT = ["jean marc", "jessica", "emmanuel"]

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

def is_same_person(nom1, nom2): 
    return nom1.lower() in nom2.lower() or nom2.lower() in nom1.lower()
    
def is_blacklisted(nom): 
    return any(b in nom.lower() for b in BLACKLIST_CLS_PERMANENT)

def get_penalite(nom, dictionnaire_hierarchie):
    for nom_cle, valeur in dictionnaire_hierarchie.items(): 
        if nom_cle in nom.lower(): 
            return valeur
    return 0

def generate_timeline():
    start_time = datetime.strptime("09:00", "%H:%M")
    end_time = datetime.strptime("20:00", "%H:%M")
    timeline = []
    current_time = start_time
    while current_time < end_time: 
        timeline.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=TIME_STEP)
    return timeline

def get_available_slots_indices(nom, plan_data, slots, matrice, map_employes):
    indices_libres = []
    for i, heure_str in enumerate(slots):
        heure_obj = datetime.strptime(heure_str, "%H:%M")
        present = False
        for p in plan_data:
            if p['nom'] == nom:
                matin_ok = p['matin'][0] and p['matin'][1] and p['matin'][0] <= heure_obj < p['matin'][1]
                aprem_ok = p['aprem'][0] and p['aprem'][1] and p['aprem'][0] <= heure_obj < p['aprem'][1]
                if matin_ok or aprem_ok:
                    present = True
        
        if present and not matrice[i][map_employes[nom]]: 
            indices_libres.append(i)
    return indices_libres

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
    
    def assigner_tache(nom, tache, start_idx, length):
        colonne = map_employes[nom]
        for k in range(start_idx, start_idx + length): 
            if k < len(slots): 
                matrice_planning[k][colonne] = tache

    compteur_cls = {nom: 0 for nom in employes_presents}
    closer_assigne = None

    # --- ETAPE 0 : LE CLOSER ---
    if not est_dimanche:
        start_soir_idx = next((i for i, s in enumerate(slots) if s.startswith("17:00")), None)
        if start_soir_idx is not None:
            candidats_disponibles = []
            for nom in employes_presents:
                infos = cache_emp[nom]
                if infos['restriction_cls'] or infos['statut'] == "Interimaire" or is_blacklisted(nom) or is_same_person(nom, closer_veille): 
                    continue
                    
                indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                if start_soir_idx in indices_libres:
                    longueur = get_continuous_block(indices_libres, start_soir_idx)
                    if longueur >= 8: 
                        candidats_disponibles.append((nom, longueur))
                        
            candidats_disponibles.sort(key=lambda x: (1 if "yacine" in x[0].lower() else 0, -x[1]))
            
            if not candidats_disponibles:
                for nom in employes_presents:
                    if not cache_emp[nom]['restriction_cls']:
                        indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                        if start_soir_idx in indices_libres: 
                            candidats_disponibles.append((nom, get_continuous_block(indices_libres, start_soir_idx)))
                candidats_disponibles.sort(key=lambda x: -x[1])
                
            if candidats_disponibles:
                gagnant, longueur_bloc = candidats_disponibles[0]
                assigner_tache(gagnant, "CLS", start_soir_idx, longueur_bloc)
                compteur_cls[gagnant] += 1
                closer_assigne = gagnant
                db.save_historique_fermeture(date_saisie, gagnant)

    # --- ETAPE 1 : LES PAUSES ---
    slots_pause_matin = math.ceil((minutes_matin + MARGE_MISSION_PAUSE_MIN) / 15)
    if slots_pause_matin > 0:
        cur_idx = 6 
        restant = slots_pause_matin
        while restant > 0 and cur_idx < 20:
            candidats_disponibles = []
            for nom in employes_presents:
                if "andré" in nom.lower(): continue 
                
                indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                if cur_idx in indices_libres: 
                    candidats_disponibles.append({"nom": nom, "longueur": get_continuous_block(indices_libres, cur_idx)})
                    
            if not candidats_disponibles: 
                cur_idx += 1
                continue
                
            def score_pause(c):
                infos = cache_emp[c['nom']]
                score = 1000 if infos['statut'] != "Interimaire" else 0
                if c['nom'] == closer_assigne: score -= 5000
                return score + min(c['longueur'], restant) * 10 - db.get_mission_score(c['nom']) * 5
                
            candidats_disponibles.sort(key=score_pause, reverse=True)
            gagnant = candidats_disponibles[0]
            
            if gagnant["nom"] == closer_assigne and score_pause(gagnant) < 0: 
                cur_idx += 1
                continue
                
            longueur_assignee = min(gagnant['longueur'], restant)
            assigner_tache(gagnant['nom'], "PAUSE", cur_idx, longueur_assignee)
            db.inc_mission_score(gagnant['nom'])
            cur_idx += longueur_assignee
            restant -= longueur_assignee

    slots_pause_aprem = math.ceil((minutes_aprem + MARGE_MISSION_PAUSE_MIN) / 15)
    if slots_pause_aprem > 0 and not est_dimanche:
        restant = slots_pause_aprem
        cur_idx = max(24, 40 - restant)
        while restant > 0 and cur_idx < 44:
            candidats_disponibles = []
            for nom in employes_presents:
                if "andré" in nom.lower(): continue 
                
                indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                if cur_idx in indices_libres: 
                    candidats_disponibles.append({"nom": nom, "longueur": get_continuous_block(indices_libres, cur_idx)})
                    
            if not candidats_disponibles: 
                cur_idx += 1
                continue
                
            def score_pause_a(c):
                infos = cache_emp[c['nom']]
                score = 1000 if infos['statut'] != "Interimaire" else 0
                if c['nom'] == closer_assigne: score -= 5000
                return score + min(c['longueur'], restant) * 10 - db.get_mission_score(c['nom']) * 5
                
            candidats_disponibles.sort(key=score_pause_a, reverse=True)
            gagnant = candidats_disponibles[0]
            
            if gagnant["nom"] == closer_assigne and score_pause_a(gagnant) < 0: 
                cur_idx += 1
                continue
                
            longueur_assignee = min(gagnant['longueur'], restant)
            assigner_tache(gagnant['nom'], "PAUSE", cur_idx, longueur_assignee)
            db.inc_mission_score(gagnant['nom'])
            cur_idx += longueur_assignee
            restant -= longueur_assignee

    # --- ETAPE 2 : CLS JOURNÉE ---
    if est_dimanche:
        for start_s, length_s in [(2, 8), (10, 7)]:
            candidats_disponibles = []
            for nom in employes_presents:
                if cache_emp[nom]['restriction_cls'] or is_blacklisted(nom) or compteur_cls[nom] >= 1: 
                    continue
                indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                l = get_continuous_block(indices_libres, start_s)
                if l > 0: 
                    candidats_disponibles.append((nom, l))
                    
            candidats_disponibles.sort(key=lambda x: (1 if "yacine" in x[0].lower() else 0, abs(x[1] - length_s)))
            if candidats_disponibles: 
                assigner_tache(candidats_disponibles[0][0], "CLS", start_s, min(candidats_disponibles[0][1], length_s))
                compteur_cls[candidats_disponibles[0][0]] += 1
    else:
        for i, ts in enumerate(slots):
            if int(ts.split(':')[0]) >= 17: break
            
            if not any(matrice_planning[i][x] == "CLS" for x in range(len(employes_presents))):
                candidats_disponibles = []
                for nom in employes_presents:
                    if nom == closer_assigne or cache_emp[nom]['restriction_cls'] or is_blacklisted(nom) or compteur_cls[nom] >= 1: 
                        continue
                    indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                    if i in indices_libres: 
                        candidats_disponibles.append((nom, get_continuous_block(indices_libres, i)))
                        
                candidats_disponibles.sort(key=lambda x: (1 if x[1] < 8 else 0, 5000 if "yacine" in x[0].lower() else 0))
                if candidats_disponibles: 
                    assigner_tache(candidats_disponibles[0][0], "CLS", i, min(candidats_disponibles[0][1], 8))
                    compteur_cls[candidats_disponibles[0][0]] += 1

    # --- ETAPE 3 : CAISSES 1, 2, 13, 14 (PRIORITÉ INTÉRIM ABSOLUE) ---
    for num_caisse in [1, 2, 13, 14]:
        nom_caisse = f"C{num_caisse}"
        dict_penalite = HIERARCHIE_PENALITE_C1_C2 if num_caisse in [1, 2] else HIERARCHIE_PENALITE_C13_C14
        
        for i, ts in enumerate(slots):
            if any(matrice_planning[i][x] == nom_caisse for x in range(len(employes_presents))): 
                continue
                
            candidats_disponibles = []
            for nom in employes_presents:
                indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                if i in indices_libres: 
                    candidats_disponibles.append((nom, get_continuous_block(indices_libres, i)))
                    
            def score_priorite_caisse(c):
                nom_c = c[0]
                longueur_c = c[1]
                infos = cache_emp.get(nom_c, {'statut': 'CDI', 'restriction_handicap': 'Aucun'})
                penalite = get_penalite(nom_c, dict_penalite)
                
                # Bonus absolu (-100000) pour imposer l'intérim
                if infos.get('statut') == "Interimaire": 
                    penalite -= 100000 
                    
                est_pair = (num_caisse % 2 == 0)
                if (infos.get('restriction_handicap') == "Caisse Impaire Uniq." and est_pair) or \
                   (infos.get('restriction_handicap') == "Caisse Paire Uniq." and not est_pair): 
                    penalite += 999999
                    
                return (penalite, -longueur_c)
                
            candidats_disponibles.sort(key=score_priorite_caisse)
            if candidats_disponibles and score_priorite_caisse(candidats_disponibles[0])[0] < 900000: 
                assigner_tache(candidats_disponibles[0][0], nom_caisse, i, candidats_disponibles[0][1])

    # --- ETAPE 4 : CAISSES 5 ET 6 (PRIORITÉ SECONDAIRE) ---
    for num_caisse in [5, 6]:
        nom_caisse = f"C{num_caisse}"
        for i, ts in enumerate(slots):
            if any(matrice_planning[i][x] == nom_caisse for x in range(len(employes_presents))): 
                continue
                
            candidats_disponibles = []
            for nom in employes_presents:
                indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                if i in indices_libres: 
                    candidats_disponibles.append((nom, get_continuous_block(indices_libres, i)))
                    
            def score_caisse_5_6(c):
                nom_c = c[0]
                longueur_c = c[1]
                infos = cache_emp.get(nom_c, {'statut': 'CDI', 'restriction_handicap': 'Aucun'})
                penalite = 0
                
                est_pair = (num_caisse % 2 == 0)
                if (infos.get('restriction_handicap') == "Caisse Impaire Uniq." and est_pair) or \
                   (infos.get('restriction_handicap') == "Caisse Paire Uniq." and not est_pair): 
                    penalite += 999999
                return (penalite, -longueur_c)
                
            candidats_disponibles.sort(key=score_caisse_5_6)
            if candidats_disponibles and score_caisse_5_6(candidats_disponibles[0])[0] < 900000: 
                assigner_tache(candidats_disponibles[0][0], nom_caisse, i, candidats_disponibles[0][1])

    # --- ETAPE 5 : LE RESTE DES CAISSES ---
    for num_caisse in [3, 4, 7, 8, 9, 10, 11, 12]:
        nom_caisse = f"C{num_caisse}"
        for i, ts in enumerate(slots):
            if any(matrice_planning[i][x] == nom_caisse for x in range(len(employes_presents))): 
                continue
                
            candidats_disponibles = []
            for nom in employes_presents:
                indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
                if i in indices_libres: 
                    candidats_disponibles.append((nom, get_continuous_block(indices_libres, i)))
                    
            def score_reste(c):
                infos = cache_emp.get(c[0], {'statut': 'CDI', 'restriction_handicap': 'Aucun'})
                penalite = 0
                est_pair = (num_caisse % 2 == 0)
                if (infos.get('restriction_handicap') == "Caisse Impaire Uniq." and est_pair) or \
                   (infos.get('restriction_handicap') == "Caisse Paire Uniq." and not est_pair): 
                    penalite += 999999
                return (penalite, -c[1])
                
            candidats_disponibles.sort(key=score_reste)
            if candidats_disponibles and score_reste(candidats_disponibles[0])[0] < 900000: 
                assigner_tache(candidats_disponibles[0][0], nom_caisse, i, candidats_disponibles[0][1])
    
    # --- ETAPE 6 : POLYVALENT ---
    for nom in employes_presents:
        indices_libres = get_available_slots_indices(nom, plan_data, slots, matrice_planning, map_employes)
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
