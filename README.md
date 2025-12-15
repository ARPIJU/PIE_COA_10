# PIE COA 10

---
# A FAIRE
- Trouver un moyen d'optimiser en temps glissant les opérations de maintenance + Se renseigner sur les vrais coups de maintenance. (2 Personnes)
- Moyenner sur tous les avions et proposer un choix de l'avion sur lequel travailler. (1 personne) Cette personne a pour unique but de faire le lien entre performances et évent de maintenance.
- Faire un README complet avec une explication du code. (1 personne)

---

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

---

# Contenu du dossier `data`

Le dossier `data` contient trois documents essentiels au fonctionnement et à la compréhension du pipeline.  
Voici leur rôle détaillé :

---

### 1. `Boeing_Perf_Data.txt`
- **Nature :** Fichier texte brut contenant les mesures de performance avion.
- **Contenu typique :**
  - Colonnes comme `Recorded Date`, `Time`, `Fuel Flow`, `EGT`, `N1`, `N2`, etc.
  - Chaque ligne correspond à un enregistrement de vol ou de test.
- **Utilité dans le pipeline :**
  - Sert de base pour calculer les métriques (ex. fuel flow).
  - Les colonnes sont standardisées et nettoyées (`timestamp` construit à partir de `Recorded Date` + `Time`).
  - Alimente l’analyse avant/après pour mesurer l’impact des événements de maintenance.

---

### 2. `FHMRB.xlsx`
- **Nature :** Fichier Excel contenant les événements de maintenance pour un avion identifié par le sheet `FHMRB`.
- **Contenu typique :**
  - Colonnes comme `Date`, `Event`, `Description`, parfois `Cost` ou `Downtime`.
  - Chaque ligne correspond à une intervention ou inspection.
- **Utilité dans le pipeline :**
  - Les événements sont alignés avec les mesures du TXT via `merge_asof`.
  - Le nom de la feuille (`FHMRB`) est utilisé comme `tail_number` pour identifier l’avion.
  - Permet de calculer les deltas de performance avant/après chaque événement.

---

### 3. `APM_User_Manual.pdf`
- **Nature :** Document PDF de référence utilisateur pour l’APM (Aircraft Performance Monitoring).
- **Contenu typique :**
  - Explications théoriques et pratiques sur les métriques de performance.
  - Définitions des colonnes et variables utilisées dans les fichiers TXT.
  - Procédures standard de collecte et d’interprétation des données.
  - Recommandations sur l’utilisation des outils APM et sur la maintenance.
- **Utilité dans le pipeline :**
  - Sert de guide pour comprendre la signification des données brutes.
  - Permet de contextualiser les résultats (ex. interprétation correcte d’un delta fuel flow).
  - Aide à configurer correctement les mappings et validations dans `schemas.py`.
  - Document de référence pour l’équipe afin d’assurer cohérence et conformité avec les standards APM.

---

## Résumé
- **`Boeing_Perf_Data.txt`** → Données brutes de performance (mesures techniques).  
- **`FHMRB.xlsx`** → Événements de maintenance (interventions, inspections).  
- **`APM_User_Manual.pdf`** → Manuel utilisateur APM, guide théorique et pratique pour interpréter les données et assurer cohérence.  

Ces trois documents sont complémentaires : le TXT fournit les mesures, l’Excel fournit les événements, et le PDF fournit le cadre théorique et méthodologique pour analyser et interpréter correctement les résultats.



