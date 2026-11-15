# Rapport de livraison, NISAR Vision 1.0

Date : 15 novembre 2026.

## 1. Fonctionnalités réalisées

**Carte interactive.** Couches HH et HV avec opacité et ordre réglables, chronologie limitée aux dates réellement présentes (lecture, vitesse, curseur), comparaison avant/après par curseur, panneau pixel (valeurs linéaires et en dB, interprétation prudente, courbe temporelle), recherche de lieu (coordonnées, ou nom via OpenStreetMap), zone d'intérêt en cercle ou rectangle, métadonnées de provenance et de maturité, fond OSM optionnel.

**Traducteur radar.** Trois modes : signal brut, lecture sémantique (cinq classes plus « indéterminé »), changements entre deux dates avec seuil réglable. Légendes, répartition par classe, règles consultables, avertissement « prototype non validé » partout où une interprétation apparaît.

**Récits (scrollytelling).** Carte fixe pilotée par le défilement, scènes avec provenance et limites, sources citées, animation des dates désactivée si l'utilisateur demande moins de mouvement. Deux récits : un exemple sans donnée (« Amazonie », texte seul, sans chiffre inventé) et un récit de démonstration sur données simulées.

**Apprentissage.** Cinq niveaux déblocables dans l'ordre, deux leçons et quatre questions par niveau, cinq simulateurs conceptuels (jour/nuit, rugosité, eau et pièges, polarimétrie, InSAR avec la relation phase-déplacement), score, XP et badges calculés côté serveur, glossaire de 64 termes, certificat PDF avec code vérifiable.

**Tableau de bord.** Série temporelle (HH, HV, classes), matrice de transition, projection exploratoire à trois scénarios avec intervalle à 95 %, exécution en tâche asynchrone avec progression et annulation, export CSV, GeoJSON, SVG et PDF.

**Transversal.** Interrupteur « données de démonstration » avec bandeau jaune permanent, états de chargement, d'erreur et de vide, navigation clavier, `aria-label` sur les cartes, graphiques et curseurs, bouton de saut au contenu.

## 2. Fonctionnalités non réalisées ou partielles

- **Aucune donnée NISAR réelle n'a été ingérée.** L'accès à ASF était bloqué (HTTP 403) dans l'environnement de développement.
- Dessin de zone en polygone libre et import GeoJSON dans l'interface : l'API les accepte, l'interface propose seulement cercle et rectangle.
- Export PNG côté serveur : non fait. Les exports sont CSV, GeoJSON, SVG, PDF.
- Table `event` et route `/events` existent, mais aucun événement n'est saisi et l'interface ne les affiche pas.
- Une seule mosaïque par date et par couche (pas d'assemblage de plusieurs granules voisins).
- Pas de rééchantillonnage : les comparaisons exigent des grilles identiques.
- Pas de mode enseignant, pas de comptes utilisateurs.
- Interface en français uniquement.
- Les produits autres que GCOV (GSLC, GUNW, GOFF, SME2) ne sont pas lus.

## 3. Tests exécutés et résultats

Tous lancés le 15 novembre 2026 dans l'environnement de développement.

| Test | Résultat |
|---|---|
| Backend, pytest sur SQLite | **104 réussis**, couverture 94 % (les plus basses : validation d'ingestion 78 %, ligne de commande 82 %, lecteur HDF5 82 %, client ASF 84 %, c'est-à-dire surtout les chemins d'erreur et le réseau) |
| Backend, pytest sur PostgreSQL 16 (sans PostGIS, `NV_USE_POSTGIS=false`) | **104 réussis** |
| Migration Alembic sur SQLite et sur PostgreSQL 16 | Réussie, 22 tables |
| Circuit réel Celery + Redis (worker séparé, API hors mode eager) | Une analyse de série temporelle passe de « queued » à « succeeded » avec résultat |
| Frontend, `tsc --noEmit` | Aucune erreur |
| Frontend, vitest | **26 réussis** (modèles des simulateurs, store, client API, composants) |
| Frontend, build de production | Réussi |
| Navigateur, Playwright (Chromium) | **5 réussis** : carte et démo, traducteur, récit, quiz serveur, analyse et export CSV |
| Contrôle visuel par captures | Carte, panneau pixel, changements, récit (activation des scènes au défilement), tableau de bord |

Bugs trouvés par ces tests et corrigés : mauvais type de géométrie sur PostgreSQL, tâche Celery non enregistrée dans le worker.

**Non exécuté :**
- Les images Docker n'ont pas été construites (pas de démon Docker). `docker compose config` valide la syntaxe uniquement.
- Le workflow GitHub Actions n'a jamais tourné.
- L'extension PostGIS n'a jamais été utilisée (non installée dans l'environnement).
- Aucun test d'accessibilité automatisé (axe) ni test sur mobile réel.
- Aucun test de charge.

## 4. Sources NISAR utilisées

Documentation de disponibilité ASF (https://nisar-docs.asf.alaska.edu/availability-overview/) et annonce Earthdata de la sortie des données L-band (https://www.earthdata.nasa.gov/news/nisar-l-band-data-released-expanding-record-surface-changes). **Aucun granule réel n'a été lu.** Tout ce qui s'affiche en démonstration est simulé par le programme. Détails dans `docs/DONNEES_NISAR.md`.

## 5. Architecture finale

Voir `docs/ARCHITECTURE.md`. En bref : React et MapLibre devant FastAPI, PostgreSQL, tuiles générées à la volée depuis des COG, tâches Celery sur Redis, pipeline d'ingestion en dix étapes avec quarantaine. Les écarts avec la pile de référence y sont listés.

## 6. Commandes de lancement

Voir `README.md` : `docker compose up --build` (Docker) ou `alembic upgrade head`, `python -m app.cli seed-demo`, `uvicorn app.main:app` et `npm run dev` (sans Docker).

## 7. Déploiement

Voir la section « Déploiement » du `README.md` : proxy HTTPS devant le service `frontend`, `.env` avec secret réel et `NV_ENV=prod`, sauvegarde des volumes `pgdata` et `nvdata`, purge quotidienne des exports.

## 8. Limites restantes

1. **Structure HDF5 non confirmée** sur un vrai granule : le premier travail utile est `scripts/inspect_granule.py`.
2. **Seuils de classification non validés.** Ils sont présentés comme un prototype et aucune précision n'est annoncée, car aucune n'a été mesurée.
3. Chemin PostGIS et images Docker jamais exécutés.
4. Identité anonyme par en-tête : pas une authentification.
5. Limiteur de débit en mémoire, par processus.
6. Les statistiques de zone et de changement supposent des grilles identiques.
7. Le service de recherche de lieu appelle OpenStreetMap depuis le navigateur de l'utilisateur, ce qui transmet la requête à un tiers. Les coordonnées saisies directement ne sortent pas.
8. Le certificat atteste de la fin du parcours pédagogique, il n'a aucune valeur officielle.

## 9. Pistes d'amélioration

Ingérer une vraie zone et en tirer un récit réel avec une source externe pour la cause des changements. Faire valider ou recalibrer les seuils par un spécialiste. Ajouter le rééchantillonnage sur grille commune et la mosaïque multi-granules. Stockage objet pour les COG. Authentification réelle si des comptes sont voulus. Dessin de polygone libre et import GeoJSON dans l'interface. Autres produits (GUNW pour l'InSAR réel, SME2 pour l'humidité). Version anglaise.
