import pytest
from flask_app import app, model, geocoding

HTTPS = 'https://localhost'


@pytest.fixture
def client(tmp_path, monkeypatch):
  monkeypatch.setenv('DATABASE', str(tmp_path / 'test.sqlite'))
  app.config['SECRET_KEY'] = 'cle-de-test'
  app.config['WTF_CSRF_ENABLED'] = False
  app.config['TESTING'] = True
  connection = model.connect()
  model.create_database(connection)
  model.fill_database(connection)
  monkeypatch.setattr(geocoding, 'geocode', lambda address: (43.3, 5.4))
  return app.test_client()


def get(client, url, **kwargs):
  return client.get(url, base_url=HTTPS, **kwargs)


def post(client, url, data=None, **kwargs):
  return client.post(url, data=data or {}, base_url=HTTPS, **kwargs)


def login(client, username='alice'):
  return post(client, '/login', {'username': username, 'password': f'{username}-2026'})


def place_id_by_name(name):
  for place in model.places(model.connect()):
    if place['name'] == name:
      return place['id']


# ---------- Visiteurs ----------

def test_visitor_can_browse_places_and_see_averages(client):
  response = get(client, '/')
  page = response.get_data(as_text=True)
  assert response.status_code == 200
  assert 'MuCEM' in page
  assert '4.5 / 5' in page


def test_visitor_filter_and_sort(client):
  page = get(client, '/?category=Musée').get_data(as_text=True)
  assert 'MuCEM' in page and 'Vieux-Port' not in page
  page = get(client, '/?sort=best').get_data(as_text=True)
  assert page.index('Calanque de Sormiou') < page.index('Plage des Catalans')


def test_invalid_filter_is_ignored(client):
  response = get(client, "/?category=';DROP TABLE places;--&sort=nimporte")
  assert response.status_code == 200
  assert 'MuCEM' in response.get_data(as_text=True)


def test_visitor_cannot_read_comments(client):
  page = get(client, f"/place/{place_id_by_name('MuCEM')}").get_data(as_text=True)
  assert '4.5 / 5' in page
  assert 'Expositions intéressantes' not in page
  assert 'Connectez-vous' in page


def test_map_page_contains_markers(client):
  page = get(client, '/map').get_data(as_text=True)
  assert 'data-places' in page
  assert 'MuCEM' in page


def test_unknown_place_is_404(client):
  assert get(client, '/place/9999').status_code == 404


def test_csp_allows_only_self_scripts(client):
  csp = get(client, '/').headers['Content-Security-Policy']
  assert "script-src 'self'" in csp
  assert 'https://tile.openstreetmap.org' in csp


# ---------- Comptes ----------

def test_register_then_login(client):
  response = post(client, '/register', {
    'username': 'david', 'password': 'motdepasse1', 'confirm': 'motdepasse1'})
  assert response.status_code == 302
  assert login_with(client, 'david', 'motdepasse1').status_code == 302
  assert 'david' in get(client, '/').get_data(as_text=True)


def login_with(client, username, password):
  return post(client, '/login', {'username': username, 'password': password})


def test_register_refuses_short_password_and_duplicates(client):
  page = post(client, '/register', {
    'username': 'david', 'password': 'court', 'confirm': 'court'}).get_data(as_text=True)
  assert 'Entre 8 et 128 caractères.' in page
  assert len(model.places(model.connect())) == 10
  page = post(client, '/register', {
    'username': 'Alice', 'password': 'motdepasse1', 'confirm': 'motdepasse1'}).get_data(as_text=True)
  assert "déjà utilisé" in page


def test_login_wrong_password(client):
  page = login_with(client, 'alice', 'mauvais').get_data(as_text=True)
  assert 'incorrect' in page
  assert 'Déconnexion' not in page


def test_logout_requires_post(client):
  login(client)
  assert get(client, '/logout').status_code == 405
  assert post(client, '/logout').status_code == 302
  assert 'Déconnexion' not in get(client, '/').get_data(as_text=True)


# ---------- Utilisateur connecté ----------

def test_logged_user_reads_comments(client):
  login(client)
  page = get(client, f"/place/{place_id_by_name('Plage des Catalans')}").get_data(as_text=True)
  assert 'Trop de monde' in page


def test_one_review_per_place(client):
  login(client, 'bob')
  place_id = place_id_by_name('Vieux-Port')
  # bob a déjà noté le Vieux-Port dans les données de test
  response = post(client, f'/place/{place_id}', {'rating': '1', 'comment': 'Doublon'},
                  follow_redirects=True)
  assert 'déjà donné votre avis' in response.get_data(as_text=True)
  assert 'Doublon' not in response.get_data(as_text=True)


def test_add_review(client):
  login(client, 'bob')
  place_id = place_id_by_name('Boulangerie Saint-Ferréol (exemple)')
  response = post(client, f'/place/{place_id}', {'rating': '5', 'comment': 'Délicieux'},
                  follow_redirects=True)
  page = response.get_data(as_text=True)
  assert 'Votre avis a été enregistré' in page
  assert '5.0 / 5' in page


def test_review_rating_out_of_range_is_refused(client):
  login(client, 'bob')
  place_id = place_id_by_name('Boulangerie Saint-Ferréol (exemple)')
  post(client, f'/place/{place_id}', {'rating': '9', 'comment': 'Trop'})
  assert model.place(model.connect(), place_id)['review_count'] == 0


def test_create_requires_login(client):
  response = get(client, '/place/create')
  assert response.status_code == 302
  assert '/login' in response.headers['Location']


def test_create_place(client):
  login(client)
  response = post(client, '/place/create', {
    'name': 'Nouveau lieu', 'address': '1 rue Test, Marseille',
    'category': 'Bar', 'description': 'Super'})
  assert response.status_code == 302
  place = model.places(model.connect(), 'Bar', 'name')[-1]
  assert place['name'] == 'Nouveau lieu'
  assert (place['latitude'], place['longitude']) == (43.3, 5.4)


def test_create_place_address_not_found(client, monkeypatch):
  def not_found(address):
    raise geocoding.GeocodingError('Adresse introuvable, vérifiez la saisie.')
  monkeypatch.setattr(geocoding, 'geocode', not_found)
  login(client)
  page = post(client, '/place/create', {
    'name': 'Nouveau lieu', 'address': 'zzzz',
    'category': 'Bar', 'description': 'Super'}).get_data(as_text=True)
  assert 'Adresse introuvable' in page


def test_create_place_invalid_category(client):
  login(client)
  response = post(client, '/place/create', {
    'name': 'X', 'address': 'Y', 'category': 'Inconnue', 'description': 'Z'})
  assert response.status_code == 200
  assert len(model.places(model.connect())) == 10


def test_owner_can_edit_and_delete(client):
  login(client, 'bob')
  place_id = place_id_by_name('MuCEM')
  response = post(client, f'/place/{place_id}/edit', {
    'name': 'MuCEM modifié', 'address': '7 Promenade Robert Laffont, 13002 Marseille',
    'category': 'Musée', 'description': 'Nouvelle description'})
  assert response.status_code == 302
  assert model.place(model.connect(), place_id)['name'] == 'MuCEM modifié'
  assert get(client, f'/place/{place_id}/delete').status_code == 200
  assert post(client, f'/place/{place_id}/delete').status_code == 302
  assert get(client, f'/place/{place_id}').status_code == 404


def test_other_user_cannot_edit_or_delete(client):
  login(client, 'alice')
  place_id = place_id_by_name('MuCEM')
  assert get(client, f'/place/{place_id}/edit').status_code == 403
  assert post(client, f'/place/{place_id}/edit', {
    'name': 'Piraté', 'address': 'x', 'category': 'Bar', 'description': 'x'}).status_code == 403
  assert post(client, f'/place/{place_id}/delete').status_code == 403
  assert model.place(model.connect(), place_id)['name'] == 'MuCEM'


def test_csrf_is_enforced(client):
  app.config['WTF_CSRF_ENABLED'] = True
  login_response = post(client, '/login', {'username': 'alice', 'password': 'alice-2026'})
  assert login_response.status_code == 400


def test_xss_is_escaped(client):
  login(client)
  post(client, '/place/create', {
    'name': '<script>alert(1)</script>', 'address': 'x',
    'category': 'Bar', 'description': '<img src=x onerror=alert(1)>'})
  page = get(client, '/').get_data(as_text=True)
  assert '<script>alert(1)</script>' not in page
  assert '&lt;script&gt;' in page
