# PIE COA 10

## Introduction
Ce projet vise à analyser l’impact des événements de maintenance sur la consommation de carburant et à proposer un plan optimisé selon des contraintes économiques.  
Il est conçu pour être **reproductible**, **transparent**, et **utile en contexte opérationnel**.

---

## Objectifs
- Quantifier l’effet réel des maintenances sur la performance (ex. fuel flow).
- Décider d’actions concrètes selon l’économie associée et les contraintes opérationnelles.
- Simuler différents contextes économiques (prix du carburant, budget).
- Produire des livrables clairs et systématiques à chaque run.

---

## Structure du dépôt

- **`main.py`** → Point d’entrée du pipeline, orchestre toutes les étapes.
- **`config/settings.json`** → Paramètres économiques, contraintes, tolérances, logging.
- **`outputs/`** → Livrables générés à chaque run (CSV + PNG).
- **`notebooks/`** → Prototypage et tests (ex. `test_main.ipynb`).
- **`classes/`** → Modules du pipeline :
  - `io/` → chargement et schémas (`data_loader.py`, `schemas.py`).
  - `processing/` → nettoyage (`cleaning.py`).
  - `domain/` → logique métier (`maintenance.py`, `apm_models.py`).
  - `analysis/` → calculs et reporting (`impact_analysis.py`, `reporting.py`).
  - `optimization/` → sélection des actions (`scheduler.py`).
  - `utils/` → configuration des logs (`logging_conf.py`).

---

## Outputs détaillés

### `impact_summary.csv`
- **event** → type d’événement (ex. Engine wash).
- **timestamp_event** → date/heure de l’événement.
- **delta_fuel_flow** → variation moyenne du fuel flow après vs avant.
- **delta_fuel** → conversion en unités de carburant.
- **Comportement** → toujours recréé, même vide (entête uniquement).

### `fuel_flow_timeline.png`
- Courbe du fuel flow dans le temps.
- Lignes verticales pour les événements.
- Message “No data available” si données absentes.
- Toujours recréé.

### `maintenance_plan.csv`
- **event** → intervention retenue.
- **expected_savings** → économies estimées.
- **cost** → coût de l’intervention.
- **downtime_hours** → durée d’immobilisation.
- **ROI** → retour sur investissement.
- Toujours recréé, même vide.

---

## Configuration (`settings.json`)

### Impact analysis
- `merge_tolerance_days` → tolérance d’alignement mesures/événements.
- `before_after_window_days` → taille de la fenêtre avant/après pour calculer les moyennes.

### Economics
- `fuel_price_per_unit` → prix du carburant (unité cohérente avec les données).
- `constraints.budget` → budget total disponible.
- `constraints.max_downtime_hours` → downtime maximal autorisé.

---

# Structure détaillée du code

## Modules et classes

### `classes/io/data_loader.py`
- **Utilité :** Charger les données brutes (mesures TXT et événements).
- **Fonctions principales :**
  - Lecture du fichier TXT de performance (fuel flow, etc.), avec détection automatique du séparateur et gestion des entêtes (`skiprows`).
  - Lecture des événements (Excel/CSV), sélection de la première feuille disponible.
  - Retourne un DataFrame et le nom de la feuille (utilisé comme `tail_number`).

### `classes/io/schemas.py`
- **Utilité :** Standardiser et valider les colonnes.
- **Fonctions principales :**
  - Harmonisation des noms de colonnes (casing, underscores).
  - Application des mappings définis dans `settings.json`.
  - Validation stricte : présence des colonnes obligatoires et types corrects.

### `classes/processing/cleaning.py`
- **Utilité :** Nettoyer et fiabiliser les données.
- **Fonctions principales :**
  - Construction du champ `timestamp` à partir de `recorded_date` et `time`.
  - Correction des anomalies temporelles (`NaT`).
  - Suppression des doublons.
  - Nettoyage des colonnes numériques et ajout de flags de qualité.

### `classes/domain/maintenance.py`
- **Utilité :** Définir le catalogue des interventions de maintenance.
- **Fonctions principales :**
  - Création du catalogue depuis `settings.json` (coûts, downtime, effets attendus).
  - Structure exploitable par l’optimiseur.

### `classes/domain/apm_models.py`
- **Utilité :** Point d’extension pour modèles métier (APM).
- **Fonctions principales :**
  - Prévu pour accueillir des calculs additionnels ou règles spécifiques.

### `classes/analysis/impact_analysis.py`
- **Utilité :** Calculer l’impact des événements sur les mesures.
- **Fonctions principales :**
  - `join_with_events` : associe événements et mesures via `merge_asof` avec tolérance.
  - `before_after` : calcule les deltas de métriques (ex. fuel flow) avant/après chaque événement.

### `classes/analysis/reporting.py`
- **Utilité :** Produire les exports et visualisations.
- **Fonctions principales :**
  - `summary_tables` : exporte `impact_summary.csv` (toujours recréé).
  - `plot_metric` : génère `fuel_flow_timeline.png` avec markers d’événements.
  - `export_csv` : exporte `maintenance_plan.csv` (toujours recréé).

### `classes/optimization/scheduler.py`
- **Utilité :** Optimiser le plan de maintenance.
- **Fonctions principales :**
  - Prend en entrée le catalogue, le prix du carburant et les contraintes.
  - Calcule ROI des interventions.
  - Sélectionne les actions rentables sous contraintes (budget, downtime).

### `classes/utils/logging_conf.py`
- **Utilité :** Configurer le logger.
- **Fonctions principales :**
  - Définir le niveau de log (`INFO`, `DEBUG`, etc.).
  - Uniformiser les messages pour tout le pipeline.

---

## Chronologie de `main.py`

1. **Initialisation**
   - Lecture de `settings.json`.
   - Configuration du logger.

2. **Chargement des données**
   - Lecture du fichier TXT de mesures.
   - Lecture des événements (première feuille disponible).
   - Ajout de `tail_number` aux événements.

3. **Standardisation et nettoyage**
   - Harmonisation des colonnes via `schemas.py`.
   - Construction et correction des timestamps.
   - Suppression des doublons et nettoyage des colonnes numériques.
   - Tri des DataFrames (`df_txt` par `timestamp`, `events_df` par `date`).

4. **Alignement événements ↔ mesures**
   - `merge_asof` avec tolérance (`merge_tolerance_days`).
   - Production du DataFrame fusionné `merged`.

5. **Calcul des impacts**
   - Calcul des deltas avant/après (`before_after_window_days`).
   - Création de `deltas_ff` avec `delta_fuel_flow` et `delta_fuel`.

6. **Optimisation économique**
   - Construction du catalogue de maintenance.
   - Lecture du prix du carburant et des contraintes.
   - Vérification de la présence de `delta_fuel`.
   - Optimisation via `scheduler.optimize` → production du plan.

7. **Reporting**
   - **Résumé des impacts :**
     - Warning si `deltas_ff` est vide.
     - Export de `impact_summary.csv` (toujours recréé).
   - **Graphique fuel flow :**
     - Export de `fuel_flow_timeline.png` (toujours recréé).
   - **Plan de maintenance :**
     - Warning si `plan` est vide.
     - Export de `maintenance_plan.csv` (toujours recréé).

8. **Fin du pipeline**
   - Log “Pipeline completed.” pour confirmer la complétion.



