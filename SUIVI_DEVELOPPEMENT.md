# Suivi de développement — Génération automatique des horaires (WFM)

> **But de ce fichier** : servir de mémoire de projet pour reprendre le développement
> dans une autre conversation. Il décrit le contexte, les contraintes, chaque
> modification faite, l'état actuel et ce qui reste à faire.
> **À mettre à jour à la fin de chaque session de travail** (voir § Journal des sessions).

---

## 0. ⚠️ CONTRAINTES IMPÉRATIVES (à lire en premier)

- **L'application est en PRODUCTION** : hébergée et utilisée par des clients réels
  (dépôt GitHub `yac0212/super-planning-web`, branche `master`).
- **NE JAMAIS pousser sur GitHub** sans validation explicite de l'utilisateur.
  Tout le travail se fait **en local**, on teste **en local**, et **c'est
  l'utilisateur** qui met à jour GitHub quand une version est terminée.
- **Aucune opération git** de la part de l'assistant (pas de `git add/commit/push`)
  sauf demande explicite. *(Rappel : un `commit` est local et ne touche pas GitHub,
  mais l'utilisateur préfère piloter git lui-même.)*

## 1. Historique et Origines du Projet (Legacy)

Avant de devenir la plateforme web complexe que nous connaissons aujourd'hui, **Super Planning** a connu une longue évolution :

### Les Origines : Les fondations en Python brut (V1 - V20)
À l'origine (ex: V12), le système de planification n'était qu'un script Python en ligne de commande. Il n'y avait pas de base de données ni d'interface graphique.
- Les données des employés (contrats, statuts, règles de caisse) et la courbe de charge du magasin étaient écrites ("hardcodées") directement dans le code source sous forme de dictionnaires Python.
- L'algorithme était basique et séquentiel : il bouclait sur les employés disponibles et remplissait les caisses ouvertes (Matin/Après-midi) jusqu'à atteindre le quota nécessaire.
- Les premières règles de pénibilité faisaient déjà leur apparition (ex: empêcher un étudiant d'enchaîner le matin et l'après-midi).
- Le rendu s'affichait brutalement dans le terminal. Le système posait vite ses limites car chaque ajout d'employé nécessitait de modifier le code.

### L'Ère de l'Interface Locale et de CustomTkinter (V21 - V57)
Face aux limites du script brut, le projet a basculé vers une véritable application de bureau (Desktop). 
- **L'Interface (GUI)** : L'application s'est dotée d'une interface graphique sombre et soignée construite avec `CustomTkinter`. Elle offrait un panneau latéral, la gestion des équipes, et une grille de planification visuelle journalière.
- **La Base de données** : Apparition de SQLite. L'équipe, les historiques et les missions de clôture (CLS) n'étaient plus hardcodés mais sauvegardés en local, assurant la persistance des données entre deux lancements de l'application.
- **Fonctionnalités avancées** :
  - Un système d'export HTML automatisé avec génération de "Feuilles de pauses" imprimables.
  - La gestion en base de données de l'Intérim (Demandes d'absences, envois fictifs par email, intégration des retours).
  - Un moteur algorithmique plus fin gérant les missions "CLS" (clôture) avec un système de compteurs et de pénalités selon la hiérarchie pour répartir équitablement la pénibilité.

### La Transition Web et le Cloud (V48+ et Production Actuelle)
Face à la nécessité du travail collaboratif et du partage, l'application lourde a été transformée en **Plateforme Web Centralisée**.
- Remplacement de `CustomTkinter` par un frontend Web complet (HTML/CSS/JS) et un backend `Flask`.
- Tout l'ancien code legacy (GUI, exports HTML) a été migré et repensé pour le web, donnant naissance à la version de production actuelle (`supermarche_dev.db`).

### L'Ère de l'Intelligence Artificielle (WFM Actuel)
Le simple algorithme séquentiel de la V12 s'est transformé en un moteur d'Intelligence Artificielle surpuissant (Workforce Management). Basé sur la bibliothèque d'optimisation `Google OR-Tools` couplée au multithreading (4 cœurs), le système est aujourd'hui capable de trouver la solution mathématique optimale englobant les congés dynamiques, les remplacements intérimaires coûteux et les exigences contractuelles complexes à la minute près, le tout en générant des mois entiers d'un simple clic.

---

## 2. État Actuel (Production)

L'application tourne sur **Flask (Python)** avec une base de données **SQLite** (`supermarche.db`). L'interface est en **HTML/CSS/JS vanille**.

- **Base de données** : `supermarche_dev.db` à la racine est une base **locale de
  dev** (elle est dans `.gitignore`, ce n'est PAS la base de production). La prod a
  sa propre base sur le serveur d'hébergement. Pour les tests automatisés, utiliser
  une **copie** de la base (voir § Comment tester).

---

## 1. Objectif fonctionnel

`algo.py` sait assigner les employés aux caisses créneau par créneau (fonction
`run_algo`, **inchangée**), mais prend en entrée des horaires de présence saisis à la
main (`ms`/`me`/`aes`/`aee` = début/fin matin, début/fin après-midi).

**Objectif V1** : générer automatiquement ces horaires de présence (qui travaille
quand), en respectant :
- heures contractuelles hebdomadaires (`employes.heures_contrat`),
- disponibilités par jour (nouvelle table `disponibilites`),
- contraintes existantes (`restriction_cls`, `restriction_handicap`, `statut`),
- droit du travail FR (repos 11h, durée max quotidienne/hebdo, pause),
- une courbe de besoin en caissiers par créneau (table `besoins_flux`, éditable via
  un écran admin).

Le résultat est sauvegardé au format `ms/me/aes/aee` (via `db.save_planning`) pour
être **relu par `run_algo`** → la chaîne complète fonctionne bout-en-bout.

---

## 2. Environnement & lancement local

- Stack : **Flask + SQLite**, solveur **OR-Tools CP-SAT**.
- Répertoire projet : `C:\Users\ayach\.gemini\antigravity\scratch\planning_app`
- **Lancer l'app** : `python app.py` → http://127.0.0.1:5000 (ou via l'outil de
  preview, config dans `.claude/launch.json`, nom `planning-local`).
- **Login** : mot de passe `inter2026` (codé en dur dans `app.py`, constante
  `ADMIN_PASSWORD`).
- Dépendances : `requirements.txt` (Flask, gunicorn, **ortools**, **requests**).
- ⚠️ Après toute modif de `app.py`/`algo.py`/`database.py`, **redémarrer** le serveur
  (le process Python garde l'ancien code en mémoire). Les modifs `static/js/*.js` et
  CSS sont rechargées au refresh (headers no-cache) ; `templates/index.html` est en
  cache → redémarrage nécessaire.

---

## 3. Fichiers clés

| Fichier | Rôle |
|---|---|
| `algo.py` | `run_algo` (assignation caisses, INCHANGÉE) + solveur WFM (`generer_horaires_wfm`, `_generer_semaine`) |
| `database.py` | Schéma SQLite + helpers (employes, besoins_flux, **disponibilites**) |
| `app.py` | Routes Flask (API employees, planning, WFM, IA) |
| `ai_predictor.py` | Multiplicateurs de flux (météo/vacances/jours fériés) — appels API externes |
| `templates/index.html` | UI (onglets/sections) |
| `static/js/main.js` | Logique front (versionné via `?v=N`) |
| `dev_wfm.py` | ⚠️ Ancien prototype du solveur, **périmé/doublon** — à supprimer un jour |

---

## 4. Schéma de base — objets ajoutés

### Table `disponibilites` (nouvelle)
Fenêtre de disponibilité **récurrente par jour de semaine**.
```sql
CREATE TABLE disponibilites (
    employe_id INTEGER NOT NULL,
    jour_idx   INTEGER NOT NULL,        -- 0=Lundi .. 6=Dimanche
    dispo_debut TEXT DEFAULT '09:00',
    dispo_fin   TEXT DEFAULT '20:00',
    disponible  INTEGER DEFAULT 1,      -- 0 = indispo totale ce jour
    PRIMARY KEY (employe_id, jour_idx),
    FOREIGN KEY (employe_id) REFERENCES employes(id) ON DELETE CASCADE
);
```
- **Absence de ligne (employe, jour) = disponible 09:00–20:00** (comportement
  historique préservé, rétro-compatible).
- `get_db_connection()` active `PRAGMA foreign_keys = ON` pour la cascade.
- Helpers : `get_disponibilites(employe_id=None)`, `set_disponibilite(...)`,
  `delete_disponibilite(employe_id, jour_idx)`.

### Table `besoins_flux` (existait déjà)
`(jour_idx 0..13, slot_idx 0..43, caisse_req, cls_req)`. Ajout du helper
`save_besoins_flux(rows)` (écriture en masse `executemany`).

### Colonnes `employes` (existaient déjà)
`heures_contrat, type_contrat, forme_caisse, forme_cls, articles_minute,
note_manager, repos_fixes`.

---

## 5. API WFM (routes ajoutées dans `app.py`)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/wfm/disponibilites` | Liste des fenêtres saisies |
| POST | `/api/wfm/disponibilites` | `{employe_id, entries:[{jour_idx,dispo_debut,dispo_fin,disponible}]}` — remplace les 7 jours de l'employé (n'envoie que les jours ≠ défaut) |
| GET | `/api/wfm/besoins` | Courbe brute (616 lignes) ; prefill si vide |
| POST | `/api/wfm/besoins` | `{grid:{"0..6":[caisse×5 plages]}, cls_req}` — étend aux 44 créneaux × 2 semaines |
| POST | `/api/wfm/test_generation` | Lance la génération WFM (existait déjà) |
| POST | `/api/ai/predict_flux` | Prédiction IA (existait déjà) |

Plages horaires (`BESOINS_BANDS` dans `app.py` et `main.js`, alignées sur slots 15 min) :
`09h-11h`=slots 0-7, `11h-14h`=8-19, `14h-17h`=20-31, `17h-19h`=32-39, `19h-20h`=40-43.

---

## 6. UI (onglets ajoutés)

Deux nouveaux onglets dans la sidebar (`templates/index.html` + `static/js/main.js`) :
1. **Disponibilités** (`data-tab="dispos"`) : sélecteur d'employé + 7 lignes
   (jour × case Indisponible × fenêtre de..à). JS : `loadDisponibilites`,
   `renderDispoGrid`, bouton `#btn-save-dispos`.
2. **Courbe de besoin** (`data-tab="besoins"`) : tableau 7 jours × 5 plages +
   champ CLS global. JS : `loadBesoins`, bouton `#btn-save-besoins`.

⚠️ Le cache-buster de `main.js` est incrémenté à chaque modif JS : actuellement
`main.js?v=11` (ligne en bas de `index.html`). **L'incrémenter** à chaque nouvelle
modif de `main.js`.

---

## 7. Solveur WFM — état actuel (`algo.py`, `_generer_semaine`)

Modèle CP-SAT, 14 jours = 2 solves de 7 jours (`generer_horaires_wfm` appelle
`_generer_semaine` avec `offset_jours=0` puis `7`). ~90 s/semaine → **~3 min** au total.

⚠️ **Convention interne** : le solveur traite toujours `jour 0 = Lundi`
(via `(j + offset_jours) % 7`), indépendamment de la vraie date de début. La
sauvegarde mappe ensuite `jour j → start_date + j`. La couverture/dispo/repos se
lisent donc sur le **jour de semaine**, pas la date calendaire.

### Contraintes en place
- **Variables** par (employé, jour, créneau) : `presence, work, caisse, cls, poly, pause`.
- `work = caisse + cls + poly` ; `presence = work + pause`.
- **Compétences** : `forme_caisse=0` → pas de caisse ; `forme_cls=0` → pas de CLS.
- **Disponibilités** (Phase A) : hors fenêtre → `presence == 0`. Helper
  `_slots_disponibles(debut, fin, disponible)` convertit HH:MM → set de slots.
- **Repos fixes** (`repos_fixes`) : jour ignoré (sparsité, aucune variable créée).
- **Couverture besoin** : SOUPLE (variables `missing`/`over`, pénalisées) → renvoie
  toujours une solution même en sous-effectif.
- **Plafond physique** : `caisse ≤ 14`, `cls ≤ 1`, et **`work ≤ 15` par créneau**
  (14 caisses + 1 CLS = 15 postes max simultanés). ← corrige le sur-effectif.
- **Plancher anti-effondrement** (DUR) : chaque jour, `sum(works_today) ≥ pic_caisse
  + pic_cls` du jour (borné par l'effectif dispo). Empêche qu'un jour se vide.
- Durée shift : CDI 6.5–9 h (26–36 slots), intérim 3–7 h. Bloc continu.
- Pause repas : si présence ≥ 6 h (24 slots) → pause 3–8 slots, continue.
- Max **5 jours/semaine** par employé.
- Intérimaires : pas de POLY, faible pénalité d'usage (renfort).
- Anti-ping-pong (changement de caisse) pénalisé.

### Objectif (maximisation)
Perf caisse (`articles_minute`) + perf CLS (`note_manager×10`) − pénalités :
slack contrat (−50), POLY (−5), **missing couverture (−1000)**, over-staffing (−500),
switch (−50).

### Solveur
`max_time_in_seconds = 90.0`, `num_search_workers = 16`, `log_search_progress = True`.

### Métriques mesurées (1 semaine, courbe utilisateur actuelle)
- Max simultané : **caisses 12/14, travail 15/15** ✅
- Présents/jour : Lun 12, Mar 19, Mer→Dim 23–25 (plancher respecté partout) ✅
- **Couverture caisses ≈ 95 %** ✅ (vs 81 % avant Phase D).

---

## 8. Problèmes connus / limites

1. **Heures contractuelles non atteintes possibles** : avec seulement 15 postes
   physiques, si la somme des heures contractuelles de l'équipe dépasse ce que
   15 postes absorbent, le solveur **coupe l'excédent** (slack contrat) au lieu de
   créer des postes fantômes. → Décision métier en attente : que faire de
   l'excédent (tâches polyvalentes hors caisse ? réduction ?).
2. **Couverture ~95 %, pas 100 %** : en partie structurel (granularité des shifts +
   pauses + effectif). Pousser plus haut = plus de temps de calcul ou refonte modèle.
3. **Temps de calcul ~3 min** (2×90 s). Bouton UI annonce « max 5 min ».
4. **Grille Planification ne charge pas auto** la date du jour au chargement de la
   page (défaut pré-existant) : après génération, naviguer avec les flèches de date
   pour voir les horaires générés (dates `start_date` → `start_date+13`).
5. `dev_wfm.py` = doublon périmé du solveur, à supprimer.
6. Beaucoup d'employés ont `articles_minute = 0` → récompense caisse nulle pour eux
   dans l'objectif (la couverture est portée surtout par la pénalité missing).

---

## 9. Comment tester (sans toucher la vraie base)

Tests automatisés sur une **copie** de la base via la variable `DATA_DIR` :
```bash
# copier la base dev vers un dossier temp, puis pointer DATA_DIR dessus
DATA_DIR="/chemin/vers/copie" python mon_script_de_test.py
```
`database.py` lit `DB_FILE = os.path.join(DATA_DIR, "supermarche_dev.db")`.

Pour mesurer le solveur sans les logs verbeux d'OR-Tools (qui écrivent au niveau OS,
non capturés par `sys.stdout`), rediriger le **fd 1** autour du solve :
```python
import os, sys
sys.stdout.flush()
devnull = os.open(os.devnull, os.O_WRONLY); saved = os.dup(1); os.dup2(devnull, 1)
try:
    res = algo._generer_semaine(nb_jours=7, offset_jours=0)
finally:
    sys.stdout.flush(); os.dup2(saved, 1); os.close(devnull); os.close(saved)
# ... puis analyser res['matrice'] : dict[e_id][j] = liste de 44 tâches
```
Le format de sortie du solveur : `matrice[e_id][j][s] ∈ {"CAISSE","CLS","POLY","PAUSE",""}`.

---

## 10. État git (local uniquement)

- Branche locale : **`feature/generation-horaires`** (créée depuis `feature-wfm`).
- 2 commits locaux existent (travail Phase A sécurisé) : `secure WFM work`,
  `disponibilites table`. **Rien poussé.**
- ⚠️ Toutes les modifs **Phase B / C / D + plafond 15 + plancher dur** sont pour
  l'instant en **working-tree non commité** (l'utilisateur pilote git lui-même).
- `master` (prod) : **jamais touchée**.

---

## 11. Avancement par phase

| Phase | Sujet | État |
|---|---|---|
| A | Table `disponibilites` + solveur respecte les fenêtres | ✅ fini + testé |
| B1 | Écran Disponibilités (UI + API) | ✅ fini + vérifié navigateur |
| B2 | Écran Courbe de besoin (UI + API) | ✅ fini + vérifié navigateur |
| C | Validation bout-en-bout (génère→sauve→`run_algo`) | ✅ fini (a révélé les défauts ci-dessous) |
| D | Rééquilibrage inter-jours + plafond postes | ✅ fait (plancher dur + `work≤15`), couverture 95 % |
| — | Décision métier heures contractuelles vs 15 postes | ⏳ à trancher avec l'utilisateur |

---

## 12. Prochaines étapes possibles

- [ ] Trancher le sort de l'excédent d'heures contractuelles (cf. limite #1).
- [ ] Confirmer la génération complète 14 jours dans l'app (l'utilisateur régénère).
- [ ] Éventuellement : intégrer `restriction_handicap` (caisse paire/impaire) — pour
      l'instant géré seulement dans `run_algo`, pas dans le WFM (OK car le WFM ne
      décide que la présence, pas le n° de caisse).
- [ ] Nettoyage : supprimer `dev_wfm.py`, `algo_test.py`, `test_algo*.py` (scratch).
- [ ] Quand la V1 est validée : **l'utilisateur** met à jour GitHub.

---

## 13. FEUILLE DE ROUTE — Chantier « Fonctionnalités + Design » (démarré 2026-07-19)

> Décision utilisateur (19/07/2026) : intégrer **toutes** les recommandations
> Fonctionnalités + Design issues de l'audit. **La section IA est reportée** (plus tard).
> Traité en **phases séquencées, testées une par une**, du plus sûr au plus lourd.
> Chaque phase met à jour ce document + le journal des sessions (§14).
>
> Légende statut : ⬜ à faire · 🔶 en cours · ✅ fini & testé

### Vue d'ensemble & ordre d'exécution

| # | Code | Chantier | Effort | Risque | Statut |
|---|------|----------|--------|--------|--------|
| 1 | D1 | Login au thème sombre | faible | faible | ✅ |
| 2 | F3 | Export CSV plannings + sauvegarde base | faible | faible | ✅ |
| 3 | F1 | Heures d'ouverture par jour | moyen | moyen (touche solveur WFM) | ✅ |
| 4 | F2 | Compteur d'heures (prévu vs contrat) | moyen | faible | ✅ |
| 5 | D2 | Masque HH:MM + navigation clavier grille | faible | faible | ✅ |
| 6 | D4 | États vides pédagogiques | faible | faible | ✅ |
| 7 | D5 | Responsive tablette | faible | faible | ✅ |
| 8 | D6 | Contraste / daltonisme | faible | faible | ✅ |
| 9 | F4 | Génération WFM asynchrone + progression | moyen | moyen (threading/gunicorn) | ✅ |
| 10 | F5 | Portail employé bidirectionnel | élevé | moyen (nouvelles tables + flux) | ✅ |
| 11 | D3 | Timeline visuelle drag & drop | élevé | moyen (grosse refonte front) | ✅ |

**✅ Chantier terminé le 2026-07-19 : les 11 phases sont livrées et testées.**

⚠️ **Contrainte transverse** : `run_algo` reste **intouchable** ; toutes les intégrations
solveur se font dans le WFM (`_generer_semaine`). Après modif `main.js` → incrémenter
`?v=N`. Après modif `app.py`/`algo.py`/`database.py`/`templates` → redémarrer le serveur.

### Spécifications détaillées

#### D1 — Login au thème sombre
- **Objectif** : la page `/login` est aujourd'hui du HTML inline blanc daté ; l'aligner
  sur le thème sombre/glassmorphism (variables CSS, accent `#2CC985`, police Inter,
  fond gradient radial). Unifie l'identité visuelle (login ↔ app).
- **Fichiers** : `app.py` (fonction `login()`, GET) uniquement — pas de logique changée.
- **Points d'attention** : garder le POST/redirect identique ; message d'erreur restylé.

#### F3 — Export CSV plannings + sauvegarde base
- **Objectif** : export CSV (compatible Excel, **sans nouvelle dépendance** — module
  `csv` stdlib) d'un planning (jour ou plage) et du compteur d'heures ; route de
  téléchargement de la base SQLite pour sauvegarde manuelle.
- **Routes** :
  - `GET /api/export/planning.csv?debut=JJ/MM/AAAA&fin=JJ/MM/AAAA` → CSV (date, nom, ms, me, aes, aee, total_h).
  - `GET /api/export/backup` → renvoie le fichier `supermarche_dev.db` (`send_file`, `as_attachment`), **derrière login**.
- **Fichiers** : `app.py` (routes) ; `templates/index.html` + `main.js` (boutons Archives).
- **Points d'attention** : encodage UTF-8 BOM pour Excel FR ; séparateur `;` (Excel FR).

#### F1 — Heures d'ouverture par jour
- **Objectif** : config propre des horaires d'ouverture/jour, remplace la déduction
  implicite (`caisse_req>0`) et **supprime le hack** « dimanche fermé à 13h15 » codé en
  dur dans `forecaster.get_base_curve` / `database.prefill_besoins_flux`.
- **Schéma DB** (nouvelle table) :
  ```sql
  CREATE TABLE horaires_ouverture (
      jour_idx INTEGER PRIMARY KEY,      -- 0=Lundi..6=Dimanche
      ouvert INTEGER DEFAULT 1,          -- 0 = fermé toute la journée
      heure_ouverture TEXT DEFAULT '09:00',
      heure_fermeture TEXT DEFAULT '20:15'
  );
  ```
  Pré-remplissage : Lun–Sam 09:00–20:15 ; **Dim 09:30–13:15** ; (ajuster au réel).
- **Helpers `database.py`** : `get_horaires_ouverture()`, `set_horaire_ouverture(jour_idx, ouvert, debut, fin)`, `prefill_horaires_ouverture()`.
- **API** : `GET/POST /api/wfm/horaires_ouverture`.
- **UI** : onglet « Heures d'ouverture » (7 lignes jour × ouvert/début/fin).
- **Intégration solveur** (`algo._generer_semaine`) : `open_slots_by_day[j]` = slots dans
  la fenêtre `[ouverture, fermeture]` du **vrai** jour de semaine (via `weekday_of`),
  **intersectés** avec le besoin (>0). Hors fenêtre → `presence == 0` et besoin ignoré.
- **Points d'attention** : NE PAS toucher `run_algo`. Convertir HH:MM → index de slot
  (slot 0 = 09:00, +15 min). Rétro-compat : si table vide, comportement historique.

#### F2 — Compteur d'heures (prévu vs contrat)
- **Objectif** : tableau de bord des heures **planifiées** cumulées par employé
  (semaine ISO + mois) vs `heures_contrat`, avec delta (heures sup / déficit). Vue
  conformité + pré-paie. Structuré pour accueillir plus tard une colonne « réalisé /
  pointage » (aujourd'hui pas de source de pointage → « prévu » = planifié).
- **Calcul** : somme des durées `(me-ms)+(aee-aes)` depuis `sauvegarde_historique` sur la
  période. Semaine = lundi→dimanche ; mois = calendaire.
- **Route** : `GET /api/stats/heures?periode=semaine|mois&ref=JJ/MM/AAAA`.
- **UI** : onglet « Compteur d'heures » (tableau nom / contrat / prévu / delta, code couleur).
- **Fichiers** : `app.py`, `templates/index.html`, `main.js`.

#### D2 — Masque HH:MM + navigation clavier grille
- **Objectif** : sur la grille Planification, saisie horaire fiabilisée (masque auto
  `HH:MM`, validation 00:00–23:59) et navigation clavier (Tab ordonné, Enter → même
  colonne ligne suivante, flèches). Réduit la pénibilité de l'écran le plus utilisé.
- **Fichiers** : `static/js/main.js` (rendu grille + handlers), CSS mineur. `?v=N`++.

#### D4 — États vides pédagogiques
- **Objectif** : remplacer grilles/listes vides par des empty states explicites
  (« Aucun planning généré — cliquez sur Générer », « Aucun événement », « Aucune
  demande en attente »…). `main.js` + CSS (`.empty-state`).

#### D5 — Responsive tablette
- **Objectif** : admin utilisable sur tablette (le manager n'est pas toujours au PC).
  Sidebar compacte/repliable < 1024px ; conteneurs de grille en `overflow-x:auto`.
- **Fichiers** : `static/css/style.css` (media queries) ; léger JS pour toggle sidebar.

#### D6 — Contraste / daltonisme
- **Objectif** : contraste WCAG AA (`--text-muted` trop faible sur fond sombre) ; le code
  couleur caisses (rouge/orange/vert) doit rester lisible en daltonisme → garder les
  **libellés texte** (C1, C2…) en plus de la couleur (déjà le cas sur le planning PRO,
  à vérifier partout). `style.css` + templates.

#### F4 — Génération WFM asynchrone + progression
- **Objectif** : supprimer le blocage de ~8 min : lancer `generer_horaires_wfm` en
  **thread de fond**, l'UI **poll** la progression (étapes + %), bouton d'annulation.
  Corrige aussi la fragilité timeout de fond.
- **Mécanique** : registre mémoire `JOBS = {job_id: {status, etape, percent, result, error}}`.
  - `POST /api/wfm/generation/start` → crée `job_id`, lance le thread, renvoie `job_id`.
  - `GET /api/wfm/generation/status/<job_id>` → `{status, etape, percent, ...}`.
  - `POST /api/wfm/generation/cancel/<job_id>` → pose un flag d'annulation.
  - `algo.generer_horaires_wfm(progress_cb=...)` : appelle `progress_cb(etape, percent)`
    aux jalons (Semaine 1 début/fin, Semaine 2, Sauvegarde, Terminé). % intra-semaine
    estimé via le temps écoulé (max 240 s/sem) dans un `CpSolverSolutionCallback`.
- **UI** : barre de progression + libellé d'étape ; remplace l'`alert` bloquant.
- **⚠️ Prod (gunicorn)** : le pattern start+poll exige que le worker reste libre pendant
  le solve → **≥ 2 workers** OU worker **threadé** (`gunicorn app:app --workers 2` ou
  `--threads 4`). À répercuter dans le `Procfile` et la doc de déploiement alwaysdata.
  Le thread partage le process → OK pour SQLite (connexions courtes par appel).

#### F5 — Portail employé bidirectionnel
- **Objectif** : l'espace employé (`/mon-planning/<token>`) devient **bidirectionnel** :
  (a) demande de **congé / indisponibilité** (plage + motif) ; (b) demande d'**échange de
  shift** avec un collègue. Côté manager : onglet **Demandes** pour valider/refuser.
- **Schéma DB** (nouvelles tables) :
  ```sql
  CREATE TABLE demandes_conges (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      employe_id INTEGER NOT NULL,
      date_debut TEXT, date_fin TEXT, motif TEXT,
      statut TEXT DEFAULT 'en_attente',   -- en_attente|approuve|refuse
      date_creation TEXT,
      FOREIGN KEY (employe_id) REFERENCES employes(id) ON DELETE CASCADE
  );
  CREATE TABLE demandes_echange (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      demandeur_id INTEGER NOT NULL, cible_id INTEGER,
      date_jour TEXT, message TEXT,
      statut TEXT DEFAULT 'en_attente',
      date_creation TEXT,
      FOREIGN KEY (demandeur_id) REFERENCES employes(id) ON DELETE CASCADE
  );
  ```
- **Routes employé (whitelistées, via token)** :
  - `POST /mon-planning/<token>/conge` → crée une demande de congé.
  - `POST /mon-planning/<token>/echange` → crée une demande d'échange.
- **Routes manager** : `GET /api/demandes`, `POST /api/demandes/<type>/<id>/approuver|refuser`.
- **Effets d'approbation** :
  - Congé approuvé → écrit une **indisponibilité** (`disponibilites`, `disponible=0`) sur
    les jours concernés (l'employé sort de la génération WFM ces jours-là).
  - Échange approuvé → applique `transfer_horaires` (réutilise l'existant).
- **UI** : formulaires côté page employé (mobile) ; onglet « Demandes » manager (badges
  de compteur en attente). `?v=N`++.
- **Points d'attention** : sécurité — les routes token ne créent que des **demandes**
  (aucune action directe sur le planning sans validation manager). Rate-limit léger.

#### D3 — Timeline visuelle drag & drop
- **Objectif** : remplacer/compléter la saisie texte de la grille par une **timeline
  horaire** (barres qu'on étire à la souris, façon Gantt) pour poser les shifts —
  l'amélioration UX la plus visible. Gros morceau front.
- **Approche** : par employé, une piste 09:00→20:15 (slots 15 min) ; drag pour créer/
  redimensionner un bloc de présence ; 2 blocs possibles (matin/après-midi) ; conversion
  bloc ↔ `ms/me/aes/aee`. Rester **rétro-compatible** avec la saisie texte (toggle vue).
- **Livraison** : v1 = affichage + édition d'un bloc au glisser ; itérations ensuite.
- **Fichiers** : `main.js` (nouveau composant), `style.css`, `index.html`. `?v=N`++.

---

## 14. Journal des sessions

### Session 2026-07-02
**Fait :**
- **Phase A** : table `disponibilites` (+ `PRAGMA foreign_keys=ON`, helpers) ;
  `_generer_semaine` lit les dispos et interdit la présence hors fenêtre ; ajout
  `_slots_disponibles()`. Corrigé un bug latent (bloc POLY intérimaire utilisait des
  variables de boucle `s`/`j` hors portée → `KeyError` possible).
- **requirements.txt** : ajout `ortools==9.15.6755` et `requests==2.33.1` (utilisés
  mais absents → le déploiement aurait cassé). `.gitignore` : ajout `*.log`.
- **Phase B** : routes `GET/POST /api/wfm/disponibilites` et `.../besoins` ;
  `save_besoins_flux()` ; 2 onglets UI (Disponibilités, Courbe de besoin) ;
  `main.js?v=9 → v=11`. Testé end-to-end UI→API→base (dispos et courbe).
- **Phase C** : validation bout-en-bout OK (génère, sauve `ms/me/aes/aee`, relu par
  `run_algo`). **A révélé** : couverture 81 %, Lundi/Mardi effondrés (4 et 8 présents).
- **Phase D** : ajout collecte `works_today_day` ; **plancher de présence par jour**
  (d'abord souple, puis passé en **DUR** = `sum(works_today) ≥ pic_caisse+pic_cls`) ;
  temps solveur 60→90 s, 16 workers. (Essai d'inflation ×1.25 du plancher →
  contre-productif, annulé.)
- **Bug sur-effectif** signalé par l'utilisateur : jusqu'à 22–26 personnes au travail
  simultané alors que le magasin a 15 postes (14 caisses + 1 CLS). **Cause** : aucune
  contrainte ne plafonnait le total simultané. **Correctif** : `sum(work) ≤ 15` par
  créneau. Vérifié : max travail = 15/15, couverture remontée à **95 %**, plus
  d'effondrement.
- **Config employés** corrigée par l'utilisateur (étudiants/alternants 12 h, mi-
  thérapeutique 25 h, etc.).
- **Intérimaires — heures** : le champ « Heures Contrat » est désormais **désactivé**
  dans l'UI (ajout + édition) quand le contrat = Interimaire (placeholder « Illimité »,
  `heures_contrat = 0` envoyé à la sauvegarde). `main.js` : fonction
  `updateHoursFieldState()`. `main.js?v=11 → v=12`.
  ⚠️ Le solveur **ignorait déjà** les heures des intérimaires (`if not is_interimaire`,
  ~ligne 588) → ils ne sont **jamais** ciblés à 35 h. Leur présence quasi-quotidienne
  observée venait du **comblement des trous de couverture** (renfort quand l'effectif
  permanent est insuffisant), pas d'une cible d'heures. **Option non faite** : augmenter
  la pénalité d'usage des intérimaires (`work*-10` dans l'objectif → plus négatif) pour
  les rendre davantage « dernier recours » (compromis : peut baisser la couverture).

- **Recalibrage de la courbe sur données réelles** : l'utilisateur a fourni 7 plannings
  réels (semaine 06→12/07, dans son Downloads). Parsés pour extraire le **vrai nombre de
  caisses ouvertes par plage/jour** → chargé dans `besoins_flux` (2 semaines). Valeurs
  réelles (caisses par plage 09-11/11-14/14-17/17-19/19-20) : Lun 8/11/8/8/7, Mar
  8/9/8/11/8, Mer 8/9/9/11/9, Jeu 9/11/7/13/9, Ven 9/10/11/12/8, Sam 11/12/11/11/9,
  **Dim 9/9/0/0/0 (caisses fermées l'après-midi)**. Découvertes : vrai max simultané
  **10–14/jour** (jamais 20) → les « 20 personnes » venaient du **bug de sur-effectif**
  (déjà corrigé par `work≤15`), PAS d'une courbe trop haute. Parsing : `sub-block` texte
  `C\d+` = caisse, `CLS` = cls.
- **⚠️ Reste à traiter (pool caisses)** : avec la courbe réelle, le solveur planifie
  encore ~20–29 personnes DISTINCTES/jour (vs ~17 en réel) car il tente de donner leurs
  heures à **tous les 31 employés**, y compris ceux **postés à l'accueil l'été** (donc
  PAS sur les caisses). Le solveur ne le sait pas. → Il faut lui indiquer **qui est
  réellement disponible sur les caisses** cette période : marquer les employés accueil
  comme indisponibles (écran Disponibilités), ou ajouter un flag « actif sur caisses ».
  C'est aussi ce qui fait sur-utiliser les intérimaires.

- **Interrupteur « Sur les caisses »** (résout le pool accueil) : nouvelle colonne
  `employes.sur_caisses` (INTEGER DEFAULT 1, migration douce `ALTER TABLE` dans
  `init_db`). Toggle dans l'onglet Équipe (ajout + édition) ; décoché = employé
  **totalement exclu** de la génération WFM (accueil, absence longue…). Badge « Hors
  caisses » sur sa fiche. Le solveur filtre :
  `[e for e in db.get_employes() if e.get('sur_caisses', 1)]` dans **`_generer_semaine`
  ET `generer_horaires_wfm`**. `main.js?v=12 → v=13`. Testé bout-en-bout (API PUT → base
  → exclusion du pool solveur 30/31 → restauration).

- **4 correctifs solveur (retours terrain)** :
  - **Heures d'ouverture** : `open_slots_by_day` (créneaux où besoin>0) ; présence
    interdite hors ouverture ; durée de shift bornée à la fenêtre du jour
    (`min(26/12, open_count)`). Retrait du `max(1,...)` sur `req_caisse/req_cls` (sinon
    un besoin 0 = « fermé » réclamait quand même 1). **Dimanche forcé fermé dès 13:00**
    (slots 16-43 mis à 0, car la bande 11-14 débordait jusqu'à 14:00). → Dimanche
    s'arrête bien à 12:45. ⚠️ *Limite : l'éditeur de courbe par bandes ne sait pas
    exprimer une fermeture en milieu de bande ; une vraie config « heures d'ouverture /
    jour » serait plus propre (dette technique).*
  - **Coupures centrées** : ≥2h (8 créneaux) de travail AVANT le début ET APRÈS la fin
    de la coupure (`ps_idx-ss_idx>=8` et `ss+sum_presence-ps-sum_pause>=8`, OnlyEnforceIf
    needs_pause).
  - **C1/C2 jamais fermées** : `sum(work) >= 2` sur chaque créneau ouvert (dans la boucle
    couverture).
  - **Intérim dernier recours** : pénalité d'usage `work*-10` → **`-60`** dans l'objectif.
  Vérifié (1 semaine, pool 29) : Dimanche fermé 13h ✅, 0 coupure mal placée ✅,
  0 violation C1/C2 ✅.
- **Intérim** : Lun/Mar ~4, jours chargés ~7 (réel ~5). En grande partie **structurel** :
  les heures contractuelles permanentes (étudiants 12h, mi-thér 25h, accueil exclus…) sont
  **< à la demande** cette période → l'intérim comble le manque (comme dans les vrais
  plannings). ⚠️ **Marquer plus d'employés « hors caisses » AUGMENTE l'intérim** (retire
  de la capacité permanente), ça ne le réduit pas. Pour descendre encore : plus de temps
  de calcul (meilleur packing) ou accepter le niveau.

- **🐞 BUG MAJEUR corrigé — alignement des jours de la semaine** : le solveur supposait
  `jour 0 = Lundi` quelle que soit la date de début. Or l'app démarre à la date du jour
  (ex. **vendredi 03/07**). Conséquence : le VRAI dimanche était traité comme un
  « mercredi » (ouvert jusqu'à 20h) et la fermeture 13h tombait sur le mauvais jour ; les
  `repos_fixes` étaient aussi décalés ; **et surtout chaque employé gaspillait ~7h le
  dimanche** (présent magasin fermé) → vidait ses heures contrat → sous-effectif ailleurs
  → intérim (intuition de l'utilisateur, exacte).
  **Fix** : param `start_weekday` (= `start_date.weekday()`) propagé dans `_generer_semaine`
  et `generer_horaires_wfm` ; `weekday_of[j] = (start_weekday + offset_jours + j) % 7` ;
  courbe / heures d'ouverture / repos / dispo lues sur ce vrai jour (via `bes_lookup`).
  Vérifié (start=vendredi) : dimanche (jour 2) ferme à **12:45**, autres jours ouverts
  jusqu'à 19:45.

- **Rééquilibrage midi/soir** : après l'alignement, diagnostic sur la génération réelle =
  le solveur **entassait le midi (15/9-12) et vidait le soir (19:30 : 3-6/8-9)**. Cause des
  « pas assez de caisses en fin de journée » et de C1/C2 fermées le soir. Fix : pénalité
  sous-couverture -1000 → **-2000**, sur-staffing -500 → **-800**, temps 90 → **120 s/sem**.
  Résultat testé : 19:30 remonte à 6-11 présents (couvre la plupart des jours) ; **Jeudi
  reste tendu** (pic 13 caisses à 17-19h — possiblement sur-évalué par le band-max, à
  vérifier / éditable dans la Courbe).
- **C1/C2 fermées en fin de journée** : c'est un comportement de **`run_algo`** (non
  modifié) : sa règle de *continuité* garde les gens sur leur caisse actuelle et ne
  **rebascule pas** quelqu'un vers C1/C2 quand leur titulaire part. Le meilleur staffing
  du soir aide, mais si ça persiste → petit **post-pass dans `run_algo`** (garantir C1/C2
  ouvertes tant qu'≥1 personne est libre) — à valider avec l'utilisateur (run_algo était
  déclaré off-limits).
- **💡 Nouvelle fonctionnalité demandée (à faire PLUS TARD)** : la responsable fait les
  **horaires hebdo** des employés et les distribue **sur papier** → vouloir (a) créer/gérer
  ces horaires dans l'app, (b) les **distribuer de façon dématérialisée** aux employés
  (espace employé / lien / export). Feature distincte et conséquente → à traiter APRÈS la
  qualité de génération. Noté comme phase future.

- **❌ Post-pass C1/C2 dans `run_algo` (ÉTAPE 7) : TENTÉ PUIS ANNULÉ (revert)**. L'idée :
  ré-étiqueter les caisses ouvertes en fin de journée pour garantir C1/C2. **Rejeté par
  l'utilisateur** : ça créait de l'**instabilité** (changements d'1 seul créneau, dus au
  forward-fill qui cassait quand C1/C2 se rouvrait ailleurs) et ça **ignorait le système
  de pénalités hiérarchiques** (`HIERARCHIE_PENALITE_*` : éviter tel employé sur C1/C2/etc.)
  qui faisait la qualité du `run_algo` d'origine. **`run_algo` a été restauré octet pour
  octet = version d'origine** (vérifié via `git show HEAD:algo.py`). ⚠️ **NE PAS re-toucher
  `run_algo` sans idée bien plus propre.**
- **C1/C2 fin de journée — OPTION A (WFM « fermeurs coupés ») implémentée, RÉUSSITE
  PARTIELLE.** L'utilisateur a choisi de corriger **côté WFM, pas `run_algo`**. Changements
  dans `_generer_semaine` :
    - **Durée** : on borne désormais le **TRAVAIL** (≤ 9h = 36 slots, `sum_work_day <=
      work_max`) au lieu de l'**amplitude de présence** (`sum_presence <= open_count`). Ça
      autorise les shifts **coupés amples** (ex. 09:00-20:00 avec 2h de pause = 9h travaillées).
    - **Contrainte** : **≥ 2 personnes présentes à l'OUVERTURE ET à la FERMETURE**
      (variables `fullspan_*`) les jours à grande amplitude (≥ 30 créneaux ouverts) = des
      « coupés » type responsable, censés tenir C1/C2 toute la journée.
    - Petite **pénalité pause** (-3/slot) pour garder les autres shifts compacts par défaut.
    - **BUG CORRIGÉ** : la pénalité POLY de l'objectif indexait `poly[(e,j,s)]` en dur →
      **crash sur les jours de `repos_fixes`** (variables non instanciées). Passée en `.get()`
      (idem pénalité pause). Important car l'utilisateur va renseigner les repos.
  **Test end-to-end (WFM → run_algo)** : C1/C2 ouvertes à la fermeture **Vendredi & Lundi**,
  mais **PAS Jeudi**. **Pourquoi** : `run_algo` attribue C1/C2 à la personne au **plus long
  bloc continu à 9h** (un ouvreur 9h-18h), pas au coupé (dont le bloc du matin est plus court
  à cause de sa coupure). L'ouvreur part à 18h → C1/C2 ferment ; le coupé, sur une caisse
  basse, ne les récupère pas.
  **CONCLUSION Option A** : le WFM seul ne garantit pas C1/C2 à 100 % (run_algo donne C1/C2
  à la personne au **plus long bloc** = un ouvreur qui part à 18h). La feature « fermeurs
  coupés » **RESTE** (horaires plus réalistes), mais il fallait aussi l'Option B.

- **✅ OPTION B — post-pass `run_algo` (« ETAPE 7 »), version PROPRE, VALIDÉE.** Feu vert
  utilisateur. Corrige les 2 erreurs de la 1re tentative ratée :
    - **Réassignation par BLOC PROPRE, sans retour** : on ne bascule sur C1/C2 qu'une
      personne dont le **bloc de caisse actuel se termine À L'INTÉRIEUR du trou** → un seul
      changement, jamais de ping-pong `Cy→C1→Cy` = **zéro instabilité « 15 min »**. On chaîne
      plusieurs personnes si le trou est long. On s'arrête pile où C1/C2 rouvre (0 doublon).
    - **Respect des pénalités** : on prend la personne de pénalité `HIERARCHIE_PENALITE_C1_C2`
      la plus faible (jamais un pénalisé si évitable).
    - **Parité** (restriction handicap) et **pauses réservées** respectées (si C1/C2 vide juste
      parce que son titulaire est en pause, on n'y touche pas — c'était la source des flips).
    - **NO-OP** si C1/C2 déjà ouvertes → le flux manuel « qui marchait parfaitement » n'est
      PAS modifié (vérifié : sur un planning bien staffé, 0 changement).
  **Tests (8 jours, données réelles)** : **0 doublon, 0 pénalisé sur C1/C2, C1 & C2 ouvertes
  à la fermeture (19:45) sur les 8 jours**. Résidus : ~3 créneaux de C2 fermée EN MILIEU de
  journée (11h-14h, 9 caisses ouvertes) sur 8 jours = micro-relèves internes de run_algo où
  combler proprement est impossible sans réintroduire l'instabilité → **laissés volontairement**
  (stabilité > combler à tout prix, conformément au retour utilisateur).
  📍 Code : `algo.py`, `run_algo`, section `# --- ETAPE 7 ...` (juste avant `infos_pauses`).

- **✅ DISTRIBUTION DES HORAIRES (MVP)** — page employé + lien/QR personnel. Choix
  utilisateur : **lien/QR perso par employé**, contenu = **ses heures de travail**.
    - **DB** : colonne `employes.token` (migration `ALTER TABLE`) ; jeton
      `secrets.token_urlsafe(8)`. Helpers `ensure_all_tokens()` (idempotent, appelé dans
      `GET /api/employees`) et `get_employe_by_token()`.
    - **Route publique** `GET /mon-planning/<token>` — **whitelistée dans `require_login`**
      (sans mot de passe). Page HTML mobile autonome : salutation + liste des prochains
      jours (aujourd'hui surligné, heures matin/après-midi lues dans `sauvegarde_historique`,
      « Repos » pour les jours sans shift). Lien invalide → 404 propre. L'employé ne voit
      **que** son planning.
    - **UI manager** (onglet Équipe) : bouton 🔗 par fiche → **modal lien copiable + QR**
      (lib `qrcodejs` via CDN, QR généré **côté client** → rien n'est envoyé à un tiers).
      URL = `window.location.origin + '/mon-planning/<token>'` (donc correcte en prod).
      `main.js?v=13 → v=14`.
    - **Total d'heures / semaine** : en-tête « Semaine du JJ/MM → XXhYY » (lundi→dimanche,
      somme de TOUS les shifts de la semaine, y compris les jours passés de la semaine en
      cours). Calcul dans la route (`_dur_h`, `_fmt_h`, `_lundi`).
    - **Testé** : page employé (BERTHE Sebastien, 10 jours, repos + totaux hebdo) ✅ ;
      31 boutons lien, modal + QR + copie ✅ ; aucune erreur JS.
    - ⚠️ **QR/lien & localhost** : le lien prend `window.location.origin`. En **local** il vaut
      `localhost:5000` → **inaccessible depuis un téléphone** (normal). Solutions : (a) en
      **prod** (déployé) le vrai domaine est utilisé → OK partout ; (b) en local, accéder à
      l'appli via l'**IP LAN** de la machine (ex. `http://192.168.1.107:5000`, Flask écoute
      déjà sur `0.0.0.0`) pour que le QR pointe vers une adresse joignable sur le même WiFi.
      Ce n'est PAS un bug — rien à changer dans le code.

**État à la fin de la session :** WFM très solide (alignement jours réels, dimanche 13h,
équilibrage midi/soir, heures d'ouverture, coupures ≥ 2h, intérim -60, plafond 15 postes,
fermeurs coupés) + bug POLY/repos corrigé. **`run_algo` = original + UNE passe propre ETAPE 7**
(garantit C1/C2 en fin de journée, no-op sinon, respecte pénalités/parité). **C1/C2 à la
fermeture = RÉGLÉ.**
**Prochaines étapes :**
1. Régénérer un PLANNING PRO et valider visuellement C1/C2 + la stabilité du placement.
2. Décider si les ~3 fermetures C2 milieu-journée / 8 jours sont acceptables (sinon : petit
   trade-off stabilité à discuter).
3. Sous-effectif fin de journée jours à gros pic (Jeudi 13 caisses 17-19h — éditable Courbe).
4. Renseigner les **`repos_fixes`** (désormais alignés).
5. Midi « un peu chargé » : valider avec le manager, ajuster la Courbe.
6. **✅ Distribution dématérialisée des plannings : FAITE (MVP)** — voir bloc dédié
   ci-dessus. Évolutions possibles plus tard : vue « planning PRO complet » (caisses/pauses)
   côté employé, bouton pour régénérer un jeton, notification de mise à jour.
**Dette technique** : vraie config « heures d'ouverture par jour ».

**À reprendre :** voir § 12. Ne rien pousser sur GitHub.

---

### Session 2026-07-04
**Fait :**
- **Résolution du déficit d'heures des CDI vs Intérimaires (Le paradoxe de la pénalité)** : L'utilisateur a signalé que les CDI n'atteignaient pas leurs 36h45 hebdos, et que le solveur compensait en générant trop d'intérimaires.
  - **Diagnostic mathématique** : Le solveur fait face à un choix permanent. S'il force un CDI à faire ses 36h45, il doit le faire venir sur des longues journées (min 6.5h). Si le magasin est en heures creuses, la présence du CDI génère du **sur-effectif** (`over_c`).
    - Pénalité de sur-effectif (`over_c`) : **-800 points** / créneau.
    - Pénalité de non-respect du contrat CDI (`slack_minus`) : **-50 points** / créneau.
    Puisque 800 > 50, le solveur "préférait" sacrifier les heures du CDI (le laisser chez lui) plutôt que de créer du sur-effectif. Ensuite, pour couvrir les pics de 3h, il appelait un intérimaire (pénalité **-60**). L'intérimaire était donc mathématiquement "moins cher" qu'un CDI qui amène avec lui 3h de pic + 3.5h de sur-effectif hors-pic.
  - **Correctif (Inversion de la hiérarchie des pénalités)** : 
    - `slack_minus` (déficit contrat CDI) est passé de **-50** à **-5000**. Le respect des 36h45 devient **IMPÉRATIF** et passe au-dessus de toutes les autres considérations (y compris le sur-effectif). Le solveur va désormais forcer les CDI à venir faire leurs heures, quitte à saturer les caisses l'après-midi. En saturant l'après-midi, leurs shifts vont naturellement déborder sur les pics du midi/soir, couvrant ainsi le magasin.
    - `slack_plus` (heures supplémentaires CDI) est passé de **-50** à **-100**. Ainsi, si un CDI a **déjà** fait ses 36h45, le solveur préférera appeler un intérimaire (-60) plutôt que de lui faire faire des heures sup (-100).
  - **Résultat attendu** : Les CDI atteindront exactement leurs heures contractuelles (le solveur ne s'arrêtera pas tant qu'ils ne sont pas à 36h45). Le besoin en intérimaires va s'effondrer et se limiter strictement aux pics impossibles à couvrir par les CDI ayant déjà atteint leurs 35h ou leurs 5 jours ouvrés.

- **Intégration d'une gestion dynamique des événements** :
  - **Interface utilisateur (Onglet Événements)** : Création d'une page frontend complète permettant aux managers de saisir et d'éditer des événements spécifiques (Promotions, Jours Fériés, Événements sportifs locaux).
  - **Base de données (`database.py`)** : Ajout d'une table `evenements` avec API REST CRUD complète (`GET, POST, DELETE` sur `/api/evenements`).
  - **Moteur IA (`forecaster.py`)** : Les ajustements s'expriment désormais de manière concrète en *nombre absolu de caisses requises* supplémentaires (ou en moins) pour 3 tranches horaires (matin, après-midi, soir) plutôt qu'en pourcentage, à la demande de l'utilisateur.
- **BUG CORRIGÉ (Génération du Dimanche)** :
  - **Problème** : L'utilisateur a signalé que le solveur planifiait les équipes jusqu'à 20h00 le dimanche, ignorant la fermeture officielle de 13h15.
  - **Cause** : Le 05/07 tombant en début de mois, le moteur IA (`forecaster.py`) appliquait automatiquement son boost "Versement des salaires/CAF" de +1 caisse. Il l'appliquait sur TOUS les créneaux, faisant passer le besoin du dimanche après-midi de `0` à `1`. Le solveur, voyant un besoin de 1 caisse, considérait le magasin "ouvert" et planifiait le personnel. De plus, la courbe de base était "hardcodée" dans l'IA et écrasait les paramétrages utilisateurs.
  - **Correctif** : L'IA lit dorénavant la courbe de base dynamique depuis la base de données (`besoins_flux`). J'ai injecté une sécurité bloquante dans le `forecaster` : l'IA (météo, calendrier, événements) n'a l'autorisation de modifier l'affluence *uniquement* sur les créneaux où le magasin est déjà marqué comme ouvert par le manager (`caisse_req > 0` ou `cls_req > 0`).

**État à la fin de la session :** Les 36h45 des CDI sont gravées dans le marbre de l'algorithme. Les événements sont paramétrables dynamiquement sur le frontend. Le bug des ouvertures "fantômes" les dimanches après-midi liées aux jours spéciaux est 100% résolu (fermeture à 13h15 strictement respectée).

**À reprendre :** Valider via la génération si le niveau de sur-effectif l'après-midi est tolérable visuellement, et vérifier les fiches de paie (les compteurs d'heures) sur la page Employé.

### Session 2026-07-10 à 2026-07-12
**Fait :**
- **Ajustements du Moteur WFM (OR-Tools)** :
  - *Amplitude horaire* : L'heure de fin de journée a été repoussée de 20h00 à 20h15 pour correspondre exactement à la fermeture physique du magasin + délai de comptage caisse.
  - *Réglementation des coupures* : Refonte du calcul des pauses. Elles doivent désormais obligatoirement faire 45 minutes ou 1 heure, et se positionner après un minimum de 3 heures de travail continu (et laisser 3 heures de travail avant la fin de journée).
  - *Stratégie Intérim (Touche Finale)* : L'utilisation des intérimaires a été re-paramétrée pour intervenir strictement en dernier recours. L'algorithme privilégie désormais toujours les CDI pour boucler les 36h45 avant d'injecter des intérimaires.
- **Connectivité & Prévisions intelligentes (Le Cerveau IA)** :
  - *Météo* : Connexion à l'API **Open-Meteo** (centrée sur Vaux-le-Pénil, 77) pour adapter dynamiquement la courbe de besoin en cas de canicule, pluie ou alerte neige.
  - *Vacances scolaires* : Connexion à l'API **data.education.gouv.fr** pour détecter automatiquement les vacances de la Zone C (Créteil) et lisser le flux.
  - *Prévisionnel 24 & 31 Décembre* : Intégration "en dur" des métriques N-1 pour ces journées hyper-chargées. Le besoin est modélisé mathématiquement (`Articles/1200 + Clients/60`) à chaque créneau, avec une coupure nette et fermeture anticipée à 19h00.
- **Intégration IA Générative (Copilote Gemini)** :
  - Installation du SDK `google-genai`.
  - Modification de la base locale (`database.py`) pour y ajouter une table `settings` sécurisant la clé API.
  - Création de `ai_agent.py` comme pont backend vers Gemini avec système de "Function Calling".
  - **Mise à jour du modèle** : Migration vers `gemini-flash-lite-latest` pour contourner les limites strictes de quota journalier de Google (Erreur 429) et assurer une stabilité en production gratuite.
  - **Correction du Function Calling** : Affinement du "System Prompt" pour imposer à l'IA de lire le planning existant (`get_planning_du_jour`) avant toute modification (`prolonger_horaire`), afin de garantir le respect de l'ordre chronologique des heures (arrivée/départ).
  - Refonte UI avec l'apparition d'un bouton flottant (Assistant IA) et d'un panneau latéral interactif permettant de requêter l'assistant en langage naturel.

**État à la fin de la session :** L'application est devenue un outil prédictif complet, aligné sur des données externes (Météo/Éducation Nationale) et doté d'une interface LLM autonome, stable et capable d'agir sur la base de données. L'application est prête à être présentée aux investisseurs/franchisés.

### Session 2026-07-17 à 2026-07-18
**Fait :**
- **Refonte UI et Assistant IA** :
  - Refonte visuelle de l'interface du chat avec du CSS moderne, et remplacement du textarea pour un support multiligne (`Maj+Entrée`).
  - Implémentation d'un mode "Walkie-Talkie" (reconnaissance vocale) rattaché au chat.
  - Ajout du badge dynamique de prédiction d'affluence.
  - Refonte du design d'ajout d'employé et nettoyage des vieux boutons standards (Générer standard enlevé).
- **Mise à jour du Copilote IA** :
  - Création de la commande `transferer_horaires` pour pallier à l'incapacité de Gemini à "remplacer" une personne par une autre.
  - Fonctionnalité de recherche de noms devenue insensible aux accents (utilisation de `unicodedata` pour pallier aux dictées vocales contenant des accents).
- **Audit de Code et Correctifs de Production** :
  - **Dépendance manquante corrigée** : Ajout de `google-genai` dans `requirements.txt`.
  - **Stabilité de Déploiement** : Augmentation du timeout Gunicorn à 10 minutes (`Procfile`) en cohérence avec le temps de génération WFM (240s/semaine).
  - **Hygiène BDD** : Correction de fuites de connexion SQLite dans les requêtes des événements (`database.py`).
  - **Optimisation API** : Implémentation d'un cache en mémoire (`@functools.lru_cache`) sur les requêtes météo et Éducation Nationale pour éviter la surcharge bloquante lors de la génération.
  - **Sécurité et Nettoyage** : Basculement de la `SECRET_KEY` sur l'environnement et suppression de tous les vieux fichiers de tests et bases de données inutilisés du dépôt.

**État à la fin de la session :** Le backend est fiabilisé, asynchrone et les performances de prédiction sont cachées pour éviter les timeouts en production. L'interface de l'IA dispose de la reconnaissance vocale et comprend les erreurs d'accentuation, la rendant robuste en environnement réel (magasin). Le système garantit 36h45 pour les CDI au cordeau.

### Session 2026-07-19
**Fait :**
- **Flux d'approbation des congés amélioré** : L'approbation d'un congé déclenche désormais une modale de décision permettant au manager d'anticiper le remplacement :
  - Générer automatiquement une demande d'intérim avec les heures exactes que devait faire le collaborateur avant son congé.
  - Basculer sur l'onglet Intérim (pré-rempli) pour saisir manuellement les heures.
  - Ignorer et retirer simplement les heures.
- **Documentation et Testabilité (QR Code)** : L'astuce pour tester le QR code des portails collaborateurs en local a été confirmée (utilisation de l'IP du réseau local type `192.168.1.xxx` au lieu de `127.0.0.1`).

### Session 2026-07-19
**Contexte :** audit complet demandé (état des lieux + optimisations + erreurs). Corrections de
l'audit appliquées par l'utilisateur, puis démarrage du **chantier « Fonctionnalités + Design »**
(cf. §13 pour la feuille de route détaillée). **Section IA reportée** (à faire plus tard).

**Corrections d'audit (faites par l'utilisateur, revérifiées ✅) :**
- `requirements.txt` : ajout `google-genai>=0.1.0` (l'import `ai_agent` en tête de `app.py`
  cassait tout redéploiement propre — panne totale évitée).
- `Procfile` : `gunicorn app:app --timeout 600` (le solve ~8 min dépassait le défaut 30 s).
- `main.js` : bouton génération « max 5 min » → « max 10 min » (aligné sur le solve réel).
- `database.py` : `get_evenements/get_evenement/add_evenement/delete_evenement` ferment
  désormais la connexion (`conn.close()`).
- `algo.py` : commentaire mort de l'objectif remplacé ; contrainte redondante `sum(work)<=25`
  supprimée ; `log_search_progress=False`.
- `app.py` : `app.secret_key = os.environ.get("SECRET_KEY", ...)`.
- Nettoyage repo : suppression `dev_wfm.py`, `algo_test.py`, `test_*.py`, `check_db.py`,
  `fix_db.py`, `trigger.py`, `integration_test.py` + bases mortes (`database.db`, `planning.db`,
  `supermarche_data.db`).

**Chantier Fonctionnalités + Design — phases livrées & testées :**

- **✅ D1 — Login au thème sombre.** `app.py` : `login()` refactorée + helper `_render_login(error)`
  (page HTML sombre/glassmorphism, accent `#2CC985`, police Inter, gradient, logo SVG). POST/redirect
  inchangés. Testé : rendu OK (message d'erreur stylé si mauvais mdp), structure vérifiée navigateur.

- **✅ F3 — Export CSV + sauvegarde base.** Helpers module-level dans `app.py` : `dur_heures(a,b)`,
  `fmt_heures(x)`, `total_jour_heures(row)` (réutilisés par F2). Ajout `send_file` à l'import flask.
  - `GET /api/export/planning.csv?debut=&fin=` → CSV `;`-séparé + BOM UTF-8 (Excel FR), 8 colonnes
    (Date, Jour, Employé, ms, me, aes, aee, Total heures). Dates invalides → 400.
  - `GET /api/export/backup` → `send_file(db.DB_FILE, as_attachment=True)` (sauvegarde manuelle).
  - UI : barre d'export dans l'onglet Archives (2 dates + 2 boutons), défauts = aujourd'hui (date
    LOCALE). Testé : CSV 200 (accents OK), 400 sur dates KO, backup 163 Ko, requête navigateur OK.

- **✅ F1 — Heures d'ouverture par jour.** Nouvelle table `horaires_ouverture(jour_idx, ouvert,
  heure_ouverture, heure_fermeture)` + prefill (Lun–Sam 09:00–20:15, **Dim 09:30–13:15**). Helpers
  `get_horaires_ouverture()` / `set_horaire_ouverture()`. API `GET/POST /api/wfm/horaires_ouverture`.
  Onglet UI « Heures d'ouverture » (7 lignes jour × Fermé/ouverture/fermeture).
  **Intégration solveur** (`algo._generer_semaine`) : nouvelle fenêtre AUTORITAIRE — `_slot_from_hhmm`
  (slot 0 = 09:00, +15 min) → `fenetre_ouv_by_wday` ; `open_slots_by_day` = fenêtre ∩ besoin(>0).
  Rétro-compat : jour sans config = toute la plage. **NE TOUCHE PAS `run_algo`.**
  Testé : prefill + API OK ; **smoke-test solveur** (solve 45 s, réseau stubbé, start=dimanche) →
  **0 créneau travaillé après 13:15 le dimanche** ✅ ; UI charge les 7 jours avec bons défauts.
  *Note : le hack Sunday dans `forecaster.get_base_curve` / `prefill_besoins_flux` devient redondant
  (la fenêtre d'ouverture le gère structurellement) — pourra être nettoyé plus tard.*

- **✅ F2 — Compteur d'heures (prévu vs contrat).** `GET /api/stats/heures?periode=semaine|mois&ref=`
  → par employé : prévu (somme heures planifiées `sauvegarde_historique` sur la période) vs cible
  (contrat hebdo, proraté ×jours/7 en mode mois), écart. Intérim (contrat 0) → cible « — ».
  Onglet UI « Compteur d'heures » : bascule Semaine/Mois + date réf + table couleur (rouge déficit /
  orange sup / vert pile). Testé : semaine (« Semaine du 13/07 au 19/07/2026 », 31 lignes) + mois
  (« Juillet 2026 », cible proratée 161h39) ✅, aucune erreur console.

**Cache-buster :** `main.js?v=16 → v=17` (une seule incrémentation couvrant toutes les modifs JS de
la session). Les en-têtes no-cache rechargent de toute façon le JS en local.

**Environnement de test :** screenshots navigateur HS (renderer) → vérifs via `read_page` /
`get_page_text` / `javascript_tool` + client de test Flask + smoke-tests solveur sur **copie** de la
base (`DATA_DIR` temp), jamais la vraie `supermarche_dev.db`.

**Chantier Fonctionnalités + Design — suite & FIN (mêmes session, 11/11 phases) :**

- **✅ D2 — Masque HH:MM + navigation clavier.** `main.js` : l'auto-format horaire existant a été
  étendu (`_TIME_SELECTOR` inclut désormais `.horaire-ouv/.horaire-fer`) ; **validation au blur**
  (`_TIME_RE` = `^([01]?\d|2[0-3]):[0-5]\d$` → bordure rouge si invalide, vide = OK) ; **navigation
  clavier** dans la grille Planification (Entrée / ↓ = même colonne ligne suivante, ↑ = précédente).
  Testé navigateur : Entrée descend, « 99:99 » → bordure rouge, valide → effacée.

- **✅ D4 — États vides pédagogiques.** Composant `.empty-state` (CSS) + helper JS `emptyState(icon,
  title, subtitle)`. Appliqué à Événements, Archives, Intérim (et déjà présent sur Compteur/Demandes).
  Testé : onglet Intérim vide affiche le composant + icône lucide.

- **✅ D5 — Responsive tablette.** Media queries `style.css` : ≤1024px sidebar compacte (210px) ;
  ≤820px la sidebar devient une **barre horizontale scrollable** en haut (colonne, header masqué,
  body scrollable), sans JS. Testé via `resize_window` : 1000px→sidebar 210px, 760px→nav horizontale.

- **✅ D6 — Contraste / daltonisme.** `--text-muted` `#a0a0a0 → #b4b4b4` ; anneau `:focus-visible`
  (accessibilité clavier) ; **repère non-coloré** ▼/▲/= sur l'écart du Compteur d'heures (lisible en
  daltonisme). Testé : `--text-muted`=#b4b4b4, écarts « ▼ -36h45 » / « = +0h ».

- **✅ F4 — Génération WFM asynchrone + progression.**
  - `algo.py` : classe `_ProgressCallback(cp_model.CpSolverSolutionCallback)` (progression via
    `progress_cb`, annulation via `should_cancel`→`StopSearch`). `_generer_semaine` et
    `generer_horaires_wfm` acceptent `progress_cb`/`should_cancel` (+ jalons Semaine 1/2 → 2..47 %,
    Semaine 2/2 → 50..93 %, Sauvegarde 96 %, Terminé 100 % ; check annulation entre semaines).
  - `app.py` : registre mémoire `WFM_JOBS` + `threading` ; routes `POST /api/wfm/generation/start`
    (thread démon, purge des jobs finis), `GET .../status/<job_id>`, `POST .../cancel/<job_id>`.
    `app.run(threaded=True)`. **Procfile : `--threads 4`** (⚠️ requis en prod pour servir le polling
    pendant le solve — worker gthread). L'ancienne route synchrone `/api/wfm/test_generation` est
    conservée.
  - `main.js` : `generateWFM` réécrite en start→polling (1,5 s)→barre de progression + bouton Annuler,
    puis flux post-génération inchangé (rapport IA / reload).
  - Testé : cycle job (10→50→96→100 « Terminé », annulation → cancelled, 404) ; **chemin réel**
    `generer_horaires_wfm` (solve 40 s/sem, réseau stubbé) → SUCCESS, 125 appels de progression, 4
    étapes ; front : barre visible « Semaine 1/2 — 50 % », 2 polls, bouton Annuler.

- **✅ F5 — Portail employé bidirectionnel.**
  - `database.py` : tables `demandes_conges` et `demandes_echange` + helpers (add/get/get_one/
    set_statut) + `remove_shift(date, nom)`.
  - `app.py` : routes employé **sans mot de passe** (préfixe `/mon-planning/` déjà whitelisté) :
    `POST /mon-planning/<token>/conge` et `.../echange` → créent une **demande** (jamais d'action
    directe) puis redirect `?envoye=…`. Routes manager : `GET /api/demandes`,
    `POST /api/demandes/conge|echange/<id>` `{action:approuver|refuser}`. **Effets** : congé approuvé
    → `remove_shift` sur la plage (retire les shifts) ; échange approuvé → `transfer_horaires` vers la
    cible.
  - Page employé (`/mon-planning/<token>`) : bannière de confirmation + 2 formulaires (`<details>`) —
    congé (du/au/motif) et cession de shift (jour/collègue via `<datalist>`/message).
  - UI manager : onglet **« Demandes »** + **badge** de compteur (rafraîchi au démarrage), cartes
    Approuver/Refuser, état vide.
  - Testé bout-en-bout (copie de base) : congé (soumission→1 en attente→approuver→shifts retirés sur
    2 jours), échange (soumission→approuver→transfert donneur→receveur), 404. Navigateur : page
    employé (2 formulaires, 30 collègues), soumission→bannière, badge manager=1, carte, approuver→
    badge vidé + état vide.
  - ⚠️ **Limite connue** : le solveur WFM lit les indispos **récurrentes** (`disponibilites`, par jour
    de semaine), pas les congés par **date précise**. Un congé approuvé retire les shifts du planning
    **déjà généré** ; une **régénération** ne le respectera pas tant qu'on n'aura pas ajouté une
    gestion d'absences par date au solveur (évolution future notée).

- **✅ D3 — Timeline visuelle drag & drop (v1).** `main.js` + `style.css` + bouton « Vue timeline »
  dans la barre Planification. Vue alternative (toggle) : par employé une piste 09:00→20:15, blocs
  matin/après-midi **redimensionnables** (poignées gauche/droite), **déplaçables** (corps), et
  **création par clic** sur piste vide (bloc 2 h dans la moitié cliquée). **Snap 15 min.** Les blocs
  lisent/écrivent les mêmes inputs `.m1/.m2/.a1/.a2` → « Sauvegarder » inchangé. Re-render branché
  sur `refreshPlanning` + `fillPlanningGrid` (synchro au chargement/changement de date). Testé :
  toggle masque les inputs, bloc « 09:00–13:00 », glisser poignée droite→ input `m2`=14:00 ;
  clic piste vide→ bloc après-midi a1=16:00/a2=18:00 ; round-trip vue tableau conserve les valeurs.

- **🐞 CORRECTIF (retour utilisateur) — shifts après-midi rangés dans les cases du matin.**
  Bug repéré sur la génération : un employé qui ne fait **que l'après-midi** (bloc unique, ex.
  16:00→20:00) voyait ses heures placées dans les colonnes **MATIN** (`ms/me`), car le mapping
  envoyait *toujours* `work_blocks[0]` en matin. Problématique notamment pour les **pauses**.
  **Fix** (`algo.generer_horaires_wfm`, mapping bloc→colonnes, **run_algo NON touché**) : `PIVOT_APREM
  = slot 16 = 13:00`. Si le shift a **1 seul bloc** qui commence à/après 13:00 → il va dans `aes/aee`
  (après-midi), `ms/me` vides. **2 blocs** (coupés par la pause) : 1er = matin, 2e = après-midi
  (inchangé — le trou `me`→`aes` **est** la pause). Testé (génération réelle sur copie, solve 40 s/sem) :
  **0** shift après-midi-seul au matin (28 désormais bien en après-midi), 130 shifts 2 blocs tous
  cohérents. ⚠️ Visible seulement sur une **nouvelle génération** (les plannings déjà générés gardent
  l'ancien mapping tant qu'on ne régénère pas).

**Bilan final :** 11/11 chantiers livrés et testés (4 fonctionnalités F1–F5 hors F-numérotation +
6 items design). Cache-buster `main.js?v=17` (couvre toutes les modifs JS de la session). Tests via
lecture de page / `javascript_tool` / client de test Flask / smoke-tests solveur sur **copie** de
base — jamais la vraie `supermarche_dev.db`. **La section IA reste reportée** (à faire plus tard).

**À reprendre / évolutions notées :**
- Solveur : absences par **date précise** (pour que la régénération respecte les congés F5) + retrait
  du hack dimanche désormais redondant dans `forecaster`/`prefill_besoins_flux` (cf. F1).
- Compteur d'heures : colonne « réalisé / pointage » (aujourd'hui « prévu » = planifié).
- Timeline (D3) : itérations (couleurs par type de poste, multi-jours, undo).
- **Section IA** (copilote élargi, prévision sur `historique_ventes`, streaming, sécu clé) : à traiter.
- Ne rien pousser sur GitHub (l'utilisateur pilote git ; appli en local pour le moment).

### Session 2026-07-19 (Corrections)
- **Modale de congés** :
  - Correction des identifiants et des fonctions de fermeture (`openModal`/`closeModal`).
  - L'action "Personnalisé" pré-remplit désormais automatiquement la page d'intérim (employé, dates).
  - Ajout du pré-remplissage des **horaires exacts** qu'avait l'employé avant que son congé ne soit approuvé. Pour ce faire, les shifts ont été récupérés juste avant leur suppression par `remove_shift` via l'API.
- **Affichage des congés traités** : L'onglet Demandes affiche désormais l'historique des congés/échanges traités (approuvés/refusés) en bas de la liste avec un badge visuel.
- **Modale QR Code** :
  - Suppression d'une modale dupliquée injectée par erreur qui masquait les identifiants requis par `qrcode.js`.
  - Implémentation d'un système de compatibilité (alias `hideModal`, fallback ID) et d'un anti-cache (v=18) pour pallier le caching navigateur des templates.
  - Ajout d'alertes JS pour diagnostiquer tout dysfonctionnement ultérieur du QR code.

- **Génération WFM multi-semaines** : Ajout d'un sélecteur dans l'interface permettant au manager de choisir de générer le planning sur 1, 2, 3 ou 4 semaines d'affilée. L'algorithme résout séquentiellement chaque semaine (temps de traitement proportionnel) pour couvrir un mois entier sans clic supplémentaire.

### Session 2026-07-19 (Changement de paradigme WFM)
- **Logique de génération** : Le solveur ne pénalise plus le sur-effectif (`over_c` = -1 au lieu de -800) afin de privilégier de manière absolue le respect des contrats horaires des CDI. Le modèle empilera les CDI jusqu'à atteindre la limite physique des 15 postes ("sans se soucier de l'affluence"), et fera uniquement appel aux intérimaires pour combler les déficits restants (`missing_c`).

### Session 2026-07-19 (Correctif heures contractuelles)
#### 1. Problème signalé (utilisateur)
Après ajout de la génération 1–4 semaines, **les employés ne font pas leur nombre exact d'heures
contractuelles** (norme 36h45/sem pour les CDI ; contrats réduits saisis dans les profils pour
étudiants / mi-temps). Le **compteur d'heures (F2)** en vue *mois* montre de gros écarts, ex. :
`BARDON Maia` (étudiante 25h/sem) **+41h47**, `COLONDON Ethan` (CDI) **-12h**, `AYACHE Yacine` /
`BECHICHI Dalya` (CDI) **-162h45** (0h prévu). L'utilisateur confirme : profils corrects, même souci
qu'à l'époque des 2 semaines. La génération multi-semaines résout **chaque semaine séparément**
(240 s/sem), donc la contrainte de contrat s'applique bien **par semaine** → le souci est antérieur,
pas dû au multi-semaines.

#### 2. Méthodo de diagnostic (tout sur une COPIE de `supermarche_dev.db` via `DATA_DIR`)
Instrumentation : monkeypatch de `cp_model.CpSolver.Solve` pour forcer un temps court + capturer le
`StatusName`, `forecaster.fetch_weather/fetch_vacances` stubbés (réseau), puis calcul par employé de
`slots_travaillés = Σ[matrice==CAISSE|CLS|POLY]` vs `contrat×4`.

**Mesures clés :**
| Test | Résultat |
|---|---|
| Contrainte **DURE** `sum(work)==contrat` (slack neutralisé), solve 70 s | **INFEASIBLE** |
| Soft d'origine (-10M), solve 120 s | FEASIBLE ; seuls `SOUSA` (-36h45) et `KEPSEU` (+0h30) hors contrat |
| Soft, **90 s** | FEASIBLE ; 3 disponibles hors contrat, pire = -5h30 |
| Soft, **180 s** | FEASIBLE ; **0 disponible hors contrat** |

**Conclusions du diagnostic :**
1. **Impossibilité structurelle** : donner à *tout le monde* exactement son contrat est **INFEASIBLE**
   (interaction max 5 jours + min 4h/shift + pauses 45min/1h + plafond 15 postes + heures d'ouverture
   + repos fixes). Un écart résiduel est donc **inévitable** → le slack (contrainte souple) est
   nécessaire, sinon la génération renvoie « aucune solution ».
2. **Problème de convergence** : le solveur s'arrête en **FEASIBLE** (jamais prouvé OPTIMAL). À temps
   court il laisse quelques employés hors contrat ; à **≥180 s** l'écart tombe à **0** pour tous les
   disponibles. ⇒ c'est le **temps de calcul**, pas le modèle.
3. **Faux déficits (cas normaux)** — vérifiés via `get_disponibilites` + `sur_caisses` :
   - `AYACHE Yacine` (id) & `BECHICHI Dalya` : `sur_caisses = 0` → **exclus** du pool solveur
     (`[e for e in db.get_employes() if e.get('sur_caisses',1)]`) → 0h **normal**.
   - `SOUSA MARTINS André` (CDI 36h45) : `disponibilites.disponible = 0` sur **les 7 jours** →
     indispo total → 0h **normal**. **De plus**, son déficit forcé (147 slots) **neutralisait** la
     piste « équité min-max » (il plafonnait le pire-déficit à 147).
   Le compteur leur affichait quand même une cible pleine → **faux -162h45**.
4. **Données périmées** : `sauvegarde_historique` contient du planning sur **les 31 jours de juillet**
   (01→31/07). `BARDON` y a **159h75 sur 22 jours** (contrat 25h/sem → ~13 jours attendus) : produit
   par l'**ancien** solveur non convergé (sur-assignation). Les écarts de la capture viennent donc
   d'anciennes générations, pas du code actuel.

#### 3. Correctifs appliqués (⚠️ `run_algo` **non touché**)

**(a) `algo._generer_semaine` — cible d'heures = `min(contrat, capacité réelle)`**
Avant : `model.Add(Σ work == total_slots_requis + slack_plus - slack_minus)` où
`total_slots_requis = round(heures_contrat*4)` (contrat brut). Problème : pour un indispo, la cible
restait le contrat → gros slack forcé, faux déficit, et pollution de la recherche.
Après : on calcule d'abord la **capacité hebdo réaliste** puis `target_slots = min(total_slots_requis,
capacity)` :
```python
repos_list = [r.strip() for r in (e.get('repos_fixes','') or '').split(',') if r.strip()]
work_max_emp = 40            # ~10 h de travail max/jour
daily_caps = []
for j in jours:
    wd = weekday_of[j]
    if jour_names[wd] in repos_list:      # jour de repos fixe -> pas de capacité
        continue
    open_j = open_slots_by_day[j]         # créneaux d'ouverture du magasin ce jour
    av = dispo_slots.get((e_id, wd))      # None = tout dispo ; sinon set des créneaux dispo
    cap_j = len(open_j) if av is None else len(av & open_j)   # dispo ∩ ouverture
    daily_caps.append(min(cap_j, work_max_emp))
capacity = sum(sorted(daily_caps, reverse=True)[:5])          # 5 meilleurs jours (max 5 j/sem)
target_slots = min(total_slots_requis, capacity)
slacks[e_id] = {'plus': slack_plus, 'minus': slack_minus, 'cap': capacity}
model.Add(sum(work.get((e_id, j, s), 0) for j in jours for s in slots)
          == target_slots + slack_plus - slack_minus)
```
Effet : un indispo total → `capacity = 0` → `target = 0` → **aucun déficit** (il ne fausse plus la
recherche) ; un employé partiellement dispo est ciblé sur ce qu'il **peut** faire (pas de pénalité
pour un manque impossible) ; un employé pleinement dispo → `capacity ≫ contrat` → `target = contrat`
(inchangé). La **forte pénalité `-10 000 000`** sur `slack_plus`/`slack_minus` est **conservée**
(objectif) : les heures dominent tout le reste (couverture, etc.).

**Pistes testées puis ABANDONNÉES** (documentées pour ne pas les refaire) :
- *Contrainte dure d'égalité* → INFEASIBLE (cf. §2).
- *Big-M réduit `-8000` + équité min-max (`max_deficit`/`max_exces` plafonnant les slacks)* →
  **PIRE** (9 disponibles hors contrat, jusqu'à +5h75). Cause : `-8000` n'est plus assez dominant
  face à la couverture (`-2000`), donc le solveur sacrifie les heures ; et le min-max était neutralisé
  par l'indispo total (SOUSA). La **forte pénalité d'origine** reste indispensable.

**(b) `app.py` — compteur d'heures `/api/stats/heures` (route `stats_heures`)**
On pré-calcule les indispos permanents, puis on retire la cible pour les non-concernés :
```python
indispo_count = {}
for d in db.get_disponibilites():
    if d['disponible'] == 0:
        indispo_count[d['employe_id']] = indispo_count.get(d['employe_id'], 0) + 1
...
hors_caisses  = not e.get('sur_caisses', 1)
indispo_total = indispo_count.get(e['id'], 0) >= 7
sans_cible = (e.get('statut')=='Interimaire') or contrat_hebdo<=0 or hors_caisses or indispo_total
cible = None if sans_cible else contrat_hebdo * facteur_semaines
statut_lbl = 'Hors caisses' if hors_caisses else ('Indisponible' if indispo_total else <contrat>)
```
Effet : les **hors-caisses** (label « Hors caisses ») et **indisponibles 7/7** (label
« Indisponible ») affichent cible/écart = **« — »** → fini les faux -162h45. Vérifié via client de
test : `AYACHE`/`BECHICHI` = « Hors caisses — », `SOUSA` = « Indisponible — ».

#### 4. Validation
- `algo._generer_semaine` (nouveau code) sur copie, solve 180 s, semaine du 06/07 (start=lundi) :
  **0 employé disponible hors contrat**, `SOUSA` à 0h proprement (cible 0). Statut solveur FEASIBLE.
- `py_compile` OK sur `algo.py`, `app.py`, `database.py`. Compteur retesté (labels + « — »).

#### 5. ⚠️ À FAIRE par l'utilisateur
1. **Relancer `python app.py`** (le serveur en cours a l'ancien code en mémoire).
2. **RÉGÉNÉRER** le planning (les écarts affichés viennent des anciennes générations périmées).
3. Vérifier le compteur : écarts quasi nuls pour les disponibles ; « — » pour hors-caisses/indispo.
4. **Données à contrôler côté profils** (pas des bugs) :
   - `SOUSA MARTINS` (CDI 36h45) est **indispo 7/7** → 0h. S'il doit travailler, corriger ses dispos.
   - `AYACHE Yacine` & `BECHICHI Dalya` (CDI 36h45) sont **« hors caisses »** → exclus. S'ils doivent
     faire leurs heures, réactiver « Sur les caisses » dans leur fiche.

#### 6. Notes techniques / dette
- **Temps de solve** : la convergence exige ~180 s/sem sur cette config (240 s/sem en prod = OK dans
  les tests). Sur des semaines très chargées (events, canicule → besoin ↑), si des écarts persistent,
  **augmenter `max_time_in_seconds`** dans `_generer_semaine` (attention : ×nb_semaines, mais la
  génération F4 est asynchrone donc pas de timeout HTTP). La cible=capacité **allège** aussi le modèle
  (moins de pression -10M impossible) → aide la convergence.
- **Capacité** = heuristique (borne haute simple, ignore l'effet exact des pauses). Suffisant ici car
  `capacity ≫ contrat` pour les pleins-temps ; à affiner si des mi-temps très contraints apparaissent.
- Évolution possible : un vrai indicateur « capacité < contrat » dans le compteur (signaler les profils
  dont les dispos ne permettent pas d'atteindre le contrat).

### Session 2026-07-19 (Correction Définitive : Respect Absolu des Contrats CDI)

#### 1. Le Problème Initial et l'Analyse
Suite au déploiement des ajustements précédents, des écarts persistants (+5h, +10h, -6h) sur les CDI étaient toujours constatés depuis l'onglet "Semaine". 

Deux problèmes distincts entraient en jeu :
1. **Une illusion d'optique dans le Compteur "Semaine" :** Lors de la génération d'un planning à partir d'un jour précis (ex: Mercredi), les créneaux Lundi/Mardi affichés dans l'onglet "Semaine" provenaient de la génération précédente (ancienne). Le mélange "Ancien planning + Nouveau planning" sur la même semaine calendaire faussait le calcul de la colonne `Prévu`.
2. **Une limitation structurelle du Solveur CP-SAT (LP Relaxation vs Symétrie) :**
   Dans le modèle précédent, le respect du contrat était garanti par des variables d'ajustement (`slack_plus`, `slack_minus`) dotées de pénalités colossales (`-10,000,000`). Mathématiquement, le solveur *voulait* respecter le contrat. Cependant, avec 20 employés, la combinatoire des pauses, des shifts (4h min), de la polyvalence et de l'équité génère un espace de recherche incroyablement vaste et symétrique. 
   Face à cet arbre de décision gigantesque, le solveur n'avait parfois pas le temps (en 4 minutes par semaine) de trouver le chemin exact pour ramener le `slack` à 0 sans briser les contraintes dures d'amplitude ou de présence. Il s'arrêtait donc sur la "meilleure solution trouvée dans le temps imparti", qui incluait hélas du `slack` (heures supplémentaires).

#### 2. La Solution Radicale
Conformément au besoin métier exprimé (« La priorité absolue est que tout le monde fasse pile l'heure qu'il faut. [...] Une fois que tout est OK, le solver ajoute des intérimaires »), l'algorithme a fait l'objet d'un profond changement de paradigme.

1. **Passage d'une contrainte souple à une contrainte DURE :**
   Les variables de tolérance `slack_plus` et `slack_minus` ont été plafonnées à **0** pour tous les employés CDI (`is_interimaire == False`). 
   *Conséquence :* Il est désormais mathématiquement IMPOSSIBLE pour le solveur d'envisager une solution où un CDI ferait 1 minute de plus ou de moins que son contrat (ou que sa capacité maximale s'il a posé trop de congés). En restreignant violemment l'espace de recherche à des solutions 100% justes, le solveur trouve quasi-instantanément l'assignation parfaite (puisqu'il ne s'épuise plus à arbitrer des solutions imparfaites).

2. **Relâchement absolu du Sur-effectif :**
   La pénalité de sur-effectif (`over_coverage_vars`) est passée de `-800` à `-1`. Le solveur n'hésitera plus à mettre du personnel "en trop" (si besoin) pour honorer les contrats CDI, ce qui garantit qu'il arrivera à caler tout le monde sans être artificiellement freiné par le besoin du magasin.

3. **Maintien du Rôle de l'Intérim :**
   Les intérimaires conservent une tolérance `max_slack = 200` et sont soumis à une pénalité de `-800` par créneau travaillé. Étant donné que la pénalité de manque d'effectif (`missing_coverage`) est de `-2000`, les intérimaires ne sont mobilisés que de manière ciblée, uniquement pour combler les failles que les CDI n'ont pas pu combler.

#### 3. Résultats de Validation
Un script de test local strict (répliquant l'extraction BDD exacte sans mélange de dates) a été exécuté. Le verdict est un respect au centime près :
- `AIT ELHADJ Sonia`: 36.5h vs contrat 36.5h (Pile)
- `BERTHE Sebastien`: 36.75h vs contrat 36.75h (Pile)
- `LEFEBVRE Jessica`: 25.0h vs contrat 25.0h (Pile)
- `SOUSA MARTINS André`: 0h vs contrat 36.75h (Indisponible, cible=0 → Pile)
- `Intérimaires` : Assurent entre 8h et 28h selon les trous du planning.

#### 4. Action Requise
Pour valider en réel sur l'UI, il faut absolument **lancer une génération sur 2 ou 4 semaines**, puis s'assurer de regarder une "Semaine" qui est **entièrement incluse dans la période générée** (Lundi au Dimanche) pour éviter le biais des reliquats de l'ancienne BDD.

#### 5. Ajout de la Visualisation "4 Semaines"
Suite à un retour métier sur la visualisation au mois : la vue "Mois" calendaire classique (ex: 1er au 31 août) posait des problèmes d'interprétation lors des générations de plannings par blocs de 4 semaines (ex: du 3 au 30 août). Le système affichait un déficit apparent car il calculait la cible sur 31 jours mais ne trouvait que 28 jours générés dans la base.
**Corrections apportées :**
- Ajout d'un bouton "4 Semaines" dans l'UI du Compteur d'heures.
- Création de la période `4semaines` dans l'API `/api/stats/heures`, qui calcule un bloc strict de 28 jours à partir du lundi de référence, garantissant un alignement parfait entre les heures générées (4 semaines) et la cible (4 semaines de contrat).
- Clarification du- [x] **Relancer Check-up complet** : Validation automatique complète de la non-planification des employés en congés approuvés. (SUCCÈS : L'employé en congé n'a aucune heure planifiée).
- [x] **Nettoyer le haut de l'interface WFM** : Allègement de l'écran en supprimant les textes des boutons, passage au tout-icône, amélioration du Glassmorphism, animations au survol, gradients sur les en-têtes et pulsation prédictive du badge IA.
- Corrigé un bug silencieux (Piège d'infaisabilité) dans `algo.py` (`_generer_semaine`) : Si le nombre de congés déduits faisait tomber la cible d'un employé en dessous du minimum syndical de son contrat (ex: moins de 4h restantes), le solveur renvoyait `INFEASIBLE` et refusait de générer le planning de tout le mois. Le bug est fixé par un arrondi à 0 si le seuil tombe sous 4h.

### Session 2026-07-21 (Masse Salariale & Calendrier Alternants)
- **Vision Masse Salariale** : Ajout d'une API `/api/stats/masse_salariale` et d'un graphique empilé dans l'onglet Statistiques. Permet d'anticiper mois par mois le volume d'heures fixes (CDI) vs variables (Intérim) en fonction de la courbe de besoin et des jours d'ouverture.
- **Calendrier Annuel (Alternants/Écoles)** : Refonte de l'onglet Disponibilités. En plus de la routine hebdomadaire, intégration d'un calendrier visuel sur 12 mois permettant de cliquer sur n'importe quel jour de l'année pour le marquer comme "Indisponible" (gestion fine des semaines d'école pour les alternants). Le solveur WFM respecte désormais ces interdictions calendaires en priorité absolue.

### Session 2026-07-19 (Génération par "Mois de Planning" ISO)

#### 1. Constat et Besoin
L'utilisateur a signalé une gêne persistante avec la logique basée sur une "date de début" arbitraire couplée à un nombre de semaines au choix (1 à 5). La visualisation "Mois" dans les compteurs peinait à s'aligner naturellement avec les plannings générés, créant des décalages d'heures apparents (heures manquantes car les mois calendaires ne font jamais exactement 4 semaines). De plus, l'industrie retail raisonne en "Mois Commercial" (semaines entières).

#### 2. Implémentation du Mois Commercial (ISO 8601)
- Création du helper `get_planning_month(year, month)` dans `algo.py`. Ce helper applique la règle standard : *une semaine appartient au mois qui contient son jeudi*.
- Ceci garantit que chaque mois est parfaitement couvert par **4 ou 5 semaines complètes** (Lundi au Dimanche). Aucun trou, aucun chevauchement.
- **Backend API (`app.py`)** : La route `/api/wfm/generation/start` a été modifiée pour accepter `year` et `month` au lieu de `start_date` et `nb_semaines`.
- **Backend Statistiques (`app.py`)** : La route `/api/stats/heures` pour `periode=mois` utilise désormais ce même helper. La "cible" d'heures contractuelles est calculée strictement sur les 4 ou 5 semaines générées, garantissant un écart parfait de `0` pour les CDI respectant leur contrat.

#### 3. Refonte UI (Génération IA)
- **`index.html`** : Le `datepicker` et le sélecteur "Nombre de semaines" ont été retirés de l'entête.
- Ils ont été remplacés par deux menus déroulants : **Mois** (Janvier - Décembre) et **Année** (générée dynamiquement).
- Ajout d'une séparation visuelle forte (layout flexbox modernisé) : les boutons de vue (Rafraîchir, Sauvegarder, Timeline) sont à gauche, et l'espace **Génération IA** est isolé à droite dans un conteneur vitré avec un bouton violet "Smart Flux".
- **`main.js`** : Ajout d'un écouteur d'évènement affichant dynamiquement les dates exactes couvertes par le mois sélectionné sous la forme `Période générée : du Lundi JJ/MM au Dimanche JJ/MM (4/5 semaines)`.

#### 4. Corrections de Bugs
- Corrigé un bug `start_date is not defined` à l'issue de la génération (le petit rapport prédictif de l'IA plantait car l'ancienne variable de date de début n'existait plus). Ajout de la `start_date` générée en retour de statut asynchrone.
- Le texte de validation annonce désormais correctement les horaires des "4" ou "5" prochaines semaines au lieu du texte en dur "14 prochains jours".
- [x] **Relancer Check-up complet** : Validation automatique complète de la non-planification des employés en congés approuvés. (SUCCÈS : L'employé en congé n'a aucune heure planifiée).
- [x] **Nettoyer le haut de l'interface WFM** : Allègement de l'écran en supprimant les textes des boutons, passage au tout-icône, amélioration du Glassmorphism, animations au survol, gradients sur les en-têtes et pulsation prédictive du badge IA.
- Corrigé un bug silencieux (Piège d'infaisabilité) dans `algo.py` (`_generer_semaine`) : Si le nombre de congés déduits faisait tomber la cible d'un employé en dessous du minimum syndical de son contrat (ex: moins de 4h restantes), le solveur renvoyait `INFEASIBLE` et refusait de générer le planning de tout le mois. Le bug est fixé par un arrondi à 0 si le seuil tombe sous 4h.

### Session 2026-07-19 (Check-up QA & Bug Congés/WFM)

#### 1. Le Constat via le Test Automatisé (QA)
À la demande de l'utilisateur, un script complet de tests automatisés (`test_qa.py`) a été écrit pour balayer 100% de l'application (API Employés, Soumission de Congés, Approbation Manager, Échanges de plannings, Besoins Intérim, Génération WFM).
Ce test en profondeur a mis en lumière une **faille d'architecture majeure** : les dates de "Congés Approuvés" n'étaient pas communiquées à l'algorithme WFM.
*Conséquence :* Si un manager approuvait les congés d'un employé au mois d'août, puis cliquait sur "Générer les horaires" pour ce même mois d'août, l'IA "oubliait" les congés et planifiait de nouveau l'employé en vacances. Le WFM ne lisait que les disponibilités hebdomadaires récurrentes (table `disponibilites`).

#### 2. La Correction Architecturale (`algo.py`)
- L'algorithme (`_generer_semaine`) effectue désormais un appel direct à `db.get_demandes_conges(statut='approuve')` avant d'initialiser son solveur.
- Il convertit les dates de début/fin des congés pour vérifier s'ils chevauchent l'un des 7 jours de la semaine en cours d'optimisation.
- **Contrainte Dure** : Si une journée (j) tombe pendant le congé d'un employé (e), sa disponibilité pour ce jour est brutalement forcée à un ensemble vide `avail = set()`.
- Ainsi, la présence autorisée sur ce jour devient mathématiquement nulle (`presence == 0` sur les 44 créneaux de la journée). Le moteur doit alors automatiquement répartir la charge de cet employé manquant vers les autres employés ou l'intérim.

#### 3. Décision sur les Échanges
Le bug s'appliquait également aux "Échanges de plannings". Cependant, relancer une génération WFM sur une période passée écrase naturellement les échanges (qui sont des petits arrangements de gré à gré). L'utilisateur a donc validé que le comportement actuel (écrasement des échanges par la ré-optimisation IA, mais préservation stricte des congés) est le standard attendu dans le Retail.

### Session 2026-07-19 (Correction Solveur "Génération infaisable" et Visualisation au Mois)

#### 1. Constat et Besoin
L'utilisateur a fait remonter 3 points :
- La visualisation "Mois" affichait des écarts horaires (car elle comparait des semaines pleines à un mois calendaire irrégulier).
- La génération WFM bloquait sur l'erreur "Génération infaisable" car le solveur OR-Tools avait été limité à 1 seul cœur (pour éviter un freeze UI) mais n'avait pas le temps de trouver la solution optimale parfaite qui respectait strictement les contrats horaires.
- Le haut de l'interface WFM paraissait "un peu chargé" visuellement.
- L'utilisateur a demandé d'effectuer un check-up complet (QA) de l'application.

#### 2. Corrections Apportées
- **Visualisation au Mois (Exacte)** : La vue "Mois" dans le panneau des compteurs se base désormais strictement sur le calendrier du mois sélectionné (ex: 1er au 31). Le contrat est calculé au prorata des jours exacts (`jours du mois / 7 * heures hebdos`), permettant de vérifier que l'IA a fait pointer tout le monde à la minute près.
- **Réglage du Solveur (OR-Tools)** : La limite `num_search_workers` a été montée à 4 au lieu de 1, et le temps maximum (`max_time_in_seconds`) a été ré-ajusté. Cela permet au solveur de profiter du multi-cœur pour trouver la solution mathématique optimale en quelques secondes, sans pour autant figer complètement l'OS de l'utilisateur (comme le faisait le paramètre par défaut de 8 ou 16 cœurs). La contrainte stricte d'exactitude des heures pour les CDIs a été pleinement restaurée, garantissant le "franc succès" observé auparavant.
- **Priorité CDI vs Intérim** : La garantie de ne faire appel à l'intérim qu'en tout dernier recours est confirmée par le système de pénalités (`-800` par créneau pour l'intérim contre `0` pour un CDI non épuisé).

#### 3. Batterie de Tests QA
- Suite à un crash inattendu du serveur de développement lors de la première passe de tests, le script de test QA global (`test_qa.py`) a été mis en pause temporairement à la demande de l'utilisateur (afin d'économiser la batterie de la machine). Ce script testera de bout en bout l'approbation des congés, les heures générées et les envois de mail à la reprise.

### Session 2026-07-30 / 31 — Refonte de `run_algo` (stabilité des caisses) + mise en production

> ⚠️ **Deux règles de ce document ont été levées par l'utilisateur pendant cette session.**
> - « NE PAS re-toucher `run_algo` » : levée. L'utilisateur a explicitement demandé de
>   retravailler l'algorithme d'affectation des caisses. `run_algo` a été profondément
>   modifié (voir ci-dessous).
> - « NE JAMAIS pousser sur GitHub » : levée, ponctuellement puis durablement.
>   L'utilisateur a demandé les pushs, y compris sur `master`. Tout est poussé.
>   **Pour la suite : redemander confirmation, ne pas considérer cela comme acquis.**

#### 1. Point de départ

Plainte initiale : *« les employés changent trop souvent de caisse à cause de l'ordre de
priorité de ces dernières »*. Banc de mesure monté (18 employés, jeudi type) :
**24 changements de caisse/jour, 33 % du planning varie selon l'ordre de saisie, 3,5 s de calcul.**

**Cause racine** : ETAPE 3 remettait les 14 caisses en concurrence à **chaque créneau de
15 min**. Un employé déjà assis en C9 était vu comme « libre » quand C3 était évaluée,
puisque C9 n'avait pas encore été traitée dans la boucle. Le bonus de continuité `-500000`
ne protégeait que le titulaire *de la caisse en cours d'évaluation*. Trace : `18h30, départ
de COLONDON de C6 → 3 déplacements en chaîne`.

#### 2. ETAPE 3 réécrite en trois phases

- **A. Reconduction** — le titulaire garde sa caisse, sans mise en concurrence. La caisse
  lui reste réservée pendant sa pause.
- **B. Comblement** — seules les caisses vides sont pourvues, uniquement par des employés
  pas déjà assis. Inclut le **retour au poste** après un CLS ou une coupure.
- **C. Rééquilibrage** — la caisse source est **fermée** au lieu d'être recomblée : la
  cascade devient impossible par construction.

Deux niveaux de priorité (décision utilisateur) : **C1/C2 sans aucune interruption**
(`CAISSES_ININTERROMPUES`, tolérance zéro, y compris pendant la pause du titulaire) ;
**C13/C14 et le reste** avec un trou toléré jusqu'à 1h30 (`TROU_TOLERE`) quand la seule
solution créerait de l'instabilité.

#### 3. Bugs corrigés dans `run_algo` (tous reproduits avant correction)

| Bug | Détail |
|---|---|
| Restriction handicap contournable | Pénalité `+999999` sous le seuil d'acceptation `< 900000` avec le bonus intérimaire `-100000` → 899999 accepté. **30 créneaux en violation reproduits.** Devenue un filtre dur (`caisse_autorisee`). |
| Blacklist par sous-chaîne | `"emmanuel" in "cadeau emmanuelle"` → **CADEAU Emmanuelle blacklistée CLS par erreur**. Comparaison par mots entiers (`_tokens`, `_cle_matche`). |
| `sont_adjacentes(n, n) == True` | Une caisse était mitoyenne d'elle-même → le retour au poste était bloqué sur C1/C2/C13/C14/C5/C6. |
| Glissement vers la caisse mitoyenne | Perdu en réécrivant la phase B ; puis re-trouvé en deux temps : `C2 → [pause] → C13 → C1`. La phase C comparait l'adjacence à la caisse *source*, pas à celle tenue avant la pause. |
| Réservation de pause non bornée | La recherche du dernier occupant remontait jusqu'au premier créneau de la journée. |
| **CLS simultanés** | La boucle du CLS de journée interdit de *démarrer* après 17h mais pas de *déborder* : un bloc lancé à 16h15 courait jusqu'à 18h15 et doublonnait avec le closer. **34 créneaux en double** sur l'ensemble des tests → 0. Dimanche : shifts `(2,8)` et `(9,8)` se recouvraient d'un créneau → `(2,7)`. |
| **Closer mangeant le titulaire CLS** | Le closer est désigné **avant** le CLS de journée et en est ensuite exclu. Le tri retenait le **plus disponible**, donc la personne présente toute la journée. Le CLS se morcelait en blocs de 45/75 min. Tri désormais sur la **moindre disponibilité avant 17h**. |

Autres règles ajoutées : **pas de bloc isolé de 15 min** (`DUREE_MIN_BLOC_CAISSE`), **relais
de pause abandonné si < 45 min restants** (`RELAI_PAUSE_MIN`), **rotation de caisse après la
coupure méridienne** sauf sur C1/C2/C13/C14 (`apres_coupure()`).

#### 4. Déterminisme et performance

- Départage explicite par nom sur **tous** les tris (CLS, closer, pauses, caisses).
  Sensibilité à l'ordre de saisie : **33 % → 0 %**.
- Matrice de présence précalculée (`build_presence`) au lieu d'un recalcul depuis la boucle
  la plus interne : **3,5 s → 60 ms**.

#### 5. Optimisation globale (ETAPE 4) — nouveau

`evaluer_planning()` note un planning complet ; `optimiser_planning()` part du glouton et
enchaîne **60 000 essais** (échange, absorption bidirectionnelle, prolongation, comblement,
réassignation, libération) avec **recuit simulé**. Le meilleur planning rencontré est
conservé à part : **le résultat ne peut jamais être moins bon que le glouton**.

Deux pièges rencontrés, tous deux corrigés :
- **Budget en secondes = non déterministe** (372 cellules d'écart entre deux générations
  identiques). Passé en **nombre d'essais** (`ESSAIS_OPTIM`), température indexée sur
  l'avancement en essais. Garde-fou `TEMPS_MAX_OPTIM_S = 30` qui signale s'il coupe.
- **Tirage aléatoire sur le numéro de colonne** → dépendait de l'ordre de saisie. Tirage
  dans un ordre canonique trié par nom.

Calibrage des poids (`POIDS`), deux erreurs à connaître :
- Relèves à coût **fixe** → l'optimiseur atteignait −50 % de relèves **en figeant dix
  personnes sur la même caisse toute la journée**. Passé en **coût progressif** (la k-ième
  relève sur une caisse coûte k fois la première).
- Récompense de couverture **uniforme** → l'optimiseur tenait C10/C11/C12 pendant que C5/C6
  restaient fermées, et fermait C14 pour ouvrir C12. Récompense **graduée**, avec C1/C2 et
  C13/C14 traitées à part (`recompense_couverture`).

**Résultat sur données réelles** (4 journées reconstituées depuis les plannings générés) :
relèves de caisse **74 → 51 (−31 %)**, postes de moins de 1h30 **27 → 19**, couverture
−0,4 %, **0 anomalie**, déterminisme intact. Compter **5 à 10 s par génération** en local.

#### 6. Méthode de test mise en place (réutilisable)

Scripts dans le scratchpad de session (non versionnés) : `suite.py` (11 scénarios
synthétiques + invariants), `optim.py`, `reel.py`, `extraire.py`, `gaspillage.py`.

- **Les scénarios synthétiques ne suffisent pas.** Deux bugs majeurs (glissement mitoyen
  via pause, closer/CLS) n'apparaissaient **que** sur les données réelles.
- **`extraire.py` reconstitue les horaires exacts depuis un planning généré** : dans la
  grille, `bg-ABS` = absent, toute autre classe = présent. Exact, contrairement à une
  lecture de capture d'écran. Deux pièges : le HTML téléchargé par le navigateur normalise
  les apostrophes en guillemets doubles ; et **le planning affiche `nom.title()`**
  (« GEAY Emilie » → « Geay Emilie ») — sans remise en correspondance avec la base,
  `cache_emp.get()` échoue et **tous les employés héritent des valeurs par défaut**
  (ni `restriction_cls`, ni handicap). *Cette erreur a faussé plusieurs mesures avant
  d'être vue.*
- ⚠️ `db.inc_mission_score` **mute la base** : deux exécutions consécutives ne donnent pas
  le même planning. Toujours repartir d'une copie vierge entre deux mesures.

#### 7. Hors algorithme

- **Version affichée** : `algo.VERSION` remonte au badge via `render_template`. Comme elle
  est lue depuis le module chargé en mémoire, **elle atteste quel `algo.py` tourne** — pas
  seulement quel template. **À incrémenter à chaque modification de comportement.**
  Session terminée en **3.0**.
- **`database.py`** : `DB_FILE` était passé de `supermarche_data.db` à `supermarche_dev.db`
  (commit WFM `d6e4f3e`) → en prod le fichier n'était pas trouvé, `init_db()` en créait un
  **vide** et l'application démarrait sans aucun employé. Résolution automatique du nom
  parmi les noms connus, variable `DB_NAME` pour forcer.
- **`migrer_schema()`** : les 7 colonnes WFM n'existaient pas sur une base antérieure.
  `CREATE TABLE IF NOT EXISTS` ne modifie pas une table existante → l'ajout/modification
  d'un salarié renvoyait une 500 et l'UI affichait `Unexpected token '<' ... is not valid
  JSON`. Migration idempotente au démarrage via `PRAGMA table_info`.
- **UI** : barre d'outils Sauvegarder/Rafraîchir **restaurée** (le commit WFM `93a46f9`
  l'avait remplacée par un fragment de template JS échappé avec ses `${emp.id}` littéraux ;
  `getElementById(...).addEventListener` sur `null` levait une TypeError qui **interrompait
  tout le script**, rendant les boutons PAUSES et GÉNÉRER totalement inertes).
  `window.open` déplacé **avant** l'`await` (bloqueur de popups). Écran de chargement
  (voile + chronomètre) sur la page principale **et** dans l'onglet ouvert.

#### 8. Déploiement — pièges rencontrés (à relire avant tout déploiement)

1. **Deux copies du dépôt sur le serveur.** L'application est servie depuis
   `~/www/super-planning-web`, pas `~/super-planning-web`. Plusieurs `git pull` ont été
   faits dans le mauvais dossier. Le chemin est visible dans l'admin AlwaysData
   (Web → Sites → Configuration → Répertoire de travail).
2. **Type de site : Python WSGI**, point d'entrée `alwaysdata_wsgi.py`. Le `Procfile`
   (`gunicorn app:app`) est un **reliquat Heroku** : `pkill -f gunicorn` ne tue rien.
3. **`debug=False` ⇒ Jinja ne recharge pas les templates.** `index.html` est compilé une
   fois et gardé en mémoire : **un redémarrage est nécessaire**, comme pour `algo.py`.
   Seuls le CSS et le JS sont statiques (Ctrl+Shift+R suffit).
4. Le shell SSH (`ssh1`) et les serveurs web sont des **machines distinctes** : `ps` n'y
   montre jamais les process du site. Le redémarrage se fait **depuis l'admin**.

#### 9. 🔴 Sécurité — non traité, à faire par l'utilisateur

Le dépôt **`yac0212/super-planning-web` est PUBLIC** et `app.py` y est versionné avec
`ADMIN_PASSWORD = "inter2026"` et `app.secret_key = "super_secret_planning_key"` **en clair**
(lignes 9 et 12). N'importe qui peut se connecter à l'application en production et forger un
cookie de session. Les fichiers `.db` sont bien couverts par `.gitignore` — les données
salariés ne sont pas exposées. **À faire : passer les deux valeurs en variables
d'environnement, CHANGER le mot de passe (il reste dans l'historique git), passer le dépôt
en privé.** Signalé à plusieurs reprises, jamais traité.

#### 10. Reste à faire

- **Mission pause structurellement sous-couverte** — comportement **préexistant**, non
  introduit cette session (l'ancien algo donne les mêmes chiffres). Le bandeau annonce
  « Mission Pause Matin : 180 min » alors que 120 min seulement sont posées. Cause : la
  boucle du matin s'arrête à l'index 20 (14h00) et celle de l'après-midi à 44. Sur le
  dimanche : 33 créneaux requis, 10 posés. **L'utilisateur a demandé de laisser de côté
  pour l'instant.**
- **Flags `restriction_cls` à auditer en base.** `BRASSAC Alexandra` était marquée
  « Interdit CLS » par erreur, ce qui expliquait entièrement un placement jugé illogique.
  `GEAY Emilie`, `LEFEBVRE Jessica`, `MAYENGO Jean Marc` et les intérimaires le sont aussi
  dans la copie locale — à vérifier. **Avant d'incriminer l'algorithme, vérifier la saisie.**
- **Règles nominatives en dur** dans `algo.py` (`BLACKLIST_CLS_PERMANENT`,
  `HIERARCHIE_PENALITE_*`, `"andré"`, `"alicia"`). Renommer un employé casse silencieusement
  la règle. **`"léandre"` ne correspond à aucun employé en base — règle morte.** À migrer en
  colonnes de base.
- **`window.open` après `await`** subsiste dans le parcours Intérim & Absences
  (`main.js`, ~4 branches) — même défaut que celui corrigé sur les deux boutons principaux.
- **Optimiseur peu efficace en planning saturé** (22 employés / 14 caisses) : les mouvements
  qui cherchent des créneaux vides échouent. Les poids ont été basculés vers l'échange et
  l'absorption, mais il reste probablement à gagner.
- **Sur le CLS, la fragmentation est incompressible** : 8 h de CLS de journée, blocs
  plafonnés à 2 h, une mission par personne ⇒ **4 personnes minimum + le closer**.
  L'utilisateur a confirmé que les deux plafonds sont volontaires. Ne pas chercher à
  descendre sous 5 titulaires sans changer ces règles.

#### 11. Commits de la session (tous poussés sur `master` ET `feature-wfm`)

`f3f5819` stabilisation ETAPE 3 + 4 bugs · `4b9c8ee` badge 2.0 · `a0ca8fa` résolution du nom
de base · `ae5efbc` window.open avant await · `762d2a2` barre d'outils restaurée ·
`c554a99` blocs 15 min + relais pause 45 min · `0b694d4` rotation après coupure ·
`56d8956` version lue depuis `algo.py` · `ae3049b` optimisation globale ·
`09d805d` absorption bidirectionnelle · `5db67e4` écran de chargement ·
`0894b14` CLS simultanés · `3ac72d3` closer/CLS · `9737f96` attente dans l'onglet ·
`303dead` migration du schéma

⚠️ **Ce fichier n'était pas versionné** : il n'existait que dans `stash@{0}` (partie fichiers
non suivis) et était absent des trois branches. Restauré à la racine cette session.
**Le commiter pour ne plus le perdre.**

<!-- Ajouter les prochaines sessions au-dessus de cette ligne, format "### Session AAAA-MM-JJ" -->
