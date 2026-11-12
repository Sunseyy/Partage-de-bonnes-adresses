import gc
import html
import io
import json
import re
import pytest
from PIL import Image
from flask_app import app, model, geocoding, date_fr, initials, is_local_path

HTTPS = 'https://localhost'
MUCEM_ADDRESS = '7 Promenade Robert Laffont, 13002 Marseille'


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


def page(response):
  return response.get_data(as_text=True)


def login(client, username='alice'):
  return login_with(client, username, f'{username}-2026')


def login_with(client, username, password, url='/login'):
  return post(client, url, {'username': username, 'password': password})


def place_id_by_name(name):
  for place in model.places(model.connect()):
    if place['name'] == name:
      return place['id']


def place_by_name(name):
  return model.place(model.connect(), place_id_by_name(name))


def count_places():
  return len(model.places(model.connect()))


def image_file(format='PNG', size=(40, 30)):
  # Une vraie petite image, fabriquée en mémoire
  file = io.BytesIO()
  Image.new('RGB', size, 'tomato').save(file, format)
  file.seek(0)
  return file


def markers(response):
  # Les marqueurs de la carte sont écrits en JSON dans l'attribut data-places
  attribute = re.search(r"data-places='([^']*)'", page(response)).group(1)
  return json.loads(html.unescape(attribute))


# ---------- Visiteurs ----------

def test_home_shows_the_best_places(client):
  response = get(client, '/')
  assert response.status_code == 200
  assert 'Calanque de Sormiou' in page(response)
  assert 'MuCEM' in page(response)
  # Seules les quatre adresses les mieux notées sont mises en avant
  assert 'Plage des Catalans' not in page(response)


def test_visitor_can_browse_places_and_see_averages(client):
  response = get(client, '/explore')
  assert response.status_code == 200
  for place in model.places(model.connect()):
    assert html.escape(place['name']) in page(response)
  assert '<strong>4.5</strong>' in page(response)
  assert '(2 avis)' in page(response)
  assert "Pas encore d'avis" in page(response)


def test_visitor_filter_and_sort(client):
  filtered = page(get(client, '/explore?category=loisirs'))
  assert 'MuCEM' in filtered and 'Vieux-Port' not in filtered
  best = page(get(client, '/explore?sort=best'))
  assert best.index('Calanque de Sormiou') < best.index('Plage des Catalans')
  worst = page(get(client, '/explore?sort=worst'))
  assert worst.index('Plage des Catalans') < worst.index('Calanque de Sormiou')
  by_name = page(get(client, '/explore?sort=name'))
  assert by_name.index('Bar du Cours Julien') < by_name.index('MuCEM') < by_name.index('Vieux-Port')


def test_places_are_sorted_by_average_by_default(client):
  default = page(get(client, '/explore'))
  assert default.index('Calanque de Sormiou') < default.index('Plage des Catalans')


def test_invalid_filter_is_ignored(client):
  response = get(client, "/explore?category=';DROP TABLE places;--&sort=nimporte")
  assert response.status_code == 200
  assert 'MuCEM' in page(response)
  assert count_places() == 11


def test_search_ignores_case_and_accents(client):
  found = page(get(client, '/explore?q=CAFE'))
  assert 'Café de la Plaine' in found and 'MuCEM' not in found
  found = page(get(client, '/explore?q=musee+mer'))
  assert 'MuCEM' in found and 'Vieux-Port' not in found
  assert 'Aucune adresse ne correspond' in page(get(client, '/explore?q=zzzz'))


def test_visitor_cannot_read_comments(client):
  response = get(client, f"/place/{place_id_by_name('MuCEM')}")
  assert '4.5 <span>/ 5</span>' in page(response)
  assert 'Expositions intéressantes' not in page(response)
  assert 'Connectez-vous' in page(response)


def test_visitor_cannot_post_a_review(client):
  place_id = place_id_by_name('MuCEM')
  response = post(client, f'/place/{place_id}', {'rating': '1', 'comment': 'Anonyme'})
  assert response.status_code == 302
  assert '/login' in response.headers['Location']
  assert model.place(model.connect(), place_id)['review_count'] == 2


def test_map_page_contains_markers(client):
  response = get(client, '/map')
  assert 'data-places' in page(response)
  places = {marker['name']: marker for marker in markers(response)}
  assert len(places) == 11
  mucem = places['MuCEM']
  assert (mucem['latitude'], mucem['longitude']) == (43.2967, 5.3611)
  assert mucem['category'] == 'loisirs'
  assert mucem['rating'] == '4.5'
  assert mucem['url'] == f"/place/{place_id_by_name('MuCEM')}"
  assert places['Boulangerie Saint-Ferréol (exemple)']['rating'] is None
  assert places['Boulangerie Saint-Ferréol (exemple)']['photo'] is None


def test_map_can_be_filtered(client):
  names = [marker['name'] for marker in markers(get(client, '/map?category=cafe'))]
  assert names == ['Bar du Cours Julien (exemple)', 'Café de la Plaine (exemple)']
  assert markers(get(client, '/map?q=introuvable')) == []


def test_unknown_place_is_404(client):
  response = get(client, '/place/9999')
  assert response.status_code == 404
  assert 'Page introuvable' in page(response)


def test_example_photo_is_served(client):
  response = get(client, '/photos/mucem.jpg')
  assert response.status_code == 200
  assert response.mimetype == 'image/jpeg'
  assert get(client, '/photos/inconnue.jpg').status_code == 404
  # Impossible de sortir du dossier des photos
  assert get(client, '/photos/..%2F..%2Finit_db.py').status_code == 404
  assert get(client, '/photos/../test.sqlite').status_code == 404


def test_credits_page(client):
  response = get(client, '/credits')
  assert response.status_code == 200
  assert 'OpenStreetMap' in page(response)
  assert 'CC BY-SA' in page(response)


def test_csp_allows_only_self_scripts(client):
  csp = get(client, '/').headers['Content-Security-Policy']
  directives = [directive.strip() for directive in csp.split(';')]
  assert "default-src 'none'" in directives
  assert "script-src 'self'" in directives
  assert "style-src 'self'" in directives
  # Images du site, tuiles de la carte, et image vide de Leaflet (« data: »)
  assert "img-src 'self' data: https://tile.openstreetmap.org" in directives
  assert 'unsafe' not in csp


def test_permissions_policy(client):
  # Seule la position est permise (bouton « Me localiser » de la carte)
  policy = get(client, '/map').headers['Permissions-Policy']
  assert 'geolocation=(self)' in policy
  assert 'camera=()' in policy
  assert 'browsing-topics' not in policy


def test_pages_respect_the_csp(client):
  # La CSP bloque les scripts et les styles écrits dans le HTML : aucune page ne doit en contenir
  place_id = place_id_by_name('Boulangerie Saint-Ferréol (exemple)')
  urls = ['/', '/explore', '/explore?q=zzzz', '/map', '/map?category=cafe', '/credits',
          '/login', '/register', '/place/9999', f'/place/{place_id}']
  pages = [page(get(client, url)) for url in urls]
  login(client)
  urls = ['/', '/explore', '/my-places', '/place/create', f'/place/{place_id}',
          f'/place/{place_id}/edit', f'/place/{place_id}/delete']
  for url in urls:
    response = get(client, url)
    assert response.status_code == 200
    pages.append(page(response))
  for content in pages:
    assert re.search(r'<script(?![^>]*\ssrc=)', content) is None
    assert '<style' not in content
    assert re.search(r'<[^>]*\sstyle\s*=', content) is None
    assert re.search(r'<[^>]*\son[a-z]+\s*=', content) is None
    assert 'javascript:' not in content


# ---------- Comptes ----------

def test_register_then_login(client):
  response = post(client, '/register', {
    'username': 'david', 'password': 'motdepasse1', 'confirm': 'motdepasse1'})
  assert response.status_code == 302
  assert login_with(client, 'david', 'motdepasse1').status_code == 302
  assert 'david' in page(get(client, '/explore'))
  assert 'Se déconnecter' in page(get(client, '/explore'))


def test_register_refuses_invalid_accounts(client):
  short = post(client, '/register', {
    'username': 'david', 'password': 'court', 'confirm': 'court'})
  assert 'Entre 8 et 128 caractères.' in page(short)
  different = post(client, '/register', {
    'username': 'david', 'password': 'motdepasse1', 'confirm': 'motdepasse2'})
  assert 'Les mots de passe ne correspondent pas.' in page(different)
  strange = post(client, '/register', {
    'username': 'da vid<', 'password': 'motdepasse1', 'confirm': 'motdepasse1'})
  assert 'Lettres, chiffres, points, tirets et underscores uniquement.' in page(strange)
  duplicate = post(client, '/register', {
    'username': 'Alice', 'password': 'motdepasse1', 'confirm': 'motdepasse1'})
  assert 'déjà utilisé' in page(duplicate)
  # Aucun de ces comptes n'a été créé
  assert login_with(client, 'david', 'motdepasse1').status_code == 200


def test_refused_account_does_not_lock_the_database(client):
  # Un compte refusé ne doit pas laisser la base verrouillée pour la requête suivante.
  # Le ramasse-miettes est coupé pour que le résultat ne dépende pas du moment où
  # Python détruit une connexion oubliée.
  gc.disable()
  try:
    post(client, '/register', {
      'username': 'alice', 'password': 'motdepasse1', 'confirm': 'motdepasse1'})
    response = post(client, '/register', {
      'username': 'david', 'password': 'motdepasse1', 'confirm': 'motdepasse1'})
  finally:
    gc.enable()
  assert response.status_code == 302


def test_session_does_not_survive_a_new_database(client):
  # Recréer la base (init_db.py) change l'identifiant des comptes : la session ouverte
  # avant ne correspond plus à personne, elle est fermée au lieu de provoquer une erreur.
  login(client)
  connection = model.connect()
  model.create_database(connection)
  model.fill_database(connection)
  response = get(client, '/explore')
  assert 'Votre session a expiré' in page(response)
  assert 'Se déconnecter' not in page(response)
  assert get(client, '/place/create').status_code == 302


def test_login_wrong_password(client):
  response = login_with(client, 'alice', 'mauvais')
  assert 'incorrect' in page(response)
  assert 'Se déconnecter' not in page(get(client, '/explore'))


def test_login_changes_the_session_id(client):
  # Contre la fixation de session : l'identifiant de session est renouvelé à la connexion
  get(client, '/login')
  before = client.get_cookie('session').value
  login(client)
  after = client.get_cookie('session').value
  assert before != after


def test_session_cookie_is_protected(client):
  response = get(client, '/login')
  cookie = response.headers['Set-Cookie']
  assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=Strict' in cookie


def test_http_is_redirected_to_https(client):
  response = client.get('/', base_url='http://localhost')
  assert response.status_code == 302
  assert response.headers['Location'].startswith('https://')


def test_login_comes_back_to_the_requested_page(client):
  response = get(client, '/my-places')
  assert response.status_code == 302
  assert response.headers['Location'] == '/login?next=/my-places'
  response = login_with(client, 'alice', 'alice-2026', '/login?next=/my-places')
  assert response.headers['Location'] == '/my-places'


@pytest.mark.parametrize('target', [
  'https://example.org/', '//example.org/', '/\\example.org', 'javascript:alert(1)', ''])
def test_login_never_redirects_to_another_site(client, target):
  response = client.post('/login', base_url=HTTPS, query_string={'next': target},
                         data={'username': 'alice', 'password': 'alice-2026'})
  assert response.status_code == 302
  assert response.headers['Location'] == '/explore'


def test_is_local_path():
  assert is_local_path('/place/3')
  assert is_local_path('/explore?category=cafe&sort=best')
  assert not is_local_path('//example.org')
  assert not is_local_path('https://example.org')
  assert not is_local_path('/\\example.org')
  assert not is_local_path('/chemin\navec-retour')
  assert not is_local_path('')


def test_logout_requires_post(client):
  login(client)
  assert get(client, '/logout').status_code == 405
  assert 'Se déconnecter' in page(get(client, '/explore'))
  assert post(client, '/logout').status_code == 302
  assert 'Se déconnecter' not in page(get(client, '/explore'))


# ---------- Avis ----------

def test_logged_user_reads_comments(client):
  login(client)
  response = get(client, f"/place/{place_id_by_name('Plage des Catalans')}")
  assert 'Trop de monde' in page(response)


def test_one_review_per_place(client):
  login(client, 'bob')
  place_id = place_id_by_name('Vieux-Port')
  # bob a déjà noté le Vieux-Port dans les données de test : pas de formulaire d'avis
  assert 'name="rating"' not in page(get(client, f'/place/{place_id}'))
  response = post(client, f'/place/{place_id}', {'rating': '1', 'comment': 'Doublon'},
                  follow_redirects=True)
  assert 'déjà donné votre avis' in page(response)
  assert 'Doublon' not in page(response)
  assert model.place(model.connect(), place_id)['review_count'] == 2


def test_add_review(client):
  login(client, 'bob')
  place_id = place_id_by_name('Boulangerie Saint-Ferréol (exemple)')
  assert 'name="rating"' in page(get(client, f'/place/{place_id}'))
  response = post(client, f'/place/{place_id}', {'rating': '5', 'comment': 'Délicieux'},
                  follow_redirects=True)
  assert 'Votre avis a été enregistré' in page(response)
  assert '5.0 <span>/ 5</span>' in page(response)
  assert 'Délicieux' in page(response)


@pytest.mark.parametrize('review', [
  {'rating': '9', 'comment': 'Trop'},
  {'rating': '0', 'comment': 'Pas assez'},
  {'rating': 'cinq', 'comment': 'En lettres'},
  {'comment': 'Sans note'},
  {'rating': '4', 'comment': '   '},
  {'rating': '4', 'comment': 'x' * 501}])
def test_invalid_review_is_refused(client, review):
  login(client, 'bob')
  place_id = place_id_by_name('Boulangerie Saint-Ferréol (exemple)')
  response = post(client, f'/place/{place_id}', review)
  assert response.status_code == 200
  assert 'field-error' in page(response)
  assert model.place(model.connect(), place_id)['review_count'] == 0


# ---------- Adresses ----------

def test_create_requires_login(client):
  response = get(client, '/place/create')
  assert response.status_code == 302
  assert '/login' in response.headers['Location']
  response = post(client, '/place/create', {
    'name': 'Anonyme', 'address': 'x', 'category': 'cafe', 'description': 'x'})
  assert response.status_code == 302
  assert count_places() == 11


def test_create_place(client):
  login(client)
  response = post(client, '/place/create', {
    'name': '  Nouveau lieu ', 'address': '1 rue Test, Marseille',
    'category': 'cafe', 'description': 'Super',
    # Champ « photo » laissé vide, tel que l'envoie un navigateur
    'photo': (io.BytesIO(b''), '')})
  assert response.status_code == 302
  place = place_by_name('Nouveau lieu')
  assert response.headers['Location'] == f"/place/{place['id']}"
  assert place['category'] == 'cafe'
  assert place['author'] == 'alice'
  assert place['photo'] is None
  assert (place['latitude'], place['longitude']) == (43.3, 5.4)


def test_create_place_address_not_found(client, monkeypatch):
  def not_found(address):
    raise geocoding.GeocodingError('Adresse introuvable, vérifiez la saisie.')
  monkeypatch.setattr(geocoding, 'geocode', not_found)
  login(client)
  response = post(client, '/place/create', {
    'name': 'Nouveau lieu', 'address': 'zzzz',
    'category': 'cafe', 'description': 'Super'})
  assert 'Adresse introuvable' in page(response)
  assert count_places() == 11


def test_create_place_invalid_category(client):
  login(client)
  response = post(client, '/place/create', {
    'name': 'X', 'address': 'Y', 'category': 'Inconnue', 'description': 'Z'})
  assert response.status_code == 200
  assert 'Choisissez une catégorie.' in page(response)
  assert count_places() == 11


@pytest.mark.parametrize('format', ['JPEG', 'PNG', 'WEBP'])
def test_create_place_with_photo(client, upload_folder, format):
  login(client)
  response = post(client, '/place/create', {
    'name': 'Lieu en photo', 'address': '1 rue Test, Marseille',
    'category': 'loisirs', 'description': 'Super',
    'photo': (image_file(format), 'Ma photo.xyz')})
  assert response.status_code == 302
  photo = place_by_name('Lieu en photo')['photo']
  # Le nom du fichier est choisi par le serveur et l'image réenregistrée en JPEG
  assert re.fullmatch(r'[0-9a-f]{32}\.jpg', photo)
  assert Image.open(upload_folder / photo).format == 'JPEG'
  response = get(client, f'/photos/{photo}')
  assert response.status_code == 200
  assert response.mimetype == 'image/jpeg'


def test_big_photo_is_resized(client, upload_folder):
  login(client)
  post(client, '/place/create', {
    'name': 'Grande photo', 'address': '1 rue Test, Marseille',
    'category': 'loisirs', 'description': 'Super',
    'photo': (image_file('JPEG', (3000, 1000)), 'grande.jpg')})
  photo = place_by_name('Grande photo')['photo']
  assert Image.open(upload_folder / photo).size == (1600, 533)


@pytest.mark.parametrize('content', [
  b'<script>alert(1)</script>',
  b'GIF89a' + b'\x00' * 64,
  b'\xff\xd8\xff\xe0' + b'\x00' * 64])
def test_create_place_refuses_fake_photo(client, upload_folder, content):
  login(client)
  response = post(client, '/place/create', {
    'name': 'Fausse photo', 'address': '1 rue Test, Marseille',
    'category': 'loisirs', 'description': 'Super',
    'photo': (io.BytesIO(content), 'photo.jpg')})
  assert response.status_code == 200
  assert 'pas une image valide' in page(response)
  assert count_places() == 11
  # Rien d'autre que les dix photos d'exemple dans le dossier
  assert len(list(upload_folder.iterdir())) == 10


def test_upload_too_large_is_refused(client):
  login(client)
  response = post(client, '/place/create', {
    'name': 'Trop lourd', 'address': '1 rue Test, Marseille',
    'category': 'loisirs', 'description': 'Super',
    'photo': (io.BytesIO(b'0' * (10 * 1024 * 1024 + 1)), 'lourde.jpg')})
  assert response.status_code == 413
  assert 'Photo trop lourde' in page(response)
  assert count_places() == 11


def test_owner_sees_the_edit_links(client):
  place_id = place_id_by_name('MuCEM')
  login(client, 'bob')
  assert f'/place/{place_id}/edit' in page(get(client, f'/place/{place_id}'))
  assert f'/place/{place_id}/delete' in page(get(client, f'/place/{place_id}'))
  post(client, '/logout')
  login(client, 'alice')
  assert f'/place/{place_id}/edit' not in page(get(client, f'/place/{place_id}'))
  assert f'/place/{place_id}/delete' not in page(get(client, f'/place/{place_id}'))


def test_my_places_lists_only_own_places(client):
  assert get(client, '/my-places').status_code == 302
  login(client, 'bob')
  response = get(client, '/my-places')
  assert response.status_code == 200
  assert 'MuCEM' in page(response) and 'Palais Longchamp' in page(response)
  assert 'Vieux-Port' not in page(response)


def test_owner_can_edit_and_delete(client, upload_folder):
  login(client, 'bob')
  place_id = place_id_by_name('MuCEM')
  assert 'Musée des civilisations' in page(get(client, f'/place/{place_id}/edit'))
  response = post(client, f'/place/{place_id}/edit', {
    'name': 'MuCEM modifié', 'address': MUCEM_ADDRESS,
    'category': 'autre', 'description': 'Nouvelle description'})
  assert response.status_code == 302
  place = model.place(model.connect(), place_id)
  assert (place['name'], place['category']) == ('MuCEM modifié', 'autre')
  # Adresse inchangée : les coordonnées et la photo sont conservées
  assert (place['latitude'], place['longitude']) == (43.2967, 5.3611)
  assert place['photo'] == 'mucem.jpg'

  assert get(client, f'/place/{place_id}/delete').status_code == 200
  assert model.place(model.connect(), place_id)['name'] == 'MuCEM modifié'
  response = post(client, f'/place/{place_id}/delete')
  assert response.status_code == 302
  assert response.headers['Location'] == '/my-places'
  assert get(client, f'/place/{place_id}').status_code == 404
  assert not (upload_folder / 'mucem.jpg').exists()


def test_new_address_is_located_again(client):
  login(client, 'bob')
  place_id = place_id_by_name('MuCEM')
  post(client, f'/place/{place_id}/edit', {
    'name': 'MuCEM', 'address': '1 rue Test, Marseille',
    'category': 'loisirs', 'description': 'Déménagé'})
  place = model.place(model.connect(), place_id)
  assert (place['latitude'], place['longitude']) == (43.3, 5.4)


def test_owner_can_change_and_remove_the_photo(client, upload_folder):
  login(client, 'bob')
  place_id = place_id_by_name('MuCEM')
  form = {'name': 'MuCEM', 'address': MUCEM_ADDRESS,
          'category': 'loisirs', 'description': 'Musée'}
  # Nouvelle photo : l'ancienne est supprimée du dossier
  post(client, f'/place/{place_id}/edit', dict(form, photo=(image_file('JPEG'), 'nouvelle.jpg')))
  photo = model.place(model.connect(), place_id)['photo']
  assert photo not in (None, 'mucem.jpg')
  assert (upload_folder / photo).is_file()
  assert not (upload_folder / 'mucem.jpg').exists()
  # Case « Retirer la photo » cochée
  post(client, f'/place/{place_id}/edit', dict(form, remove_photo='y'))
  assert model.place(model.connect(), place_id)['photo'] is None
  assert not (upload_folder / photo).exists()


def test_other_user_cannot_edit_or_delete(client, upload_folder):
  login(client, 'alice')
  place_id = place_id_by_name('MuCEM')
  response = get(client, f'/place/{place_id}/edit')
  assert response.status_code == 403
  assert 'Accès refusé' in page(response)
  assert post(client, f'/place/{place_id}/edit', {
    'name': 'Piraté', 'address': 'x', 'category': 'cafe', 'description': 'x',
    'remove_photo': 'y'}).status_code == 403
  assert get(client, f'/place/{place_id}/delete').status_code == 403
  assert post(client, f'/place/{place_id}/delete').status_code == 403
  place = model.place(model.connect(), place_id)
  assert (place['name'], place['photo']) == ('MuCEM', 'mucem.jpg')
  assert (upload_folder / 'mucem.jpg').is_file()


# ---------- Sécurité ----------

def test_csrf_is_enforced(client):
  app.config['WTF_CSRF_ENABLED'] = True
  response = login_with(client, 'alice', 'alice-2026')
  assert response.status_code == 400
  assert 'Formulaire expiré' in page(response)
  assert 'Se déconnecter' not in page(get(client, '/explore'))


def test_xss_is_escaped(client):
  login(client)
  post(client, '/place/create', {
    'name': '<script>alert(1)</script>', 'address': "x' onmouseover='alert(1)",
    'category': 'cafe', 'description': '<img src=x onerror=alert(1)>'})
  place_id = place_id_by_name('<script>alert(1)</script>')
  post(client, f'/place/{place_id}', {'rating': '3', 'comment': '<b>gras</b>'})
  for url in ['/explore', '/my-places', f'/place/{place_id}', f'/place/{place_id}/edit',
              f'/place/{place_id}/delete', '/explore?q=<script>alert(1)</script>']:
    content = page(get(client, url))
    assert '&lt;script&gt;' in content
    assert '<script>alert(1)</script>' not in content
    assert '<img src=x' not in content
    assert '<b>gras</b>' not in content
  # Sur la carte, les données sont dans un attribut : ni balise ni apostrophe ne doivent en sortir
  response = get(client, '/map')
  assert '<script>alert(1)</script>' not in page(response)
  names = [marker['name'] for marker in markers(response)]
  assert '<script>alert(1)</script>' in names
  addresses = [marker['address'] for marker in markers(response)]
  assert "x' onmouseover='alert(1)" in addresses


def test_unexpected_error_does_not_show_its_details(client, monkeypatch):
  def broken(*args, **kwargs):
    raise RuntimeError('detail interne')
  monkeypatch.setattr(model, 'places', broken)
  # Pendant les tests Flask laisse remonter les exceptions : on rétablit le comportement réel
  monkeypatch.setitem(app.config, 'PROPAGATE_EXCEPTIONS', False)
  response = get(client, '/explore')
  assert response.status_code == 500
  assert 'Erreur du serveur' in page(response)
  assert 'detail interne' not in page(response)


# ---------- Mise en forme ----------

def test_initials():
  assert initials('sara.beldi') == 'SB'
  assert initials('jean-paul_martin') == 'JP'
  assert initials('alice') == 'AL'
  assert initials('x') == 'X'


def test_date_fr():
  assert date_fr('2025-10-12 12:00:00') == '12 oct. 2025'
  assert date_fr('2026-03-01 12:00:00') == '1 mars 2026'
