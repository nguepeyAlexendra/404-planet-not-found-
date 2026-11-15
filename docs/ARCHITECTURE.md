# Architecture

```
Navigateur (React, MapLibre, Recharts)
        │  /api/v1/*  (proxy nginx ou proxy Vite)
        ▼
FastAPI ── SQLAlchemy ──► PostgreSQL (PostGIS) ou SQLite en développement
   │  │
   │  └── tuiles PNG à la volée (rio-tiler) depuis des COG sur disque
   │
   └── Celery ──► Redis (file) ; le worker lit la même base et les mêmes COG
```

## Pipeline d'ingestion (`backend/app/ingestion/`)

Dix étapes, idempotentes par couple `source_id` + somme SHA-256 : découverte (asf_search), contrôle du budget de téléchargement, téléchargement, ouverture HDF5, validation, conversion en COG par bande, calcul d'étendue, écriture du manifeste JSON, enregistrement en base, journal `ingestion_run`. Un produit invalide va en quarantaine et ses fichiers partiels sont nettoyés. Relancer la même ingestion ne crée pas de doublon.

## Modèle de données (22 tables)

Catalogue : `dataset`, `raster_asset`, `ingestion_run`, `layer`, `aoi`, `classification_ruleset`. Contenu : `event`, `story`, `scene`, `learning_level`, `lesson`, `quiz`, `question`, `answer_option`, `attempt`, `user_progress`, `badge`, `user_badge`, `certificate`, `glossary_term`. Travaux : `job`, `export`. Les contraintes (maturité, statut, unicité des récompenses) sont dans la base, pas seulement dans le code.

## Règles de calcul

- Les moyennes se font sur les valeurs **linéaires**, puis sont converties en dB.
- Un pixel sans donnée n'est jamais affiché comme 0 : il est transparent sur la carte et « non disponible » dans les panneaux.
- Une bande absente rend l'analyse impossible et le dit.
- Matrice de transition et détection de changement exigent des grilles identiques (même CRS, résolution, étendue). Sinon l'API répond par une erreur qui liste les raisons.
- Projection : régression linéaire avec intervalle de prédiction à 95 %. Les trois scénarios multiplient la pente observée (1, 0,5 et 1,5). C'est un outil d'exploration, pas une prévision.

## API (préfixe `/api/v1`)

Système : `health`, `health/ready`. Catalogue : `datasets`, `layers`, `layers/{key}/metadata`, `map/pixel`, `events`, `tiles/...` (amplitude, classes, changement). Traducteur : `translator/ruleset`, `classification`, `changes`. Analyse : `analytics/aoi`, `time-series`, `change-matrix`, `projection` (jobs asynchrones, réponse 202), `jobs/{id}`, `jobs/{id}/cancel`, `exports`, `exports/{id}/download`. Contenu : `stories`, `learning/*`, `glossary`, `certificate`. La documentation interactive complète est à `/api/docs` hors production.

Conventions : erreurs `{error:{code,message,details,request_id}}`, en-tête `Idempotency-Key` pour les jobs, `X-Client-Id` pour la session anonyme.

## Identité et confidentialité

Il n'y a pas de compte. Le navigateur génère un identifiant aléatoire (`X-Client-Id`) stocké localement. Les zones, jobs, exports et la progression d'apprentissage sont rattachés à cet identifiant et invisibles pour les autres (réponse 404). **Ce n'est pas de l'authentification** : quiconque connaît l'identifiant accède aux données de cette session. Cela convient à un MVP sans donnée personnelle. Un certificat n'affiche publiquement que le prénom et l'initiale du nom.

## Écarts par rapport à la pile de référence (à valider)

| Référence | Réalisé | Raison |
|---|---|---|
| TiTiler | rio-tiler intégré à l'API | Un service de moins à déployer pour le MVP. TiTiler reste possible (voir `tile_base_url`), mais le front construit pour l'instant ses URL de tuiles lui-même (`src/lib/tiles.ts`) : le passage à TiTiler demande ce petit changement. |
| Plotly ou Recharts | Recharts | Un des deux choix permis, plus léger. |
| Redis + Celery ou RQ | Celery + Redis | Testé pour de bon, voir le rapport. |
| MinIO / stockage objet | Volume disque | Rien dans le code n'écrit sur S3. À ajouter si les COG doivent être partagés entre machines. |
| PostGIS | Optionnel (`NV_USE_POSTGIS`) | Les colonnes de géométrie sont PostGIS quand l'extension est active. Le code n'appelle aucune fonction spatiale PostGIS pour l'instant. |

## Améliorations ajoutées hors cahier des charges (à confirmer)

Quarantaine des produits invalides, plafond de téléchargement, `Idempotency-Key`, limiteur de débit, journaux JSON avec identifiant de requête, schéma de migration versionné, commande `ingest-remote --dry-run`, script `inspect_granule.py`, mode lecture réduite du mouvement (`prefers-reduced-motion`).
