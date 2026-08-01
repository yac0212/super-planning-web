# Bancs d'essai du solveur

Scripts de mesure du chantier CP-SAT. Ils étaient dans un dossier temporaire lié à une
session ; déplacés ici le 2026-08-01 pour ne pas les perdre.

`pristine.db` est une copie de la base de production (données réelles). Elle est couverte
par `*.db` dans `.gitignore` — **ne pas la committer**, le dépôt est public.

## Lancer

```bash
cd bancs
JOURS=4 CPSAT_POSTE=60 CPSAT_SECONDES=30 python bench_cpsat.py
```

`CPSAT_MODULE=solveur_xxx` permet de comparer une autre formulation sans toucher à
`solveur_cpsat.py`.

## Ce que fait chaque script

| Script | Mesure |
|---|---|
| `bench_cpsat.py` | compare glouton / recuit / CP-SAT sur N journées réelles — **le juge de paix** |
| `plafond.py` | réduit l'instance jusqu'à obtenir `OPTIMAL` prouvé — **la mesure qui manque** |
| `reel.py` | glouton contre recuit seuls, sans CP-SAT |
| `determinisme_cpsat.py` | deux générations du même jour donnent-elles le même planning ? |
| `effets_bord.py` | montre que `run_algo` écrit en base pendant qu'il calcule |
| `convergence.py` | le budget du recuit sert-il à quelque chose ? |
| `rendement.py` | part du budget de recuit gaspillée en mouvements invalides |
| `suite.py` | 11 scénarios de synthèse + vérification des invariants |

## Où reprendre

Mesurer le plafond avec `plafond.py`. Tant qu'on ne sait pas si les 99 relèves du glouton
sont proches de l'optimum prouvé, on optimise à l'aveugle.

Les fichiers `solveur_sym.py`, `solveur_leger.py`, `solveur_decoupe.py`,
`solveur_candidats.py`, `solveur_poids.py` et `solveur_plafond.py` à la racine du projet
sont des variantes **jamais mesurées** — écrites par des agents interrompus avant de rendre
le moindre chiffre. À traiter comme des brouillons, pas comme des résultats.
