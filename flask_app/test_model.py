import sqlite3
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


def new_place(user_id, name='Chez Test', category='Café'):
  return {
    'id': None, 'user_id': user_id, 'name': name,
    'address': '1 rue de Test, Marseille', 'category': category,
    'description': 'Une description', 'latitude': 43.3, 'longitude': 5.4
  }


def test_add_user_and_get_user(connection, user_id):
  user = model.get_user(connection, 'alice', 'motdepasse1')
  assert user == {'id': user_id, 'username': 'alice'}


def test_add_user_twice_is_refused_whatever_the_case(connection, user_id):
  with pytest.raises(Exception) as exception_info:
    model.add_user(connection, 'ALICE', 'autremotdepasse')
  assert str(exception_info.value) == "Ce nom d'utilisateur est déjà utilisé"


def test_get_user_wrong_password(connection, user_id):
  with pytest.raises(Exception) as exception_info:
    model.get_user(connection, 'alice', 'mauvais')
  assert str(exception_info.value) == 'Utilisateur inconnu'


def test_get_user_unknown(connection):
  with pytest.raises(Exception) as exception_info:
    model.get_user(connection, 'personne', 'motdepasse1')
  assert str(exception_info.value) == 'Utilisateur inconnu'


def test_insert_place_and_place(connection, user_id):
  place_id = model.insert_place(connection, new_place(user_id))
  place = model.place(connection, place_id)
  assert place['name'] == 'Chez Test'
  assert place['author'] == 'alice'
  assert place['average_rating'] is None
  assert place['review_count'] == 0


def test_unknown_place(connection):
  with pytest.raises(model.UnknownPlace):
    model.place(connection, 999)


def test_places_filter_by_category(connection, user_id):
  model.insert_place(connection, new_place(user_id, 'Un café', 'Café'))
  model.insert_place(connection, new_place(user_id, 'Un bar', 'Bar'))
  assert len(model.places(connection)) == 2
  filtered = model.places(connection, 'Bar')
  assert [place['name'] for place in filtered] == ['Un bar']


def test_places_average_and_sort_by_rating(connection, user_id):
  bob = model.add_user(connection, 'bob', 'motdepasse2')
  good = model.insert_place(connection, new_place(user_id, 'Bon'))
  bad = model.insert_place(connection, new_place(user_id, 'Mauvais'))
  model.insert_place(connection, new_place(user_id, 'Sans avis'))
  model.insert_review(connection, {'place_id': good, 'user_id': bob, 'rating': 5, 'comment': 'Top'})
  model.insert_review(connection, {'place_id': good, 'user_id': user_id, 'rating': 4, 'comment': 'Bien'})
  model.insert_review(connection, {'place_id': bad, 'user_id': bob, 'rating': 2, 'comment': 'Bof'})

  best = model.places(connection, None, 'best')
  assert [p['name'] for p in best] == ['Bon', 'Mauvais', 'Sans avis']
  assert best[0]['average_rating'] == 4.5
  assert best[0]['review_count'] == 2
  worst = model.places(connection, None, 'worst')
  assert [p['name'] for p in worst] == ['Mauvais', 'Bon', 'Sans avis']


def test_review_only_once_per_place(connection, user_id):
  place_id = model.insert_place(connection, new_place(user_id))
  review = {'place_id': place_id, 'user_id': user_id, 'rating': 4, 'comment': 'Bien'}
  model.insert_review(connection, review)
  with pytest.raises(Exception) as exception_info:
    model.insert_review(connection, review)
  assert str(exception_info.value) == 'Vous avez déjà donné votre avis sur ce lieu'


def test_review_rating_must_be_between_1_and_5(connection, user_id):
  place_id = model.insert_place(connection, new_place(user_id))
  with pytest.raises(Exception):
    model.insert_review(connection, {'place_id': place_id, 'user_id': user_id, 'rating': 6, 'comment': 'Trop'})


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


def test_fill_database(connection):
  model.fill_database(connection)
  assert len(model.places(connection)) == 10
