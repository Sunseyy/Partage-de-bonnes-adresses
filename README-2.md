# Partage de bonnes adresses (sujet n°8)

Application Flask + SQLite pour partager des adresses, les noter et les voir sur une carte.

## Installation

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp example.env .env        # puis changez FLASK_SECRET_KEY
python init_db.py          # crée database.sqlite avec des données de test
flask run
```

Le site est servi en HTTPS avec un certificat auto-signé (`FLASK_RUN_CERT=adhoc` dans `.env`) : ouvrez
https://127.0.0.1:5000 et acceptez l'avertissement du navigateur.

Comptes de test : `alice / alice-2026`, `bob / bob-2026`, `charlie / charlie-2026`.

Tests : `python -m pytest`

## Fonctionnalités

| Fonctionnalité | Où |
|---|---|
| Inscription / connexion (nom d'utilisateur + mot de passe Argon2) | `/register`, `/login` |
| Parcourir les adresses, moyennes, filtre par catégorie, tri par note | `/` (public) |
| Carte avec un marqueur par lieu (Leaflet + OpenStreetMap) | `/map` (public) |
| Ajouter une adresse (nom, adresse, catégorie, description) | `/place/create` |
| Modifier / supprimer ses propres adresses (403 sinon) | `/place/<id>/edit`, `/place/<id>/delete` |
| Avis 1 à 5 + commentaire, une seule fois par lieu | `/place/<id>` |
| Commentaires visibles seulement une fois connecté | `/place/<id>` |

## Choix techniques

- Structure du projet du prof : `model.py` (SQL), `build.sql`, `__init__.py` (routes), templates Jinja2.
- Sécurité : requêtes SQL paramétrées, mots de passe hachés avec Argon2, sessions côté serveur (Flask-Session),
  CSRF (Flask-WTF) sur tous les formulaires, en-têtes de sécurité et CSP (Flask-Talisman), échappement automatique de Jinja2.
- L'adresse saisie est transformée en coordonnées par l'API Nominatim (OpenStreetMap), appelée côté serveur
  (`geocoding.py`). Aucun JavaScript n'est nécessaire dans les formulaires.
- Le JavaScript sert uniquement à afficher la carte. Leaflet 1.9.4 est copié dans `static/leaflet/`
  (pas de CDN), donc la CSP reste stricte : scripts uniquement depuis le site lui-même, images depuis
  le site et les tuiles `tile.openstreetmap.org`.
- La moyenne des notes est calculée en SQL (`AVG` + `LEFT JOIN`), le tri est choisi dans une liste fixe.
- Les catégories sont une liste fixe (`model.CATEGORIES`).
