# Données NISAR : sources, maturité, ce qui est vérifié

## Source principale

NISAR est la source scientifique de la plateforme. Les produits viennent d'ASF DAAC (NASA Earthdata). L'accès est gratuit avec un compte Earthdata. Les sources externes (fond OpenStreetMap, éventuellement Sentinel) ne servent que de contexte visuel et ne sont jamais présentées comme des observations NISAR.

Références consultées pendant le développement :
- https://nisar-docs.asf.alaska.edu/availability-overview/
- https://www.earthdata.nasa.gov/news/nisar-l-band-data-released-expanding-record-surface-changes

## Niveaux de maturité (état au 15 novembre 2026)

| Niveau | Mise à disposition | Acquisitions couvertes | Remarque |
|---|---|---|---|
| Beta | 27 février 2026 | 17 octobre 2025 au 20 janvier 2026 | Couverture partielle |
| Provisional | 20 juillet 2026 | 17 juin 2026 à fin octobre 2026 | Niveaux 0 à 3 |
| Validated | 6 novembre 2026 | À partir du 21 octobre 2026 | Niveaux 0 à 2 |

Un trou permanent existe du 27 juillet au 10 août 2026. Le retraitement des données antérieures au 21 octobre 2026 est annoncé pour 2027. Ces informations viennent de la documentation ASF au moment de la rédaction et peuvent évoluer : à revérifier avant publication.

La plateforme ne mélange jamais deux niveaux de maturité sans le dire. La détection de changement signale quand deux produits n'ont pas la même maturité, et l'interface affiche la maturité de chaque date.

## Produits utilisés

Le MVP lit uniquement le produit **L2 GCOV** (covariance polarimétrique géocodée), bandes réelles HHHH et HVHV. Les termes croisés complexes sont ignorés. Les autres produits (GSLC, GUNW, GOFF, SME2...) ne sont pas traités.

## Ce qui est confirmé et ce qui ne l'est pas

| Élément | Statut |
|---|---|
| Recherche ASF via `asf_search` avec `dataset=NISAR`, `dataMaturity`, `processingLevel` | Vérifié dans la documentation et la bibliothèque installée, **jamais exécuté contre le vrai serveur** (accès bloqué) |
| Chemins HDF5 `/science/LSAR/GCOV/grids/frequencyA/...` et `/science/LSAR/identification/...` | **Non confirmé** sur un granule réel. Écrits d'après la documentation publique |
| Noms des attributs (`epsg_code`, `_FillValue`) | **Non confirmé** |
| Seuils de classification (`gcov_lband_prototype_v0_1.json`) | Illustratifs, **non validés** par un expert, aucune précision n'est annoncée |
| Chaîne d'ingestion (validation, COG, manifeste, quarantaine) | Testée sur granules simulés au même format que le lecteur attend |

## Procédure de première ingestion réelle

1. `python scripts/inspect_granule.py granule.h5 --tree` : repérer les chemins absents.
2. Corriger `backend/app/ingestion/hdf5_gcov.py` si besoin (constantes `GRID_PATH`, `ID_PATH` en tête de fichier).
3. `python -m app.cli ingest-local granule.h5 --maturity validated`.
4. Si le produit est invalide, il est mis en quarantaine (`data/quarantine/`) avec la raison dans la table `ingestion_run`.
5. Ouvrir la carte, décocher la démonstration, vérifier que les dates réelles apparaissent et comparer visuellement avec ASF Vertex.
6. Faire relire les seuils du traducteur par un spécialiste avant de les présenter comme autre chose qu'un prototype.

## Données de démonstration

`python -m app.cli seed-demo` génère six granules simulés (paysage artificiel près de Douala : lac, zone bâtie, sol nu, forêt, défrichement progressif). Ils portent `is_demo=true` et la maturité `demo`, n'apparaissent que si l'utilisateur coche l'option, et déclenchent un bandeau jaune permanent.
