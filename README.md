# Partage de bonnes adresses

## Présentation

**Partage de bonnes adresses** est une application qui permet aux utilisateurs de découvrir, partager et évaluer des lieux tels que des restaurants, des cafés, des commerces et des espaces de loisirs.

L'objectif est de proposer une plateforme collaborative où chacun peut partager ses bonnes adresses et consulter les évaluations laissées par la communauté.

## Fonctionnalités prévues

- Inscription et connexion avec un nom d'utilisateur et un mot de passe.
- Ajout d'une adresse avec le nom du lieu, son adresse, sa catégorie et une description.
- Consultation des adresses par les visiteurs, sans obligation de connexion.
- Publication d'avis avec une note de 1 à 5 et un commentaire, à raison d'un avis par utilisateur et par lieu.
- Consultation des commentaires réservée aux utilisateurs authentifiés.
- Filtrage des adresses par catégorie et tri par note moyenne.
- Affichage des lieux sur une carte avec des marqueurs.
- Modification et suppression des adresses par leurs propriétaires.

## Technologies envisagées

- **Langage :** Python
- **Base de données :** à définir
- **Framework :** à définir
- **Interface utilisateur :** à définir
- **Carte interactive :** à définir

Les choix techniques seront précisés après validation des consignes avec l'enseignant.

## Structure du projet

```text
partage-bonnes-adresses/
├── README.md
├── .gitignore
├── requirements.txt
├── .env.example
├── app/
│   └── __init__.py
├── tests/
└── docs/
    └── questions-prof.md
```

## Installation

### Prérequis

- Python 3 installé
- Git installé

### Récupérer le projet

```bash
git clone URL_DU_DEPOT
cd partage-bonnes-adresses
```

Remplacer `URL_DU_DEPOT` par l'URL du dépôt GitHub.

### Créer un environnement virtuel

Sous Windows :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Sous Linux/macOS :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Installer les dépendances

```bash
pip install -r requirements.txt
```

Les dépendances seront ajoutées à ce fichier après le choix du framework et des outils utilisés.

## Travail en équipe

Le projet est développé en collaboration à l'aide de Git et GitHub.

- `main` : branche principale contenant la version stable du projet.
- `feature/*` : branches dédiées au développement des fonctionnalités.
- Les modifications sont proposées via des Pull Requests avant leur intégration dans `main`.

## Tests

Les tests seront regroupés dans le dossier `tests/` afin de vérifier le bon fonctionnement des fonctionnalités développées.

## État du projet

**Statut :** initialisation du projet.

Les choix techniques, la conception de la base de données et l'implémentation des fonctionnalités restent à définir.

## Auteurs

- Aya Sara Beldi
- Oualid OKYCH

## Licence

Projet réalisé dans le cadre d'un travail universitaire.
