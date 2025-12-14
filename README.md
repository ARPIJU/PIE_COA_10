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

## Logique du pipeline

1. **Chargement des données**
   - Lecture du fichier TXT de mesures (fuel flow, etc.).
   - Lecture des événements de maintenance.

2. **Standardisation & nettoyage**
   - Harmonisation des colonnes via `schemas.py`.
   - Construction et correction des timestamps.
   - Suppression des doublons et nettoyage des colonnes numériques.

3. **Alignement événements ↔ mesures**
   - `merge_asof` avec tolérance (`merge_tolerance_days`).
   - Association des événements aux mesures les plus proches.

4. **Calcul des impacts**
   - Moyenne du fuel flow avant/après chaque événement (`before_after_window_days`).
   - Export des deltas dans `impact_summary.csv`.

5. **Optimisation économique**
   - Conversion des deltas en économies monétaires selon `fuel_price_per_unit`.
   - Sélection des interventions rentables sous contraintes (`budget`, `max_downtime_hours`).
   - Export du plan dans `maintenance_plan.csv`.

6. **Reporting**
   - Export systématique des trois fichiers (CSV + PNG).
   - Warnings dans les logs si aucun delta ou plan rentable.

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

