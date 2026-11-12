import sqlite3
import os
import unicodedata
from uuid import uuid4
from flask_app import data
from flask_app import photos
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

passwordHasher = PasswordHasher()

# Catégories : la clé est enregistrée en base (elle sert aussi dans les URL
# et les classes CSS), le libellé est le texte affiché.
CATEGORIES = {
  'restaurant': 'Restaurant',
  'cafe': 'Café',
  'loisirs': 'Loisirs',
  'commerce': 'Commerce',
  'hebergement': 'Hébergement',
  'autre': 'Autre'
}

CATEGORY_PLURALS = {
  'restaurant': 'Restaurants',
  'cafe': 'Cafés',
  'loisirs': 'Loisirs',
  'commerce': 'Commerces',
  'hebergement': 'Hébergements',
  'autre': 'Autres'
}

# Clés autorisées pour le tri et leur libellé affiché
SORTS = {
  'best': 'Note moyenne',
  'worst': 'Note la plus basse',
  'name': 'Nom (A à Z)',
  'recent': 'Ajouts récents'
}

# ORDER BY ne peut pas être paramétré : on choisit dans une liste fixe,
# jamais à partir d'un texte envoyé par l'utilisateur.
ORDER_BY = {
  'name': 'places.name COLLATE NOCASE',
  'best': '''AVG(reviews.rating) IS NULL, AVG(reviews.rating) DESC,
             places.name COLLATE NOCASE''',
  'worst': '''AVG(reviews.rating) IS NULL, AVG(reviews.rating) ASC,
              places.name COLLATE NOCASE''',
  'recent': 'places.id DESC'
}


class UnknownPlace(Exception):
  pass


def dictionary_factory(cursor, row):
  dictionary = {}
  for index in range(len(cursor.description)):
    column_name = cursor.description[index][0]
    dictionary[column_name] = row[index]
  return dictionary

def normalize(text : str) -> str:
  # Minuscules sans accents, pour que « cafe » trouve aussi « Café »
  text = text.lower().replace('œ', 'oe').replace('’', "'")
  decomposed = unicodedata.normalize('NFD', text)
  return ''.join(c for c in decomposed if not unicodedata.combining(c))

def search_matches(search : str, name : str, address : str,
                   description : str, category : str) -> bool:
  # Fonction appelée par SQLite pour chaque adresse (voir connect) : vrai si
  # tous les mots recherchés figurent dans le nom, l'adresse, la description
  # ou la catégorie du lieu.
  text = normalize(' '.join([
    name, address, description,
    CATEGORIES.get(category, ''), CATEGORY_PLURALS.get(category, '')]))
  return all(word in text for word in normalize(search).split())

def connect(database : str = None) -> sqlite3.Connection:
  if database is None:
    database = os.getenv('DATABASE', 'database.sqlite')
  connection = sqlite3.connect(database)
  connection.execute('PRAGMA foreign_keys = 1')
  connection.row_factory = dictionary_factory
  connection.create_function('search_matches', 5, search_matches,
                             deterministic=True)
  return connection

def read_build_script() -> str:
  path = os.path.join(os.path.dirname(__file__), 'build.sql')
  with open(path) as file:
    script = file.read()
  return script

def create_database(connection : sqlite3.Connection):
  script = read_build_script()
  connection.executescript(script)
  connection.commit()

# ---------- Utilisateurs ----------

def add_user(connection : sqlite3.Connection, username: str, password: str) -> str:
  sql = '''
    INSERT INTO users(id, username, password_hash)
    VALUES (:id, :username, :password_hash);
  '''
  user_id = str(uuid4())
  password_hash = passwordHasher.hash(password)
  try:
    connection.execute(sql, {
      'id': user_id,
      'username': username,
      'password_hash': password_hash
    })
    connection.commit()
  except sqlite3.IntegrityError:
    # Un INSERT refusé laisse sa transaction ouverte : sans rollback, la base
    # resterait verrouillée pour les autres connexions (« database is locked »)
    connection.rollback()
    raise Exception("Ce nom d'utilisateur est déjà utilisé")
  return user_id

def user_exists(connection : sqlite3.Connection, user_id : str) -> bool:
  sql = '''
    SELECT id FROM users
    WHERE id = :id;
  '''
  return len(connection.execute(sql, {'id': user_id}).fetchall()) > 0

def get_user(connection : sqlite3.Connection, username: str, password: str) -> dict:
  sql = '''
    SELECT * FROM users
    WHERE username = :username;
  '''
  cursor = connection.execute(sql, {'username': username})
  rows = cursor.fetchall()
  if len(rows) == 0:
    raise Exception('Utilisateur inconnu')
  user = rows[0]
  try:
    passwordHasher.verify(user['password_hash'], password)
  except VerifyMismatchError:
    raise Exception('Utilisateur inconnu')
  return {'id': user['id'], 'username': user['username']}

# ---------- Adresses ----------

PLACE_SELECT = '''
  SELECT places.*, users.username AS author,
         AVG(reviews.rating) AS average_rating,
         COUNT(reviews.id) AS review_count
  FROM places
  JOIN users ON places.user_id = users.id
  LEFT JOIN reviews ON reviews.place_id = places.id
'''

def places(connection : sqlite3.Connection, category : str = None,
           sort : str = 'name', search : str = None,
           user_id : str = None) -> list:
  # Chaque filtre est facultatif : NULL veut dire « pas de filtre »
  sql = PLACE_SELECT + '''
    WHERE (:category IS NULL OR places.category = :category)
      AND (:user_id IS NULL OR places.user_id = :user_id)
      AND (:search IS NULL OR search_matches(
            :search, places.name, places.address,
            places.description, places.category))
    GROUP BY places.id
    ORDER BY ''' + ORDER_BY[sort] + ';'
  return connection.execute(sql, {
    'category': category,
    'user_id': user_id,
    'search': search
  }).fetchall()

def place(connection : sqlite3.Connection, id : int) -> dict:
  sql = PLACE_SELECT + '''
    WHERE places.id = :id
    GROUP BY places.id;
  '''
  rows = connection.execute(sql, {'id': id}).fetchall()
  if len(rows) == 0:
    raise UnknownPlace('Lieu inconnu')
  return rows[0]

def insert_place(connection : sqlite3.Connection, place : dict) -> int:
  # place['photo'] est le nom du fichier de la photo, ou None s'il n'y en a pas
  sql = '''
    INSERT INTO places(id, user_id, name, address, category, description,
                       latitude, longitude, photo)
    VALUES (:id, :user_id, :name, :address, :category, :description,
            :latitude, :longitude, :photo);
  '''
  cursor = connection.execute(sql, place)
  connection.commit()
  return cursor.lastrowid

def update_place(connection : sqlite3.Connection, place : dict) -> int:
  # La condition sur user_id garantit qu'on ne modifie que ses propres adresses
  sql = '''
    UPDATE places
    SET name = :name, address = :address, category = :category,
        description = :description, latitude = :latitude,
        longitude = :longitude, photo = :photo
    WHERE id = :id AND user_id = :user_id;
  '''
  cursor = connection.execute(sql, place)
  connection.commit()
  return cursor.rowcount

def delete_place(connection : sqlite3.Connection, id : int, user_id : str) -> int:
  sql = '''
    DELETE FROM places
    WHERE id = :id AND user_id = :user_id;
  '''
  cursor = connection.execute(sql, {'id': id, 'user_id': user_id})
  connection.commit()
  return cursor.rowcount

# ---------- Avis ----------

def insert_review(connection : sqlite3.Connection, review : dict) -> None:
  sql = '''
    INSERT INTO reviews(place_id, user_id, rating, comment)
    VALUES (:place_id, :user_id, :rating, :comment);
  '''
  try:
    connection.execute(sql, review)
    connection.commit()
  except sqlite3.IntegrityError:
    # Même raison que dans add_user : on referme la transaction restée ouverte
    connection.rollback()
    raise Exception('Vous avez déjà donné votre avis sur ce lieu')

def place_reviews(connection : sqlite3.Connection, place_id : int) -> list:
  sql = '''
    SELECT reviews.*, users.username
    FROM reviews
    JOIN users ON reviews.user_id = users.id
    WHERE place_id = :place_id
    ORDER BY created_at DESC, reviews.id DESC;
  '''
  return connection.execute(sql, {'place_id': place_id}).fetchall()

def user_review(connection : sqlite3.Connection, place_id : int, user_id : str):
  sql = '''
    SELECT * FROM reviews
    WHERE place_id = :place_id AND user_id = :user_id;
  '''
  rows = connection.execute(
    sql, {'place_id': place_id, 'user_id': user_id}).fetchall()
  return rows[0] if len(rows) > 0 else None

# ---------- Données de test ----------

def fill_database(connection : sqlite3.Connection):
  user_ids = {}
  for user in data.users():
    user_ids[user['username']] = add_user(
      connection, user['username'], user['password'])
  place_ids = {}
  for place in data.places():
    place_ids[place['name']] = insert_place(connection, {
      'id': None,
      'user_id': user_ids[place['user']],
      'name': place['name'],
      'address': place['address'],
      'category': place['category'],
      'description': place['description'],
      'latitude': place['latitude'],
      'longitude': place['longitude'],
      'photo': photos.install_example(place['photo'])
    })
  for review in data.reviews():
    insert_review(connection, {
      'place_id': place_ids[review['place']],
      'user_id': user_ids[review['user']],
      'rating': review['rating'],
      'comment': review['comment']
    })
