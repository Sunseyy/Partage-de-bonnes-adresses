# Partage de bonnes adresses (sujet n°8) : notes techniques

Application Flask + SQLite pour partager des adresses, les noter et les voir sur une carte.
La présentation du projet et l'installation détaillée sont dans [README.md](README.md).

## Lancement rapide

```
python -m venv .venv
source .venv/bin/activate  # sous Windows : .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp example.env .env        # puis changez FLASK_SECRET_KEY
python init_db.py          # crée database.sqlite avec des données de test
flask run
```

Le site est servi en HTTPS avec un certificat auto-signé (`FLASK_RUN_CERT=adhoc` dans `.env`) : ouvrez
https://127.0.0.1:5000 et acceptez l'avertissement du navigateur.

Comptes de test : `alice / alice-2026`, `bob / bob-2026`, `charlie / charlie-2026`.

Tests : `python -m pytest` (87 tests, sur une base temporaire et sans accès à internet).

## Pages

| Page | Adresse | Accès |
|---|---|---|
| Accueil : présentation, recherche, adresses les mieux notées | `/` | public |
| Explorer : liste des adresses, moyennes, recherche, filtre par catégorie, tri par note | `/explore` | public |
| Carte avec un marqueur par lieu (Leaflet + OpenStreetMap) | `/map` | public |
| Fiche d'un lieu : note moyenne et nombre d'avis | `/place/<id>` | public |
| Commentaires du lieu, avis 1 à 5 + commentaire (une seule fois par lieu) | `/place/<id>` | connecté |
| Ajouter une adresse (nom, adresse, catégorie, description, photo facultative) | `/place/create` | connecté |
| Mes adresses | `/my-places` | connecté |
| Modifier / supprimer ses propres adresses (403 sinon) | `/place/<id>/edit`, `/place/<id>/delete` | propriétaire |
| Inscription / connexion (nom d'utilisateur + mot de passe Argon2) | `/register`, `/login` | public |
| Déconnexion (formulaire POST) | `/logout` | connecté |
| Photos envoyées par les utilisateurs | `/photos/<fichier>` | public |
| Crédits (photos, carte, polices, icônes) | `/credits` | public |

## Choix techniques

- Structure du projet du prof : `model.py` (SQL), `build.sql`, `__init__.py` (routes), templates Jinja2.
- Trois tables : `users`, `places`, `reviews`. Les règles importantes sont aussi garanties par la base :
  nom d'utilisateur unique sans tenir compte des majuscules (`UNIQUE COLLATE NOCASE`), note entre 1 et 5 (`CHECK`),
  un seul avis par utilisateur et par lieu (`UNIQUE (place_id, user_id)`), avis supprimés avec leur lieu (`ON DELETE CASCADE`).
- La moyenne des notes est calculée en SQL (`AVG` + `LEFT JOIN`), le tri est choisi dans une liste fixe (`model.ORDER_BY`).
- Les catégories sont une liste fixe (`model.CATEGORIES`).
- La recherche passe par une fonction Python déclarée à SQLite (`search_matches`) : elle ignore les majuscules
  et les accents, et tous les mots saisis doivent être trouvés.
- Une seule connexion SQLite par requête, rangée dans `flask.g` et fermée à la fin de la requête
  (`get_connection` et `close_connection`). Une écriture refusée par la base est annulée (`rollback`) :
  sinon sa transaction resterait ouverte et bloquerait les requêtes suivantes (« database is locked »).
- L'adresse saisie est transformée en coordonnées par l'API Nominatim (OpenStreetMap), appelée côté serveur
  (`geocoding.py`). En modification, l'appel n'est refait que si l'adresse a changé.
- Photos (`photos.py`) : c'est Pillow qui vérifie que le fichier est bien une image (JPEG, PNG ou WebP, 10 Mo au plus).
  Une image trop grande est réduite à 1600 pixels pour son plus grand côté, puis tout est réenregistré en JPEG
  sous un nom tiré au hasard, ce qui retire aussi les métadonnées (position GPS, appareil). Les fichiers vont
  dans `uploads/`, en dehors de `static/`, et sont servis par la route `/photos/<fichier>`.
- Interface écrite en HTML et CSS sans framework, d'après la maquette : barre latérale sur ordinateur,
  barre d'onglets en bas de l'écran sur téléphone. Les polices et les icônes sont servies par le site
  (`static/fonts/` et `templates/_icons.html`), rien ne vient d'un CDN.
- Les formulaires fonctionnent sans JavaScript. `static/app.js` ajoute seulement du confort (fenêtre « Laisser un avis »,
  aperçu de la photo, affichage du mot de passe, filtres appliqués dès qu'on les change sur grand écran)
  et `static/map.js` affiche la carte, qui est la seule partie du site à avoir besoin de JavaScript.
- Leaflet 1.9.4 est copié dans `static/leaflet/` (pas de CDN).

## Sécurité

- Requêtes SQL paramétrées, échappement automatique de Jinja2.
- Mots de passe hachés avec Argon2. Le message d'erreur est le même pour un compte inconnu et pour un mauvais mot de passe.
- Sessions côté serveur (Flask-Session, dossier `flask_session/`). Le cookie est `Secure`, `HttpOnly` et `SameSite=Strict`,
  il disparaît à la fermeture du navigateur, et l'identifiant de session est renouvelé à la connexion.
  Si le compte n'existe plus (base recréée par `init_db.py`), la session est fermée.
- CSRF (Flask-WTF) sur tous les formulaires, déconnexion comprise.
- Les droits sont vérifiés deux fois : dans la vue (403 si l'adresse appartient à quelqu'un d'autre) et dans le SQL
  (`WHERE id = :id AND user_id = :user_id`).
- Les commentaires ne sont lus dans la base et envoyés au navigateur que pour un utilisateur connecté.
- Après la connexion, on ne redirige que vers une page du site (`is_local_path`).
- HTTPS obligatoire, HSTS et en-têtes de sécurité (Flask-Talisman). La CSP reste stricte : `default-src 'none'`,
  scripts, styles et polices uniquement depuis le site lui-même, donc aucun script ni style écrit dans les pages.
  Les images viennent du site et des tuiles `tile.openstreetmap.org` ; `data:` est permis pour les images
  parce que Leaflet remplace une tuile abandonnée par une image vide écrite dans son adresse.
- `Permissions-Policy` : seule la position est permise, pour le bouton « Me localiser » de la carte.
- Pages d'erreur du site pour les codes 400, 403, 404, 405, 413 et 500. Le détail d'une erreur imprévue
  reste dans le journal du serveur.
