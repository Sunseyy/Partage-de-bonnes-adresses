import pytest
from flask_app import model


@pytest.fixture
def connection():
  connection = model.connect(':memory:')
  model.create_database(connection)
  return connection


@pytest.fixture
def user_id(connection):
  return model.add_user(connection, 'alice', 'motdepasse1')


def new_place(user_id, name='Chez Test', category='cafe', photo=None):
  return {
    'id': None, 'user_id': user_id, 'name': name,
    'address': '1 rue de Test, Marseille', 'category': category,
    'description': 'Une description', 'latitude': 43.3, 'longitude': 5.4,
    'photo': photo
  }


def names(places):
  return [place['name'] for place in places]


# ---------- Utilisateurs ----------

def test_add_user_and_get_user(connection, user_id):
  user = model.get_user(connection, 'alice', 'motdepasse1')
  assert user == {'id': user_id, 'username': 'alice'}


def test_password_is_stored_hashed(connection, user_id):
  row = connection.execute('SELECT password_hash FROM users').fetchone()
  assert 'motdepasse1' not in row['password_hash']
  assert row['password_hash'].startswith('$argon2')


def test_add_user_twice_is_refused_whatever_the_case(connection, user_id):
  with pytest.raises(Exception) as exception_info:
    model.add_user(connection, 'ALICE', 'autremotdepasse')
  assert str(exception_info.value) == "Ce nom d'utilisateur est déjà utilisé"
  # Une transaction restée ouverte verrouillerait la base pour les autres connexions
  assert not connection.in_transaction


def test_user_exists(connection, user_id):
  assert model.user_exists(connection, user_id)
  assert not model.user_exists(connection, 'identifiant-inconnu')


def test_get_user_wrong_password(connection, user_id):
  with pytest.raises(Exception) as exception_info:
    model.get_user(connection, 'alice', 'mauvais')
  assert str(exception_info.value) == 'Utilisateur inconnu'


def test_get_user_unknown(connection):
  with pytest.raises(Exception) as exception_info:
    model.get_user(connection, 'personne', 'motdepasse1')
  assert str(exception_info.value) == 'Utilisateur inconnu'


# ---------- Adresses ----------

def test_insert_place_and_place(connection, user_id):
  place_id = model.insert_place(connection, new_place(user_id))
  place = model.place(connection, place_id)
  assert place['name'] == 'Chez Test'
  assert place['author'] == 'alice'
  assert place['photo'] is None
  assert place['average_rating'] is None
  assert place['review_count'] == 0


def test_place_keeps_its_photo(connection, user_id):
  place_id = model.insert_place(connection, new_place(user_id, photo='abc.jpg'))
  assert model.place(connection, place_id)['photo'] == 'abc.jpg'
  changes = dict(new_place(user_id, photo=None), id=place_id)
  model.update_place(connection, changes)
  assert model.place(connection, place_id)['photo'] is None


def test_unknown_place(connection):
  with pytest.raises(model.UnknownPlace):
    model.place(connection, 999)


def test_places_filter_by_category(connection, user_id):
  model.insert_place(connection, new_place(user_id, 'Un café', 'cafe'))
  model.insert_place(connection, new_place(user_id, 'Un restaurant', 'restaurant'))
  assert len(model.places(connection)) == 2
  assert names(model.places(connection, 'restaurant')) == ['Un restaurant']


def test_places_filter_by_user(connection, user_id):
  bob = model.add_user(connection, 'bob', 'motdepasse2')
  model.insert_place(connection, new_place(user_id, "Lieu d'Alice"))
  model.insert_place(connection, new_place(bob, 'Lieu de Bob'))
  assert names(model.places(connection, user_id=bob)) == ['Lieu de Bob']


def test_places_search_ignores_case_and_accents(connection, user_id):
  model.insert_place(connection, new_place(user_id, 'Café de la Gare'))
  model.insert_place(connection, new_place(user_id, 'Hôtel du Port', 'hebergement'))
  assert names(model.places(connection, search='CAFE')) == ['Café de la Gare']
  assert names(model.places(connection, search='hotel')) == ['Hôtel du Port']
  # Tous les mots doivent être trouvés, dans le nom, l'adresse, la description ou la catégorie
  assert names(model.places(connection, search='port marseille')) == ['Hôtel du Port']
  assert names(model.places(connection, search='hébergements')) == ['Hôtel du Port']
  assert model.places(connection, search='port lyon') == []


def test_places_search_is_not_interpreted_as_sql(connection, user_id):
  model.insert_place(connection, new_place(user_id))
  assert model.places(connection, search="'; DROP TABLE places; --") == []
  assert model.places(connection, search='%') == []
  assert len(model.places(connection)) == 1


def test_places_average_and_sort_by_rating(connection, user_id):
  bob = model.add_user(connection, 'bob', 'motdepasse2')
  good = model.insert_place(connection, new_place(user_id, 'Bon'))
  bad = model.insert_place(connection, new_place(user_id, 'Mauvais'))
  model.insert_place(connection, new_place(user_id, 'Sans avis'))
  model.insert_review(connection, {'place_id': good, 'user_id': bob, 'rating': 5, 'comment': 'Top'})
  model.insert_review(connection, {'place_id': good, 'user_id': user_id, 'rating': 4, 'comment': 'Bien'})
  model.insert_review(connection, {'place_id': bad, 'user_id': bob, 'rating': 2, 'comment': 'Bof'})

  best = model.places(connection, None, 'best')
  assert names(best) == ['Bon', 'Mauvais', 'Sans avis']
  assert best[0]['average_rating'] == 4.5
  assert best[0]['review_count'] == 2
  worst = model.places(connection, None, 'worst')
  assert names(worst) == ['Mauvais', 'Bon', 'Sans avis']


def test_places_sort_by_name_and_by_date(connection, user_id):
  model.insert_place(connection, new_place(user_id, 'zèbre'))
  model.insert_place(connection, new_place(user_id, 'Abeille'))
  assert names(model.places(connection, None, 'name')) == ['Abeille', 'zèbre']
  assert names(model.places(connection, None, 'recent')) == ['Abeille', 'zèbre']
  model.insert_place(connection, new_place(user_id, 'Mouette'))
  assert names(model.places(connection, None, 'recent')) == ['Mouette', 'Abeille', 'zèbre']


def test_update_place_only_by_owner(connection, user_id):
  bob = model.add_user(connection, 'bob', 'motdepasse2')
  place_id = model.insert_place(connection, new_place(user_id))
  changes = dict(new_place(bob, 'Piraté'), id=place_id)
  assert model.update_place(connection, changes) == 0
  assert model.place(connection, place_id)['name'] == 'Chez Test'
  changes = dict(new_place(user_id, 'Renommé'), id=place_id)
  assert model.update_place(connection, changes) == 1
  assert model.place(connection, place_id)['name'] == 'Renommé'


def test_delete_place_only_by_owner_and_removes_reviews(connection, user_id):
  bob = model.add_user(connection, 'bob', 'motdepasse2')
  place_id = model.insert_place(connection, new_place(user_id))
  model.insert_review(connection, {'place_id': place_id, 'user_id': bob, 'rating': 3, 'comment': 'Ok'})
  assert model.delete_place(connection, place_id, bob) == 0
  assert model.delete_place(connection, place_id, user_id) == 1
  assert model.place_reviews(connection, place_id) == []


# ---------- Avis ----------

def test_review_only_once_per_place(connection, user_id):
  place_id = model.insert_place(connection, new_place(user_id))
  review = {'place_id': place_id, 'user_id': user_id, 'rating': 4, 'comment': 'Bien'}
  model.insert_review(connection, review)
  with pytest.raises(Exception) as exception_info:
    model.insert_review(connection, review)
  assert str(exception_info.value) == 'Vous avez déjà donné votre avis sur ce lieu'
  assert not connection.in_transaction
  assert model.user_review(connection, place_id, user_id)['rating'] == 4


def test_review_rating_must_be_between_1_and_5(connection, user_id):
  place_id = model.insert_place(connection, new_place(user_id))
  for rating in (0, 6):
    with pytest.raises(Exception):
      model.insert_review(connection, {
        'place_id': place_id, 'user_id': user_id, 'rating': rating, 'comment': 'Trop'})
  assert model.user_review(connection, place_id, user_id) is None


# ---------- Données de test ----------

def test_fill_database(connection, upload_folder):
  model.fill_database(connection)
  places = model.places(connection)
  assert len(places) == 11
  assert all(place['category'] in model.CATEGORIES for place in places)
  # Chaque photo d'exemple est copiée dans le dossier des photos
  photos = [place['photo'] for place in places if place['photo'] is not None]
  assert len(photos) == 10
  assert all((upload_folder / photo).is_file() for photo in photos)
