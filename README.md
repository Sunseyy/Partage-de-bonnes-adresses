# Partage de bonnes adresses

Projet universitaire de programmation web (sujet n°8). 
Bonne lecture ^^

## Présentation

**Partage de bonnes adresses** est une application web qui permet aux utilisateurs de découvrir, partager et évaluer des lieux tels que des restaurants, des cafés, des commerces, des hébergements et des espaces de loisirs.

L'objectif est de proposer une plateforme collaborative où chacun peut partager ses bonnes adresses et consulter les évaluations laissées par la communauté.

L'application est écrite en Python avec Flask. Les données sont enregistrées dans une base SQLite locale.

## Fonctionnalités

Les fonctionnalités demandées par le sujet :

- Inscription et connexion avec un nom d'utilisateur et un mot de passe.
- Ajout d'une adresse avec le nom du lieu, son adresse, sa catégorie et une description.
- Consultation des adresses et de leur note moyenne par les visiteurs, sans obligation de connexion.
- Publication d'avis avec une note de 1 à 5 et un commentaire, à raison d'un avis par utilisateur et par lieu.
- Consultation des commentaires réservée aux utilisateurs authentifiés.
- Filtrage des adresses par catégorie et tri par note moyenne.
- Affichage des lieux sur une carte avec un marqueur pour chaque lieu.
- Modification et suppression des adresses par leurs propriétaires uniquement.

Ce qui a été ajouté autour, d'après la maquette :

- Page d'accueil avec les adresses les mieux notées.
- Recherche par mots-clés dans le nom, l'adresse, la description et la catégorie, sans tenir compte des majuscules ni des accents.
- Page « Mes adresses » pour retrouver, modifier ou supprimer ses lieux.
- Photo facultative pour chaque adresse.
- Carte avec une couleur de marqueur par catégorie, une légende qui sert de filtre et une fiche pour le lieu sélectionné.
- Interface adaptée aux téléphones.

## Lancer le projet

### Prérequis

- Python 3 (le projet a été testé avec Python 3.14)
- Git
- Une connexion internet pour afficher le fond de carte et pour localiser une adresse que l'on ajoute (services d'OpenStreetMap). Le reste du site fonctionne sans.

### Installation

Sous Windows (PowerShell) :

```powershell
git clone https://github.com/Sunseyy/Partage-de-bonnes-adresses.git
cd Partage-de-bonnes-adresses
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item example.env .env
python init_db.py
flask run
```

Sous Linux/macOS :

```bash
git clone https://github.com/Sunseyy/Partage-de-bonnes-adresses.git
cd Partage-de-bonnes-adresses
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp example.env .env
python init_db.py
flask run
```

Quelques précisions :

- **`.env`** contient la configuration locale. Remplacez la valeur de `FLASK_SECRET_KEY` par une valeur aléatoire, par exemple celle affichée par `python -c "import secrets; print(secrets.token_hex(32))"`. Ce fichier n'est pas envoyé sur GitHub.
- **`python init_db.py`** crée la base `database.sqlite` et la remplit avec des données d'exemple (3 comptes, 11 adresses à Marseille, 19 avis). Relancer cette commande remet la base à zéro : les comptes, adresses et avis ajoutés depuis sont perdus.
- **`flask run`** démarre le site. Il se lance depuis le dossier du projet, comme `init_db.py` : c'est là que sont créés la base, le dossier `uploads/` (photos) et le dossier `flask_session/` (sessions).
- Si PowerShell refuse d'exécuter `Activate.ps1`, on peut se passer de l'activation en appelant directement le Python de l'environnement : `.venv\Scripts\python.exe -m pip install -r requirements.txt`, `.venv\Scripts\python.exe init_db.py`, puis `.venv\Scripts\python.exe -m flask run`.

### Ouvrir le site

Le site est servi en HTTPS avec un certificat auto-signé (`FLASK_RUN_CERT=adhoc` dans `.env`). Ouvrez **https://127.0.0.1:5000** (avec le « s » de https). Le navigateur affiche un avertissement la première fois : choisissez « Paramètres avancés », puis « Continuer vers 127.0.0.1 ».

### Comptes de test

| Nom d'utilisateur | Mot de passe |
|---|---|
| `alice` | `alice-2026` |
| `bob` | `bob-2026` |
| `charlie` | `charlie-2026` |

On peut aussi créer son propre compte depuis la page « Créer un compte ».

## Tests

```bash
python -m pytest
```

Les 87 tests vérifient les requêtes SQL (`test_model.py`), les pages et les droits d'accès (`test_app.py`) et la localisation des adresses (`test_geocoding.py`). Ils utilisent une base temporaire et n'appellent pas internet : ils ne modifient ni `database.sqlite` ni le dossier `uploads/`.

## Technologies

- **Langage :** Python
- **Framework :** Flask, avec des templates Jinja2
- **Base de données :** SQLite (fichier local `database.sqlite`)
- **Interface utilisateur :** HTML et CSS écrits à la main, un peu de JavaScript sans bibliothèque (le site reste utilisable sans JavaScript, sauf la carte)
- **Carte interactive :** Leaflet et les fonds de carte d'OpenStreetMap, avec le géocodage fait côté serveur en Python (service Nominatim)
- **Sécurité :** mots de passe hachés avec Argon2, protection CSRF (Flask-WTF), sessions côté serveur (Flask-Session), HTTPS et en-têtes de sécurité (Flask-Talisman)
- **Photos :** Pillow
- **Tests :** pytest

Les pages, les choix techniques et les mesures de sécurité sont détaillés dans [README-2.md](README-2.md).

## Structure du projet

```text
Partage-de-bonnes-adresses/
├── README.md             présentation et installation
├── README-2.md           notes techniques : pages, choix, sécurité
├── requirements.txt      dépendances Python
├── example.env           modèle du fichier .env
├── init_db.py            crée la base et la remplit avec les données d'exemple
└── flask_app/
    ├── __init__.py       application Flask : configuration, formulaires, routes
    ├── model.py          accès à la base de données (requêtes SQL)
    ├── build.sql         schéma de la base
    ├── data.py           données d'exemple
    ├── geocoding.py      transforme une adresse en coordonnées (Nominatim)
    ├── photos.py         vérifie et enregistre les photos envoyées
    ├── example_photos/   photos des données d'exemple
    ├── templates/        pages HTML (Jinja2)
    ├── static/           style.css, app.js, map.js, polices, Leaflet
    ├── conftest.py       réglages communs aux tests
    └── test_*.py         tests
```



## État du projet

**Statut :** les huit fonctionnalités du sujet sont en place et testées.

## Auteurs

- Aya Sara Beldi
- Oualid OKYCH

## Crédits

Les photos de démonstration viennent de [Wikimedia Commons](https://commons.wikimedia.org/). Elles ont été redimensionnées ; chacune reste sous la licence indiquée. Les lieux marqués « (exemple) » sont fictifs : leur photo illustre seulement le quartier ou le type de lieu. La même liste est affichée dans le site, sur la page « Crédits ».

| Utilisation | Photo | Auteur | Licence |
|---|---|---|---|
| Page d'accueil, connexion et inscription | [Le rouge aux fenêtres du Vieux Port](https://commons.wikimedia.org/wiki/File:Le_rouge_aux_fen%C3%AAtres_du_Vieux_Port.jpg) | Didier PILLET | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/deed.fr) |
| Notre-Dame de la Garde | [Basilique Notre-Dame-de-la-Garde in Marseille at sunset](https://commons.wikimedia.org/wiki/File:1027_Basilique_Notre-Dame-de-la-Garde_in_Marseille_at_sunset_Photo_by_Giles_Laurent.jpg) | Giles Laurent | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr) |
| Vieux-Port | [Vieux-Port de Marseille, France](https://commons.wikimedia.org/wiki/File:Vieux-Port_de_Marseille,_France.jpg) | Clément Bardot | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr) |
| Café de la Plaine (exemple) | [Warm cup of coffee on a table at a cafe](https://commons.wikimedia.org/wiki/File:Warm_cup_of_coffee_on_a_table_at_a_cafe.jpg) | Shixart1985 | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/deed.fr) |
| MuCEM | [Le Musée des Civilisations de l'Europe et de la Méditerranée - MuCEM (Marseille)](https://commons.wikimedia.org/wiki/File:Le_Mus%C3%A9e_des_Civilisations_de_l%27Europe_et_de_la_M%C3%A9diterran%C3%A9e_-_MuCEM_(Marseille)_(14178627994).jpg) | Jean-Pierre Dalbéra | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/deed.fr) |
| Palais Longchamp | [Palais Longchamp 2](https://commons.wikimedia.org/wiki/File:Palais_Longchamp_2.jpg) | kallerna | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr) |
| Restaurant du Panier (exemple) | [Bouillabaisse 07](https://commons.wikimedia.org/wiki/File:Bouillabaisse_07.jpg) | Arnaud 25 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr) |
| Hôtel du Vallon (exemple) | [Vallon des Auffes 011](https://commons.wikimedia.org/wiki/File:Vallon_des_Auffes_011.jpg) | Arnaud 25 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr) |
| Plage des Catalans | [Plage des catalans, Marseille](https://commons.wikimedia.org/wiki/File:Plage_des_catalans,_Marseille_(22463883475).jpg) | Jeanne Menjoulet | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/deed.fr) |
| Calanque de Sormiou | [Marseille Calanque Sormiou](https://commons.wikimedia.org/wiki/File:Marseille_Calanque_Sormiou.jpg) | Benh LIEU SONG | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/deed.fr) |
| Bar du Cours Julien (exemple) | [Cours Julien à Marseille (France)](https://commons.wikimedia.org/wiki/File:Cours_Julien_%C3%A0_Marseille_(France).jpg) | DC | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/deed.fr) |

- **Carte :** fond de carte et recherche des coordonnées © les contributeurs d'[OpenStreetMap](https://www.openstreetmap.org/copyright) (licence ODbL), avec le service Nominatim. Affichage par [Leaflet](https://leafletjs.com/) (licence BSD à 2 clauses).
- **Polices :** [Outfit](https://fonts.google.com/specimen/Outfit) et [Caveat](https://fonts.google.com/specimen/Caveat), sous licence SIL Open Font License 1.1 (textes des licences dans `flask_app/static/fonts/`).
- **Icônes :** dessinées d'après [Feather](https://feathericons.com/) (licence MIT) et [Lucide](https://lucide.dev/) (licence ISC).

## Licence

Projet réalisé dans le cadre d'un travail universitaire pourle Master R&T Promos 2026-2027. ^^
