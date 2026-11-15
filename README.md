# NISAR Vision

Plateforme web pour explorer et comprendre les observations radar du satellite NISAR (NASA et ISRO). Elle réunit cinq modules : une carte multicouche, un traducteur radar, des récits cartographiques, un parcours d'apprentissage avec simulateurs, et un tableau de bord d'analyse.

**État honnête du projet.** Le code est complet et testé, mais il n'a été exécuté que sur des **données de démonstration simulées**. L'environnement de développement n'avait pas accès au serveur ASF, aucun vrai granule NISAR n'a donc été téléchargé ni lu. Tout ce qui est simulé est étiqueté « DÉMO » dans l'interface et dans la base. Les étapes à faire sur une machine connectée sont décrites plus bas et dans `docs/DONNEES_NISAR.md`.

## Démarrage rapide avec Docker

```bash
cp .env.example .env          # puis changer POSTGRES_PASSWORD
docker compose up --build
# interface : http://localhost:8080
# API et documentation interactive : http://localhost:8000/api/docs (masquée si NV_ENV=prod)
```

Au premier lancement l'API applique la migration et charge les données de référence (couches, règles, récits, parcours, glossaire). Le catalogue satellite reste vide tant qu'aucun granule n'est ingéré. Pour essayer l'interface avec la démonstration :

```bash
docker compose --profile tools run --rm cli seed-demo
```

Puis cocher « Afficher les données de démonstration simulées » dans l'interface.

> Les images Docker n'ont pas pu être construites pendant le développement (pas de démon Docker). `docker-compose.yml` a été validé syntaxiquement. Le premier `docker compose up --build` est donc le vrai test, voir `docs/RAPPORT_LIVRAISON.md`.

## Lancement sans Docker (développement)

Prérequis : Python 3.12 ou plus, Node 22.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
alembic upgrade head              # SQLite local par défaut
python -m app.cli seed-demo       # données simulées, étiquetées demo
uvicorn app.main:app --reload --port 8000

# autre terminal
cd frontend && npm ci && npm run dev    # http://localhost:5173, proxy /api vers :8000
```

Sans Redis, les analyses s'exécutent dans le processus de l'API (`NV_CELERY_ALWAYS_EAGER=true`, valeur par défaut hors Docker).

## Ingérer de vraies données NISAR

Les produits NISAR L-band sont publics et gratuits sur ASF DAAC. Il faut un jeton Earthdata (gratuit) : créer un compte sur urs.earthdata.nasa.gov, puis « Generate Token ». Le jeton se donne uniquement par la variable d'environnement `NV_EARTHDATA_TOKEN`, jamais dans le dépôt.

```bash
export NV_EARTHDATA_TOKEN=...
cd backend
# 1. voir ce qui existe et estimer la taille, sans rien télécharger
python -m app.cli ingest-remote --wkt "POLYGON((9.5 3.9,9.9 3.9,9.9 4.2,9.5 4.2,9.5 3.9))" \
        --start 2026-10-21 --end 2026-11-05 --maturity validated --dry-run
# 2. télécharger et ingérer (refuse au-delà de NV_INGEST_MAX_DOWNLOAD_GB, 20 Go par défaut, sauf --confirm)
python -m app.cli ingest-remote --wkt "..." --start 2026-10-21 --end 2026-11-05 --maturity validated
# ou, pour un fichier déjà téléchargé
python -m app.cli ingest-local /chemin/granule.h5 --maturity validated
```

**À faire d'abord, une seule fois :** vérifier que la structure HDF5 réelle correspond à ce que le lecteur attend.

```bash
python scripts/inspect_granule.py /chemin/granule.h5 --tree
```

Le script liste chaque chemin attendu (présent ou absent). S'il y a des écarts, tout se corrige dans un seul fichier : `backend/app/ingestion/hdf5_gcov.py`.

## Tests

```bash
make test-api     # backend : pytest + couverture
make test-web     # frontend : typecheck + vitest
make e2e          # navigateur (API et front lancés, base avec seed-demo)
```

Les tests backend tournent aussi sur PostgreSQL : `NV_TEST_DATABASE_URL=postgresql+psycopg://... pytest`. Avec un serveur sans PostGIS, ajouter `NV_USE_POSTGIS=false`.

## Déploiement

1. Serveur Linux avec Docker. Copier le dépôt, créer `.env` avec un vrai mot de passe et `NV_ENV=prod`.
2. Placer un proxy HTTPS (Caddy, Traefik ou nginx) devant le service `frontend` (port 8080) et fixer `NV_CORS_ORIGINS` à l'URL publique.
3. `docker compose up -d --build`. Le service `api` migre la base au démarrage.
4. Sauvegardes : volume `pgdata` (`pg_dump`) et volume `nvdata` (COG et manifestes). Les granules bruts se re-téléchargent, les COG se régénèrent.
5. Exploitation : `docker compose logs -f api worker` (journaux JSON avec `request_id`), `GET /api/v1/health` et `/api/v1/health/ready`, purge des exports expirés par `cli purge-exports` (à planifier une fois par jour).

Limite connue : le limiteur de débit est en mémoire de processus. Avec plusieurs workers gunicorn il s'applique par processus. Pour une exposition publique, ajouter une limite au niveau du proxy.

## Structure

```
backend/    FastAPI, SQLAlchemy 2, Alembic, traitement raster, ingestion, tâches Celery, tests
frontend/   React, TypeScript, Vite, Tailwind, MapLibre, Recharts, tests vitest et Playwright
docs/       DONNEES_NISAR.md, ARCHITECTURE.md, RAPPORT_LIVRAISON.md
scripts/    inspect_granule.py
```

Pour comprendre les choix et leurs limites : `docs/ARCHITECTURE.md`. Pour la liste de ce qui est fait, non fait et non vérifié : `docs/RAPPORT_LIVRAISON.md`.
