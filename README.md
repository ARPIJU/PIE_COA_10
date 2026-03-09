# PIE_COA_10

Projet d'analyse de performance avion (APM) orienté maintenance.

Ce document explique:

1. ce que fait le projet,
2. comment l'utiliser pas à pas,
3. comment lire les resultats,

## 1. Objectif metier

Le projet aide a repondre a la question suivante:

- Les actions de maintenance ont-elles un effet mesurable sur la performance carburant?

Le pipeline relie:

1. des donnees de performance (fichier TXT),
2. des evenements de maintenance (fichier Excel),
3. des regles de traitement (fichier de configuration JSON),

pour produire des fichiers de sortie exploitables (CSV et graphiques).

## 2. Ce que le pipeline fait aujourd'hui

Le pipeline principal est `main.py`.

Il execute automatiquement:

1. chargement des fichiers source,
2. harmonisation et nettoyage des donnees,
3. filtrage passe-bas du signal de performance,
4. export des donnees traitees par avion,
5. generation de graphiques brut vs filtre,
6. analyse de correlation,
7. export global de donnees nettoyees.


## 3. Structure du projet

### 3.1 Dossiers principaux

- `main.py`: point d'entrée du pipeline.
- `config/settings.json`: configuration centrale.
- `data/`: donnees d'entrée.
- `outputs/`: resultats generés.
- `classes/`: modules de traitement.
- `notebooks/`: notebooks d'exploration/test.

### 3.2 Modules Python par role

#### Chargement / schema

- `classes/io/data_loader.py`
  - charge le TXT de performance,
  - detecte automatiquement le separateur,
  - charge les evenements Excel.
- `classes/io/schemas.py`
  - standardise les noms de colonnes,
  - applique les mappings,
  - valide les colonnes critiques.

#### Nettoyage et traitement signal

- `classes/processing/cleaning.py`
  - construit/corrige les timestamps,
  - supprime les doublons,
  - nettoie les colonnes numériques,
  - ajoute des indicateurs de qualite.
- `classes/processing/low_pass_filtering.py`
  - applique un filtre passe-bas Butterworth,
  - trace la comparaison signal brut / signal filtre,
  - annote les evenements de maintenance.

#### Analyse

- `classes/analysis/correlation.py`
  - calcule les correlations de Pearson par avion.
- `classes/analysis/impact_analysis.py`
  - calcule des metriques avant/apres maintenance,
  - estime des impacts par type,
  - fournit des tableaux de synthese.
- `classes/analysis/global_drift.py`
  - calcule D(t), une derive globale post-maintenance.
- `classes/analysis/reporting.py`
  - exporte CSV et graphiques.

#### Modele metier et optimisation

- `classes/domain/maintenance.py`
  - catalogue des maintenances (cout, downtime, etc.).
- `classes/optimization/scheduler.py`
  - selection gloutonne d'actions selon ROI et contraintes.

## 4. Donnees d'entree requises

### 4.1 Donnees performance (TXT)

Par defaut:

- `data/Boeing_Perf_Data.txt`

Colonnes typiques attendues (avant mapping):

- `Date Recorded ()`
- `Time`
- `Airplane ID ()`
- `FF Total`

Le mapping vers les noms internes se fait dans `config/settings.json`.

### 4.2 Evenements maintenance (Excel)

Par defaut:

- `data/CMA-FORM-FOE-10 (Perf Factor - Fuel Flow factor Record).xlsx`

Feuilles cibles configurees:

- `FHMRB`, `FHMRF`, `FHMRO`, `FHMRI`

Note:

- `main.py` ignore explicitement `FHMRI` dans le traitement actuel.

## 5. Configuration (`config/settings.json`)

Le fichier de configuration contient tout ce qu'un utilisateur doit adapter.

Sections importantes:

1. `paths`: chemins des donnees et sorties.
2. `excel_sheets_priority`: ordre des feuilles avion.
3. `txt_read`: lecture TXT (skip rows, encodage, separateurs).
4. `columns_mapping`: correspondance des noms de colonnes.
5. `schema`: colonnes obligatoires/optionnelles.
6. `cleaning`: regles de nettoyage.
7. `lowpass_filter`: parametres de filtrage.
8. `selected_tail_numbers`: avions a traiter.
9. `impact`: parametres d'analyse d'impact (modules avances).
10. `economics`: parametres economiques et catalogue maintenance.

## 6. Installation pas a pas (Windows)

Depuis le dossier du projet.

### 6.1 Creer un environnement Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 6.2 Installer les dependances

Installez manuellement:

```powershell
pip install pandas numpy matplotlib seaborn scipy openpyxl
```

## 7. Lancer le pipeline

```powershell
python main.py
```

Si tout est correct:

- vous verrez les logs de progression,
- les fichiers de sortie apparaitront dans `outputs/`,
- le log final indiquera le succes du pipeline.

## 8. Sorties generees et interpretation

### 8.1 Sorties produites par le pipeline principal

- `outputs/data_<TAIL>.csv`
  - donnees traitees par avion,
  - contient la colonne filtree `%ff_dev_total_(%)_filtered` si calculable.
- `outputs/lowpass_filter_<TAIL>.png`
  - comparaison signal brut (bruite) et signal filtre (tendance),
  - positions des evenements de maintenance.
- `outputs/data_processed.csv`
  - jeu de donnees global nettoye.

### 8.2 Comment lire un graphe `lowpass_filter_<TAIL>.png`

- Courbe brute: variation mesurée, souvent bruitée.
- Courbe filtrée: tendance de fond.
- Lignes verticales: dates d'évènements de maintenance.

Lecture métier simple:

- une baisse de la tendance apreè maintenance peut indiquer un effet favorable,
- une tendance stable ou en hausse suggère un effet faible, court ou absent.

### 8.3 Fichiers de sortie avances (selon scripts executes)

Vous pouvez aussi trouver:

- `outputs/impact_interval_non_maintenance.csv`
- `outputs/maintenance_type_rates.csv`
- `outputs/maintenance_impacts_modeled.csv`
- `outputs/impact_summary.csv`
- `outputs/maintenance_plan.csv`

Ces fichiers sont liés aux modules d'impact/optimisation et a des runs complémentaires.

## 9. Mode d'emploi client (operatoire)

Procédure recommandée à chaque nouvelle livraison de données:

1. deéoser les nouveaux fichiers dans `data/`,
2. vérifier/adapter `config/settings.json`,
3. lancer `python main.py`,
4. ouvrir les graphiques dans `outputs/`,
5. partager les CSV de sortie pour validation metier.

## 10. Parametres à ajuster en priorité

### 10.1 Choix des avions

Modifier:

- `selected_tail_numbers`

### 10.2 Niveau de lissage du filtre

Modifier dans `lowpass_filter`:

- `cutoff_period_weeks` (plus grand = plus lisse),
- `order` (ordre du filtre).

### 10.3 Mapping des colonnes source

Modifier:

- `columns_mapping.txt`
- `columns_mapping.excel_events`

Utiliser cette section si les noms de colonnes fournis par le client changent.

## 11. Fonctions avancées disponibles

Le projet inclut des briques deja codees pour des usages plus pousses:

1. `classes/analysis/impact_analysis.py`
   - calcul d'impacts avant/apres,
   - estimation de taux par type de maintenance.
2. `classes/optimization/scheduler.py`
   - proposition d'actions selon ROI/budget/downtime.
3. `classes/analysis/global_drift.py`
   - derive globale D(t) multi-avions.

Ces briques peuvent etre integrees dans un flux client finalise en phase suivante.

## 12. Tests et verification

Scripts de test disponibles:

- `classes/analysis/tests/test_global_drift.py`

### Pourquoi `test_global_drift.py` est important

Ce script est un test important car il vérifie que la logique de dérive globale `D(t)` reste cohérente et exploitable.

Il valide notamment:

1. que le calcul de `D(t)` s'exécute sans erreur sur les sorties filtrées,
2. que la condition mathematique de reference `D(0) = 0` est respectée,
3. que la structure des résultats est saine (`t_days` trie, `n_samples > 0`),
4. que les graphes de dérive peuvent être générés pour revue métier.

Exemple:

```powershell
python -m classes.analysis.tests.test_global_drift
```

## 13. Dépannage rapide

### Erreur "fichier introuvable"

Vérifier dans `config/settings.json`:

- `paths.data_dir`
- `paths.txt_file`
- `paths.excel_file`

### Erreur "colonne manquante"

Veéifier:

- les noms de colonnes dans les fichiers source,
- le mapping dans `columns_mapping`.

### Pas de courbe filtrée

Vérifier:

- que `%ff_dev_total_(%)` existe dans vos donnees,
- que la colonne contient bien des valeurs numeriques exploitables.

### Avion ignore dans les sorties

Vérifier:

- sa présence dans `selected_tail_numbers`,
- sa présence reelle dans la colonne `tail_number` du TXT.

## 14. Limites actuelles (transparence)

1. Le pipeline principal ne chaine pas encore automatiquement toute la partie impact + optimisation.
2. Le projet ne fournit pas encore de fichier de dependances verrouille (`requirements.txt` / lockfile).
3. Certains scripts sont exploratoires et doivent etre valides avant usage production.
4. La qualité des résultats depend de la qualité des timestamps et des mappings de colonnes.

## 15. Glossaire simple

- `tail_number`: identifiant avion (ex: FHMRB).
- `timestamp`: date + heure de la mesure.
- `filtre passe-bas`: méthode qui lisse le bruit pour mieux voir la tendance.
- `derive`: évolution progressive d'un indicateur dans le temps.
- `ROI`: retour sur investissement (gain estime - coût).

