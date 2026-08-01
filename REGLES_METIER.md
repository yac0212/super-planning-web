# Inventaire des règles métier — affectation des caisses

État au 31/07/2026, `algo.py` version 3.0.
Document préparatoire à la réécriture du solveur en CP-SAT (OR-Tools).

Objectif : lister **toutes** les règles réellement appliquées par le code, repérer
celles qui sont mortes ou redondantes, et décider lesquelles reprendre dans le
nouveau modèle. Chaque règle porte un identifiant (`D` = dure, `S` = souple,
`N` = nominative) pour pouvoir en discuter sans ambiguïté.

---

## 1. Cadre temporel

| | Valeur | Source |
|---|---|---|
| Pas de temps | 15 min | `TIME_STEP` |
| Journée | 09:00 → 20:00 | `generate_timeline()` |
| Nombre de créneaux | 44 | — |
| Nombre de caisses | 14 | `ORDRE_CAISSES` |

Un employé peut avoir **deux plages** dans la journée (matin `ms/me`, après-midi
`aes/aee`). L'intervalle entre les deux est une **coupure** — l'employé quitte le
site. C'est différent d'une pause, où il reste sur place.

Tâches possibles dans une cellule : `C1`..`C14`, `CLS`, `PAUSE`, `POLY`, vide.

---

## 2. Contraintes dures

Le solveur ne doit **jamais** les violer, même au prix d'une caisse fermée.

| Id | Règle | Source |
|---|---|---|
| **D1** | Un employé ne peut tenir qu'une tâche à la fois | structure de la matrice |
| **D2** | Une caisse est tenue par au plus une personne à un créneau donné | implicite |
| **D3** | On n'affecte personne hors de ses heures de présence | `presence[nom][i]` |
| **D4** | `restriction_handicap = "Caisse Impaire Uniq."` → caisses impaires seulement | `caisse_autorisee()` [algo.py:94](algo.py:94) |
| **D5** | `restriction_handicap = "Caisse Paire Uniq."` → caisses paires seulement | idem |
| **D6** | `restriction_cls = 1` → jamais de mission CLS, jamais closer | [algo.py:696](algo.py:696), [algo.py:722](algo.py:722) |
| **D7** | Pas de glissement d'une caisse vers sa mitoyenne | `sont_adjacentes()` [algo.py:107](algo.py:107) |
| **D8** | Une seule mission CLS par personne et par jour | `compteur_cls >= 1` |
| **D9** | Le closer du jour ≠ le closer de la veille | `historique_fermeture` |
| **D10** | Un intérimaire ne peut pas être closer | [algo.py:722](algo.py:722) |
| **D11** | Le closer est exclu du CLS de journée | [algo.py:769](algo.py:769) |

**D4/D5 — le bug historique.** Cette restriction était une simple pénalité de
900000, contournable par un bonus. 30 créneaux de violation avaient été
reproduits. Elle doit rester un **filtre**, jamais un coût.

**Paires mitoyennes (D7)** : `[1,2] [13,14] [5,6] [3,4] [7,8] [9,10] [11,12]`.
Passer de C1 à C2 est interdit — les deux caisses sont côte à côte, le client ne
comprend pas. Une pause **ne rompt pas** la continuité : `C13 → PAUSE → C14` doit
être détecté comme un glissement.

---

## 3. Couverture des caisses

Ordre de priorité d'ouverture : **1, 2, 13, 14, 5, 6, 3, 4, 7, 8, 9, 10, 11, 12**

| Id | Règle | Valeur |
|---|---|---|
| **D12** | C1 et C2 ouvertes **sans interruption** | tolérance 0 |
| **S1** | C13 et C14 : trou toléré | ≤ 6 créneaux (1h30) |
| **S2** | Autres caisses : ouvertes si quelqu'un est libre, sinon fermées | — |
| **S3** | Récompense de couverture graduée selon la priorité | C1/C2 = 800, C13/C14 = 400, autres = 40 + 12×rang |

**S3 est un correctif.** Avec une récompense uniforme, l'optimiseur ouvrait C10,
C11 et C12 pendant que C5 et C6 restaient fermées. La graduation est ce qui fait
respecter l'ordre.

---

## 4. Stabilité des affectations

C'est le cœur du problème d'origine : trop de changements de caisse.

| Id | Règle | Valeur |
|---|---|---|
| **S4** | Coût d'une relève sur une caisse — **progressif** : la k-ième coûte k fois | 60 × k |
| **S5** | Surcoût si le sortant était encore disponible (relève non justifiée) | 150 |
| **S6** | Poste de moins de 1h30 | 300 |
| **S7** | Poste de 15 min (bloc isolé) | 800 |
| **S8** | Même caisse matin **et** après-midi, hors C1/C2/C13/C14 | 300 |
| **S9** | Durée minimale d'un poste avant qu'un déplacement soit autorisé | 6 créneaux (1h30) |
| **S10** | Durée minimale d'un bloc | 2 créneaux (30 min) |

**S4 est un correctif.** Avec un coût de relève fixe, l'optimiseur supprimait
toutes les relèves en figeant dix personnes sur la même caisse toute la journée —
exactement ce qu'il ne fallait pas.

**S8** encode « en général les gens préfèrent changer de caisse » après la
coupure. L'exception C1/C2/C13/C14 vient de l'usage : sur ces caisses-là, revenir
au même poste l'après-midi est accepté.

---

## 5. Missions

### 5.1 Mission CLS

Semaine, journée :
- Blocs de **2h maximum** (8 créneaux) — plafond volontaire, confirmé
- Ne peut pas **démarrer** après 17:00
- Une seule mission par personne et par jour (D8)

Dimanche : deux créneaux fixes, remplacent le CLS de semaine.
- 09:30 → 11:15 (index 2, 7 créneaux)
- 11:15 → 13:15 (index 9, 8 créneaux)

Le dimanche, **pas de closer** et **pas de pause l'après-midi**.

### 5.2 Le closer

- Démarre à **17:00**
- Exige un bloc continu de **≥ 2h**
- Interdit : `restriction_cls`, intérimaires, closer de la veille
- Choisi parmi les candidats valides : **celui qui est le moins présent avant
  17h**, puis le plus long bloc, puis le nom

**Ce critère est un correctif.** Avant, on retenait le plus disponible — ce qui
consommait le meilleur titulaire du CLS de journée, réduit ensuite à des
fragments de 45 ou 75 min. Cas Alexandra du 04/08.

Si aucun candidat ne passe les filtres, repli qui ignore tout sauf
`restriction_cls`.

### 5.3 Mission pause

Durée calculée, pas choisie :

```
créneaux_matin = ceil((somme des heures de présence du matin × 3 + 30) / 15)
```

- Matin : démarre créneau 6 (10:30), s'arrête avant le créneau 20 (14:00)
- Après-midi : démarre `max(24, 40 − durée)`, s'arrête avant le créneau 44
- **S11** — pas de relais si le reliquat fait moins de 45 min (`RELAI_PAUSE_MIN`)

Priorité (score décroissant) :

| Critère | Poids |
|---|---|
| N'est pas intérimaire | +1000 |
| Est le closer | −5000 |
| Longueur du bloc disponible | ×10 |
| Nombre de missions déjà faites (`compteur_missions`) | ×(−5) |

⚠️ Cette mission est **structurellement sous-couverte** — problème antérieur à la
refonte, mis de côté à la demande. À traiter dans le modèle CP-SAT.

---

## 6. Règles nominatives en dur

Huit règles portent des noms de personnes, écrites dans le code. Confrontées à la
base de production :

| Id | Règle | Ligne | Cible réelle | Décision 31/07 |
|---|---|---|---|---|
| **N1** | `BLACKLIST_CLS_PERMANENT = ["jean marc", "jessica", "emmanuel"]` | [algo.py:13](algo.py:13) | voir ci-dessous | ❌ supprimée (redondante) |
| **N2** | Pénalité C1/C2 : `léandre` 1000 | [algo.py:39](algo.py:39) | *personne* | ❌ supprimée (morte) |
| **N3** | Pénalité C1/C2 : `dalya` 2000, `ethan` 3000, `yacine` 5000 | [algo.py:40](algo.py:40) | BECHICHI, COLONDON, AYACHE | ➡️ base, `caisses_evitees` |
| **N4** | Pénalité C13/C14 : `yacine` 3000, `ethan` 3000, ~~`nathalie` 500~~ | [algo.py:45](algo.py:45) | AYACHE, COLONDON | ➡️ base ; **Nathalie supprimée** |
| **N5** | Éviter `yacine` pour le CLS du dimanche | [algo.py:707](algo.py:707) | AYACHE Yacine | ➡️ base, `evite_cls` |
| **N6** | Éviter `yacine` pour le closer | [algo.py:740](algo.py:740) | AYACHE Yacine | ➡️ base, `evite_cls` |
| **N7** | Pénaliser `yacine` de 5000 sur le CLS de journée | [algo.py:776](algo.py:776) | AYACHE Yacine | ➡️ base, `evite_cls` |
| **N8** | `andré` exclu de la mission pause | [algo.py:805](algo.py:805), [algo.py:847](algo.py:847) | SOUSA MARTINS André | ➡️ base, `evite_pause` — **définitif** |
| **N9** | `alicia` bonus −50000 sur C1 | [algo.py:1008](algo.py:1008) | PIERQUIN Alicia | ❌ **supprimée** |

### Détail de N1

| Clé | Employé visé | `restriction_cls` en base | Verdict |
|---|---|---|---|
| `jean marc` | MAYENGO Jean Marc | **1** | déjà interdit par la base |
| `jessica` | LEFEBVRE Jessica | **1** | déjà interdit par la base |
| `emmanuel` | *aucun* | — | ne matche personne |

`emmanuel` ne matche pas CADEAU Emmanuelle : le filtre exige des **mots entiers**,
et `emmanuel ≠ emmanuelle`. Elle a de toute façon `restriction_cls = 1`.

**→ `BLACKLIST_CLS_PERMANENT` peut être supprimée en entier.** Elle ne fait rien
que la base ne fasse déjà.

### Détail de N9

PIERQUIN Alicia a `restriction_handicap = "Caisse Impaire Uniq."`. C1 lui est
donc déjà autorisée et C2 déjà interdite. Le bonus de −50000 sert seulement à la
préférer sur C1 plutôt qu'une autre impaire. **À confirmer : toujours voulu ?**

### Détail de N2

Aucun employé nommé « Léandre » dans la base. Règle morte depuis un départ.

---

## 7. Autres pénalités souples (phase B de l'étape 3)

Ces valeurs pilotent le choix du titulaire quand une caisse se libère.
Elles sont d'un ordre de grandeur très supérieur aux `POIDS` de l'optimiseur —
il s'agit d'un tri, pas d'une somme.

| Situation | Valeur | Effet |
|---|---|---|
| Reprend sa caisse habituelle après pause ou CLS | −300000 | fortement encouragé |
| Reprend sa caisse habituelle **après coupure**, caisse non critique | +250000 | découragé (règle S8) |
| Sa caisse habituelle est libre ailleurs | +150000 | ne pas le détourner |
| **C1 ou C2** et intérimaire | −100000 | intérimaires préférés — **décision 31/07 : C1/C2 uniquement** |
| Bloc plus court que 1h30 | +200000 | découragé |

**Décision du 31/07** : le bonus intérimaire portait sur les quatre caisses
critiques. Il est ramené à **C1 et C2 seulement** (`CAISSES_ININTERROMPUES` au
lieu de `CAISSES_CRITIQUES`). Sur C13 et C14, un intérimaire n'est plus favorisé.

---

## 8. Champs de la base déclarés mais jamais lus par l'algorithme

La table `employes` a **14 colonnes**. `run_algo` n'en utilise que **4**.

| Colonne | Utilisée ? | Décision 31/07 |
|---|---|---|
| `nom` | ✅ | conservée |
| `statut` | ✅ | conservée — uniquement le test `== "Interimaire"` |
| `restriction_cls` | ✅ | **conservée, fait autorité pour le CLS** |
| `restriction_handicap` | ✅ | conservée |
| `forme_cls` | ❌ | ❌ **abandonnée** — contredisait `restriction_cls` |
| `articles_minute` | ❌ | ❌ **colonne supprimée** |
| `note_manager` | ❌ | ❌ **colonne supprimée** |
| `forme_caisse` | ❌ | vaut 1 partout — à supprimer aussi ? |
| `heures_contrat` | ❌ | laissée (chantier WFM) |
| `type_contrat` | ❌ | doublon de `statut` |
| `repos_fixes` | ❌ | laissée (chantier WFM) |
| `sur_caisses` | ❌ | hors migration, origine inconnue |
| `token` | ❌ | hors migration, origine inconnue |

**Colonnes à créer** pour accueillir les règles nominatives :

| Colonne | Type | Remplace | Contenu |
|---|---|---|---|
| `caisses_evitees` | TEXT | N3, N4 | `"1:5000,2:5000,13:3000,14:3000"` — numéro:pénalité |
| `evite_cls` | BOOLEAN | N5, N6, N7 | préférence, **distincte** de l'interdiction `restriction_cls` |
| `evite_pause` | BOOLEAN | N8 | exclut de la mission pause |

Valeurs à saisir après migration :

| Employé | `caisses_evitees` | `evite_cls` | `evite_pause` |
|---|---|---|---|
| AYACHE Yacine | `1:5000,2:5000,13:3000,14:3000` | 1 | 0 |
| COLONDON Ethan | `1:3000,2:3000,13:3000,14:3000` | 0 | 0 |
| BECHICHI Dalya | `1:2000,2:2000` | 0 | 0 |
| SOUSA MARTINS André | — | 0 | **1** |
| tous les autres | — | 0 | 0 |

Après cette migration, **`algo.py` ne contient plus aucun nom de personne**.

---

## 9. Défauts constatés à corriger dans le nouveau modèle

### 9.1 `run_algo` écrit en base pendant qu'il calcule

`inc_mission_score()` [algo.py:832](algo.py:832) et [algo.py:873](algo.py:873),
`save_historique_fermeture()` [algo.py:758](algo.py:758).

Le score de mission est **lu** dans le tri des pauses et **incrémenté** dans la
foulée. Conséquence, mesurée sur le 14/08/2026, 23 employés, base non
réinitialisée entre les runs :

```
run 1 vs run 2 : 209 cellules différentes
run 1 vs run 3 : 251 cellules différentes
```

**Le déterminisme n'existe que si la base est remise à zéro entre deux
générations.** Tous les tests de reproductibilité passés copiaient `pristine.db`
avant chaque run, ce qui masquait le problème.

→ Dans le modèle CP-SAT : lire les compteurs **une seule fois** au début, ne rien
écrire avant que le planning soit validé par l'utilisateur.

### 9.2 `compteur_missions` n'est jamais remis à zéro

Cumul depuis la mise en service. Écart actuel : 15 (LEFEBVRE Jessica) contre 1
(AYACHE Yacine). Un nouvel arrivant part à 0 et sera choisi en priorité pendant
des semaines. Il faudrait une fenêtre glissante — les 30 derniers jours, par
exemple — plutôt qu'un cumul à vie.

Ligne orpheline : `Alicia` coexiste avec `PIERQUIN Alicia` dans
`compteur_missions`, séquelle d'un renommage.

### 9.3 Rendement du solveur actuel

Sur 60000 essais : 83 % ne produisent aucune proposition valide, 1,2 % sont
acceptés. Gain réel de la phase d'optimisation sur 4 journées réelles :
**5 relèves évitées sur 99**. C'est le glouton qui produit la qualité.

---

## 10. Décisions du 31/07/2026

Arbitrées par l'utilisateur, à appliquer dans le modèle CP-SAT.

| # | Question | Décision |
|---|---|---|
| 1 | `forme_cls` vs `restriction_cls` | **`restriction_cls`** fait autorité ; `forme_cls` abandonnée |
| 2 | Bonus intérimaire sur caisses critiques | conservé **pour C1 et C2 seulement** |
| 3 | Bonus d'Alicia sur C1 (N9) | **supprimé** |
| 4 | André exclu de la mission pause (N8) | **définitif** — passe en base |
| 5 | Pénalités de Nathalie | **toutes supprimées** |
| 6 | `articles_minute`, `note_manager` | **colonnes supprimées** |
| 7 | Mission pause sous-couverte | **laissée en l'état** |
| 8 | `compteur_missions` | **fenêtre glissante 30 jours** |

Supprimées en plus, sans discussion nécessaire :
- **N1** `BLACKLIST_CLS_PERMANENT` — entièrement redondante avec `restriction_cls`
- **N2** `léandre` — ne correspond à personne
- ligne orpheline `Alicia` dans `compteur_missions`

### Conséquence de la décision 8 : il faut une nouvelle table

Le compteur actuel est un **cumul sans dates** — impossible d'en extraire une
fenêtre glissante. Et le planning généré **n'est stocké nulle part** :
`sauvegarde_historique` ne conserve que les horaires saisis en entrée, jamais
l'affectation produite. Il n'existe donc **aucun historique à rétro-remplir**.

```sql
CREATE TABLE historique_missions (
    date_str TEXT,
    nom      TEXT,
    mission  TEXT      -- 'PAUSE' | 'CLS' | 'CLOSER'
);
```

La fenêtre démarre donc à zéro pour tout le monde. Pendant le premier mois, le
critère d'équité sera peu discriminant et le départage se fera sur les autres
critères. C'est acceptable, mais il faut le savoir : `compteur_missions` devient
inutilisable et sera abandonnée.

### Conséquence de la décision 6 : trois fichiers à modifier

`articles_minute` et `note_manager` sont référencées dans :
- [database.py](database.py) — `CREATE TABLE`, `COLONNES_AJOUTEES`, `add_employe`, `update_employe`
- [app.py](app.py) — routes d'ajout et de modification d'un salarié
- [static/js/main.js](static/js/main.js) — lignes 146, 166-167, 184, 220-221
- [templates/index.html](templates/index.html) — champs `emp-apm`, `emp-note` des deux modales

SQLite 3.45 est disponible, `ALTER TABLE ... DROP COLUMN` fonctionne.
**La suppression des colonnes doit se faire après une sauvegarde de la base de
production.**

---

---

## 11. Le plafond a été mesuré — 2026-08-01

Question posée depuis le début du chantier : les 99 relèves du glouton sont-elles
proches de l'optimum ? Réponse, par résolution exacte sur instances réduites.

| fenêtre | créneaux | glouton | optimum **prouvé** | temps |
|---|---|---|---|---|
| 09:00–09:45 | 4 | 0 relève | **0** | 0,6 s |
| 09:00–10:15 | 6 | 0 | **0** | 1,6 s |
| 09:00–10:45 | 8 | 0 | **1** | 12 s |
| 09:00–11:45 | 12 | 1 | **1** | 29 s |

**Le glouton est à l'optimum**, prouvé. Sur la fenêtre de 8 créneaux l'optimum a
même une relève *de plus* : il l'échange contre de la couverture, ce qui est le
bon arbitrage.

Sur la journée entière, 900 secondes de CP-SAT :

```
glouton :  22 relèves, couverture 427
cpsat   :  22 relèves, couverture 424   (FEASIBLE, écart 3,37 %)
```

L'écart de 3,37 % n'est pas de la marge : c'est une borne molle. Trois méthodes
indépendantes — glouton, recuit simulé, CP-SAT — convergent vers le même plateau.

**Décision : chantier CP-SAT arrêté.** [solveur_cpsat.py](solveur_cpsat.py) est
conservé comme instrument de mesure du plafond, pas comme moteur de production.

### Ce qui a été appliqué à la place

| Correction | Effet mesuré |
|---|---|
| Missions écrites une seule fois, en fin de génération, remplacées par date | 4 générations du même jour → toujours 7 missions, plus aucun cumul |
| `compteur_missions` remplacé par `historique_missions` daté, fenêtre 30 jours | fin du cumul à vie (Jessica 15 contre Yacine 1) |
| `BLACKLIST_CLS_PERMANENT` supprimée | redondante avec `restriction_cls` |
| Les 8 règles nominatives remontées en base | **plus aucun nom de personne dans `algo.py`** |
| Bonus intérimaire ramené à C1/C2 | décision 2 |
| `ESSAIS_OPTIM` laissé à 60000 | 20000 coûte 11 créneaux de couverture et 4 postes courts |

Non-régression sur 4 journées réelles : relèves 102 → 96, postes < 1h30 20 → 13,
couverture 830 → 833, **0 anomalie**.

Version passée à **3.1**.

### Reste à faire au déploiement

- Migrer la base de production : les colonnes `caisses_evitees`, `evite_cls` et
  `evite_pause` se créent seules au démarrage, mais **les valeurs sont à saisir**
  (tableau du § 8). Sans elles, les préférences de Yacine, Ethan, Dalya et André
  sont perdues.
- Supprimer les colonnes `articles_minute`, `note_manager`, `forme_cls`
  (décision 6) — touche 4 fichiers, **après sauvegarde de la production**.
- Exposer les trois nouvelles colonnes dans l'onglet Équipe.

---

*Établi par lecture intégrale de `algo.py`, `database.py` et de la base de
production, avec vérification de chaque nom en dur contre la table `employes`.*
