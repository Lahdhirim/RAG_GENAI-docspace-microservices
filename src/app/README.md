# Docspace — Frontend documentaire

Application Angular 21 / TypeScript autonome. **Tout le frontend, sa configuration et ses tests se trouvent dans `src/app/` du dépôt.** Aucun changement du backend ou de l'infrastructure n'est nécessaire au développement du frontend.

## Démarrage

Prérequis : Node.js 22.12+ ou 24 et npm.

```sh
cd src/app
npm ci
npm start
```

Ouvrir http://localhost:4200. Le serveur Angular transmet **uniquement `/documents`** à FastAPI via `proxy.conf.cjs` (cible par défaut : http://127.0.0.1:8000, port publié par le Compose existant). Le service Document Manager et sa base doivent être disponibles ; le frontend ne les démarre pas. Si l'API est sur une autre machine, adapter uniquement la cible du proxy frontend.

L'application appelle exclusivement `GET /documents`. L'URL de navigation `/documents` est également une route Angular : le proxy du serveur de développement distingue une navigation HTML d'une requête HTTP de données. Aucun endpoint de détail, de téléchargement ou de mutation n'est supposé.

## Fonctionnalités

- Tableau des noms, chemins, extensions, tailles, dates de modification, présence et état de parsing.
- Compteurs issus des données de l'API ; taille totale incluant les documents absents référencés.
- Filtres par nom/chemin, présence et extension, tri par nom, taille ou modification, pagination locale de 10 lignes.
- Détails de toutes les métadonnées disponibles, sans requête supplémentaire ; dates nulles affichées par `—`.
- Chargement, bibliothèque vide, filtres sans résultat, erreur HTTP/réseau, réponse invalide, délai de 15 secondes et réessai.
- Interface responsive, tableau à défilement horizontal sur petits écrans, navigation clavier et dialogue natif (Échap, focus contenu et retour au déclencheur).
- Rubriques Parsing, Recherche OpenSearch et Agent IA désactivées et marquées « À venir ».

Les filtres et le tri opèrent **localement** sur la liste récupérée ; il ne s'agit pas d'une recherche OpenSearch. Les indicateurs de parsing sont uniquement ceux renvoyés par l'API. Une actualisation échouée masque le tableau ; les compteurs précédents restent visibles avec la mention « Actualisation en échec ».

## Contrat API

Source consultée : `src/services/doc_manager_service/app.py`, `models/document.py` et `database/queries.py` sur `worker-service`. La réponse est `{ "documents": [...] }`, avec `filename` (et non la colonne SQL `file_name`), `id`, `relative_path`, `extension`, `content_hash`, `size_bytes`, `is_present`, `is_parsed`, `file_created_at`, `file_modified_at`, `file_accessed_at`, `created_at`, `updated_at`. Les cinq dates peuvent être nulles. Les booléens sérialisés par Pydantic sont des booléens JSON.

Le service valide la structure de la réponse avant affichage. Aucun jeu de données de démonstration n'est injecté dans l'application.

## Architecture

- `src/core/documents/` : contrat typé, validation et accès HTTP.
- `src/features/documents/` : écran documentaire chargé à la demande, état via signals et filtres calculés.
- `src/shared/` : présentation des tailles et des dates.
- `src/app.component.ts`, `src/app.routes.ts` : coque et navigation. De futures fonctionnalités pourront ajouter leurs propres routes et services sans coupler l'écran documentaire aux microservices.
- Configuration Angular, TypeScript, proxy et dépendances verrouillées à la racine de ce dossier.

## Compilation et tests

```sh
npm run build
npm test
npx playwright install chromium
npm run test:e2e
```

`npm run build` génère `dist/documents/browser/`. Les tests unitaires couvrent le contrat, les réponses invalides, erreurs HTTP et timeout. Les tests Playwright lancent le serveur Angular et interceptent les réponses `GET /documents` : affichage, filtres, tri, pagination, détails, états de chargement/erreur/vide, réessai, nombre et méthode des appels, absence de débordement global et erreurs JavaScript, sur ordinateur et mobile.

Pour utiliser un Chromium déjà installé :

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e
```

Les tests simulés ne remplacent pas une validation d'intégration avec une instance FastAPI et une base actives.

## Hébergement futur

Le build utilise une URL relative `/documents`. L'hébergement de production devra transmettre les appels de données `GET /documents` au Document Manager et servir l'entrée Angular pour les navigations HTML, y compris lors d'un accès direct à la route `/documents`. Le proxy Angular est limité au développement et ne fait pas partie du build. Cette configuration de production reste à la charge de l'infrastructure ; aucun Dockerfile ni Compose n'est modifié ici.
