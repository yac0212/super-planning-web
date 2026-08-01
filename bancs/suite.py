# -*- coding: utf-8 -*-
"""Suite de 10 scenarios : sur-effectif, sous-effectif, interim, handicap, etc.
Chaque run repart d'une base vierge. Verifie les invariants metier."""
import sys, os, shutil, time
SANDBOX = os.path.dirname(os.path.abspath(__file__))
PROJ = r"C:\Users\ayach\.gemini\antigravity\scratch\planning_app"
os.environ['DATA_DIR'] = SANDBOX
sys.path.insert(0, SANDBOX)
sys.path.insert(1, PROJ)

PRISTINE = os.path.join(SANDBOX, "pristine.db")
LIVE = os.path.join(SANDBOX, "supermarche_dev.db")

import database as db
import algo, algo_orig

# La suite verifie les INVARIANTS du glouton : l'optimisation globale est
# desactivee ici, elle est mesuree separement par optim.py
algo.ESSAIS_OPTIM = 0

J = lambda a, b, c, d: {"ms": a, "me": b, "aes": c, "aee": d}
MATIN = lambda a, b: J(a, b, "", "")
APREM = lambda a, b: J("", "", a, b)
PLEIN = lambda a, b, c, d: J(a, b, c, d)

CDI = ["AIT ELHADJ Sonia", "AYACHE Yacine", "BERTHE Sebastien", "BRASSAC Alexandra",
       "CHARPENTIER Nora", "COLONDON Ethan", "GOURGEOIS Nathalie", "MIATOLOKA Cecilia",
       "MOYSAN Christelle", "NEJMI Anas", "POWELL Laura", "SY Diariata"]
ETU = ["BARDON Maia", "BECHICHI Dalya", "KIATA Corneille", "KEPSEU Mandela"]
INTERIM = [f"Interimaire {n}" for n in range(1, 7)] + ["Intérimaire 7", "Intérimaire 8"]
RESTREINTS = ["PIERQUIN Alicia", "SOUSA MARTINS André"]   # Caisse Impaire Uniq.

# ---------------------------------------------------------------- scenarios
def sc_sureffectif():
    """22 personnes pour 14 caisses : plus d'operateurs que de postes."""
    s = {}
    for n in CDI + ETU:
        s[n] = PLEIN("09:00", "13:00", "14:00", "20:00")
    for n in INTERIM[:6]:
        s[n] = PLEIN("09:00", "13:00", "14:00", "20:00")
    return s

def sc_sous_effectif():
    """4 personnes seulement : moins d'operateurs que de caisses critiques."""
    return {n: PLEIN("09:00", "13:00", "14:00", "20:00") for n in CDI[:4]}

def sc_effectif_minimal():
    """2 personnes : C1 et C2 doivent absorber tout le monde."""
    return {CDI[0]: PLEIN("09:00", "13:00", "14:00", "20:00"),
            CDI[1]: PLEIN("09:00", "13:00", "14:00", "20:00")}

def sc_que_interimaires():
    """Aucun CDI : que des interimaires (tous restriction_cls=1)."""
    return {n: PLEIN("09:00", "13:00", "14:00", "20:00") for n in INTERIM[:8]}

def sc_majorite_interim():
    """2 CDI encadrant 8 interimaires."""
    s = {n: PLEIN("09:00", "13:00", "14:00", "20:00") for n in CDI[:2]}
    s.update({n: PLEIN("10:00", "14:00", "15:00", "19:00") for n in INTERIM[:8]})
    return s

def sc_rotation_stricte():
    """Aucun chevauchement : equipe du matin puis equipe de l'apres-midi."""
    s = {n: MATIN("09:00", "14:00") for n in CDI[:7]}
    s.update({n: APREM("14:00", "20:00") for n in CDI[7:] + ETU[:2]})
    return s

def sc_arrivees_echelonnees():
    """Montee en charge : 1 personne de plus toutes les 30 min."""
    s = {}
    for k, n in enumerate(CDI + ETU[:2]):
        h = 9 + (k // 2)
        m = "30" if k % 2 else "00"
        s[n] = PLEIN(f"{h:02d}:{m}", "13:00", "14:00", "20:00")
    return s

def sc_departs_echelonnes():
    """Fermeture progressive : depart toutes les 30 min a partir de 16h."""
    s = {}
    for k, n in enumerate(CDI + ETU[:2]):
        h = 16 + (k // 2)
        m = "30" if k % 2 else "00"
        fin = f"{min(h,19):02d}:{m}"
        s[n] = PLEIN("09:00", "13:00", "14:00", fin)
    return s

def sc_handicap_massif():
    """Beaucoup de restrictions paire/impaire simultanees."""
    s = {n: PLEIN("09:00", "13:00", "14:00", "20:00") for n in CDI[:10] + RESTREINTS}
    return s

def sc_dimanche():
    """Dimanche : double shift CLS impose, pas de pause apres-midi."""
    return {n: PLEIN("09:00", "13:00", "14:00", "20:00") for n in CDI + ETU[:2]}

def sc_coupures_multiples():
    """Coupures midi decalees, beaucoup de va-et-vient."""
    s = {}
    for k, n in enumerate(CDI + ETU):
        deb = f"{9 + k % 3:02d}:00"
        cm = f"{12 + k % 3:02d}:30"
        rep = f"{13 + k % 3:02d}:30"
        s[n] = PLEIN(deb, cm, rep, "20:00")
    return s

SCENARIOS = [
    ("01 sur-effectif 22 pers.",  "30/07/2026", sc_sureffectif, None),
    ("02 sous-effectif 4 pers.",  "30/07/2026", sc_sous_effectif, None),
    ("03 effectif minimal 2",     "30/07/2026", sc_effectif_minimal, None),
    ("04 que des interimaires",   "30/07/2026", sc_que_interimaires, None),
    ("05 majorite interim",       "30/07/2026", sc_majorite_interim, None),
    ("06 rotation stricte",       "30/07/2026", sc_rotation_stricte, None),
    ("07 arrivees echelonnees",   "30/07/2026", sc_arrivees_echelonnees, None),
    ("08 departs echelonnes",     "30/07/2026", sc_departs_echelonnes, None),
    ("09 handicap massif",        "30/07/2026", sc_handicap_massif, "handicap"),
    ("10 dimanche",               "02/08/2026", sc_dimanche, None),
    ("11 coupures multiples",     "30/07/2026", sc_coupures_multiples, None),
]

# ---------------------------------------------------------------- invariants
ININT = {1, 2}
CRIT = {1, 2, 13, 14}
PAIRES = [[1, 2], [13, 14], [5, 6], [3, 4], [7, 8], [9, 10], [11, 12]]
TROU_MAX_TOLERE = 6   # 1h30


def num_de(t):
    return int(t[1:]) if t.startswith("C") and t != "CLS" else None


def verifier(res, cache, scen):
    """Retourne (liste d'anomalies, metriques)."""
    slots, noms, M = res['slots'], res['employes_presents'], res['matrice_planning']
    from datetime import datetime
    anomalies = []

    # presence reelle par employe
    pres = {}
    for n in noms:
        t = scen[n]
        pres[n] = []
        for s in slots:
            h = datetime.strptime(s, "%H:%M")
            ok = False
            for a, b in ((t['ms'], t['me']), (t['aes'], t['aee'])):
                if a and b and datetime.strptime(a, "%H:%M") <= h < datetime.strptime(b, "%H:%M"):
                    ok = True
            pres[n].append(ok)

    for c, n in enumerate(noms):
        restr = cache.get(n, {}).get('restriction_handicap', 'Aucun')
        prev = None
        for i, s in enumerate(slots):
            t = M[i][c]
            if t and not pres[n][i]:
                anomalies.append(f"{s} {n} affecte '{t}' hors de ses heures")
            num = num_de(t)
            if num and restr != 'Aucun':
                pair = num % 2 == 0
                if (restr == "Caisse Impaire Uniq." and pair) or (restr == "Caisse Paire Uniq." and not pair):
                    anomalies.append(f"{s} {n} ({restr}) sur C{num}")
            if num and prev and prev != num and any(prev in p and num in p for p in PAIRES):
                anomalies.append(f"{s} {n} glisse de C{prev} vers la caisse mitoyenne C{num}")
            if num:
                prev = num
            elif t != "PAUSE":
                prev = None

    # trous sur les caisses prioritaires
    trous = {n: 0 for n in CRIT}
    trou_max = {n: 0 for n in CRIT}
    ORDRE = [1, 2, 13, 14, 5, 6, 3, 4, 7, 8, 9, 10, 11, 12]
    for i, s in enumerate(slots):
        occ = set(filter(None, (num_de(M[i][c]) for c in range(len(noms)))))
        for k in CRIT:
            # une caisse ne peut etre comblee que depuis une caisse strictement
            # moins prioritaire ; C13/C14 ne puisent pas dans les autres critiques
            source_possible = {a for a in occ if ORDRE.index(a) > ORDRE.index(k)}
            # une caisse mitoyenne n'est jamais une source valable (regle anti-glissement),
            # et C13/C14 ne puisent pas dans les autres caisses critiques
            source_possible -= {a for a in source_possible
                                if any(a in p and k in p for p in PAIRES)}
            if k not in ININT:
                source_possible -= CRIT
            if k in occ or not source_possible:
                trous[k] = 0
                continue
            trous[k] += 1
            trou_max[k] = max(trou_max[k], trous[k])
            if k in ININT:
                anomalies.append(f"{s} C{k} fermee alors que C{sorted(source_possible)} sont tenues")
            elif trous[k] > TROU_MAX_TOLERE:
                anomalies.append(f"{s} C{k} fermee depuis {trous[k]*15} min (max tolere {TROU_MAX_TOLERE*15})")

    # metriques de stabilite
    switch = mid = 0
    stints = []
    couv = 0
    for c, n in enumerate(noms):
        seq = [M[i][c] for i in range(len(slots))]
        couv += sum(1 for t in seq if num_de(t))
        st, cur, ln = [], None, 0
        for t in seq:
            if t == "PAUSE":
                continue
            if num_de(t):
                if t == cur:
                    ln += 1
                else:
                    if cur: st.append((cur, ln))
                    cur, ln = t, 1
            else:
                if cur: st.append((cur, ln))
                cur, ln = None, 0
        if cur: st.append((cur, ln))
        merged = []
        for cc, l in st:
            if merged and merged[-1][0] == cc: merged[-1] = (cc, merged[-1][1] + l)
            else: merged.append((cc, l))
        switch += max(0, len(merged) - 1)
        stints += [l for _, l in merged]
        # bloc isole de 15 min : interdit sauf sur C1/C2 (qui ne ferment jamais)
        for cc, l in merged:
            if l == 1 and int(cc[1:]) not in ININT:
                anomalies.append(f"{n} : bloc isole de 15 min sur {cc}")
        for i in range(1, len(slots)):
            a, b = num_de(seq[i-1]), num_de(seq[i])
            if a and b and a != b:
                mid += 1

    # meme caisse matin ET apres-midi hors C1/C2/C13/C14 : mal vecu par l'equipe
    meme_caisse_mj = 0
    for c, nom in enumerate(noms):
        avant, apres, vu_coupure = set(), set(), False
        for i in range(len(slots)):
            if not pres[nom][i]:
                if avant:
                    vu_coupure = True
                continue
            n = num_de(M[i][c])
            if n:
                (apres if vu_coupure else avant).add(n)
        meme_caisse_mj += len((avant & apres) - CRIT)

    # nombre de releves par caisse : combien de titulaires successifs se
    # succedent sur une meme caisse dans la journee
    releves = 0
    for k in range(1, 15):
        occ = []
        for i in range(len(slots)):
            qui = next((noms[c] for c in range(len(noms)) if num_de(M[i][c]) == k), None)
            if qui and (not occ or occ[-1] != qui):
                occ.append(qui)
        releves += max(0, len(occ) - 1)

    return anomalies, dict(
        switch=switch, mid=mid, couv=couv, mj=meme_caisse_mj, rel=releves,
        avg=(sum(stints) / len(stints) * 15) if stints else 0,
        micro=sum(1 for l in stints if l < 6),
        tmax12=max(trou_max[1], trou_max[2]) * 15,
        tmax1314=max(trou_max[13], trou_max[14]) * 15,
        n=len(noms))


def lancer(mod, date, scen, variante):
    shutil.copy(PRISTINE, LIVE)
    cache = {e['nom']: e for e in db.get_employes()}
    if variante == "handicap":
        # tri : l'attribution des restrictions ne doit pas dependre de l'ordre du dict,
        # sinon le test de determinisme compare deux configurations differentes
        for k, nom in enumerate(sorted(scen)):
            if nom not in RESTREINTS and k % 3 == 0:
                cache[nom] = dict(cache.get(nom, {}), restriction_handicap=
                                  "Caisse Paire Uniq." if k % 2 else "Caisse Impaire Uniq.")
    t0 = time.time()
    res = mod.run_algo(date, scen, cache)
    return res, cache, (time.time() - t0) * 1000


# ---------------------------------------------------------------- execution
print(f"{'scenario':28s} {'algo':7s} {'n':>3s} {'chgt':>5s} {'depl':>5s} {'releves':>8s} "
      f"{'memeMJ':>7s} {'moy':>6s} {'couv':>5s} {'ANO':>4s} {'ms':>6s}")
print("-" * 108)

total_ano = {"ANCIEN": 0, "NOUVEAU": 0}
detail_ano = {}

for label, date, fabrique, variante in SCENARIOS:
    scen = fabrique()
    for tag, mod in (("ANCIEN", algo_orig), ("NOUVEAU", algo)):
        res, cache, ms = lancer(mod, date, scen, variante)
        if "error" in res:
            print(f"{label:28s} {tag:7s} ERREUR : {res['error']}")
            continue
        ano, m = verifier(res, cache, scen)
        total_ano[tag] += len(ano)
        if ano:
            detail_ano.setdefault((label, tag), ano)
        print(f"{label:28s} {tag:7s} {m['n']:3d} {m['switch']:5d} {m['mid']:5d} {m['rel']:8d} "
              f"{m['mj']:7d} {m['avg']:5.0f}m {m['couv']:5d} {len(ano):4d} {ms:6.0f}")
    print()

print(f"TOTAL ANOMALIES  ancien={total_ano['ANCIEN']}  nouveau={total_ano['NOUVEAU']}\n")

for (label, tag), ano in detail_ano.items():
    print(f"--- {label} [{tag}] : {len(ano)} anomalies ---")
    vus = {}
    for a in ano:
        cle = a.split(' ', 1)[1][:60]
        vus.setdefault(cle, []).append(a.split(' ', 1)[0])
    for cle, heures in list(vus.items())[:6]:
        print(f"    {cle}  x{len(heures)}  ({heures[0]}...{heures[-1]})")
    if len(vus) > 6:
        print(f"    ... et {len(vus)-6} autres motifs")
    print()

# determinisme sur tous les scenarios
print("Determinisme (ordre de saisie inverse) :")
for label, date, fabrique, variante in SCENARIOS:
    scen = fabrique()
    inv = {k: scen[k] for k in reversed(list(scen))}
    r1, _, _ = lancer(algo, date, scen, variante)
    r2, _, _ = lancer(algo, date, inv, variante)
    g1 = {n: [r1['matrice_planning'][i][r1['employes_presents'].index(n)] for i in range(len(r1['slots']))]
          for n in r1['employes_presents']}
    g2 = {n: [r2['matrice_planning'][i][r2['employes_presents'].index(n)] for i in range(len(r2['slots']))]
          for n in r2['employes_presents']}
    d = sum(1 for n in g1 for a, b in zip(g1[n], g2[n]) if a != b)
    print(f"  {label:28s} {d} cellule(s) differente(s)")

shutil.copy(PRISTINE, LIVE)
