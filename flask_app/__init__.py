import os
import re
from datetime import datetime, timezone
from functools import wraps
from flask import (Flask, abort, flash, g, render_template, redirect, request,
                   send_from_directory, session, url_for)
from flask_app import model
from flask_app import geocoding
from flask_app import photos
from flask_session import Session
from flask_talisman import Talisman
from flask_wtf import CSRFProtect, FlaskForm
from flask_wtf.file import FileField
from werkzeug.datastructures import FileStorage
from wtforms import (BooleanField, IntegerField, PasswordField, StringField,
                     TextAreaField, validators)

# Taille maximale d'une requête, photo comprise (10 Mo)
MAX_UPLOAD = 10 * 1024 * 1024

app = Flask(__name__)
app.config['WTF_CSRF_ENABLED'] = True
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD
Session(app)
CSRFProtect(app)
# Tout est servi par l'application elle-même ('self') : feuille de style, polices,
# icônes, Leaflet et photos. Seules les tuiles de la carte viennent d'OpenStreetMap.
# « data: » ne sert qu'à Leaflet : quand il abandonne une tuile (zoom, déplacement),
# il la remplace par une image vide écrite directement dans son adresse.
Talisman(app, content_security_policy={
    'default-src' : '\'none\'',
    'style-src': '\'self\'',
    'font-src': '\'self\'',
    'img-src' : ['\'self\'', 'data:', 'https://tile.openstreetmap.org'],
    'script-src' : '\'self\'',
    'form-action': '\'self\'',
    'base-uri': '\'none\'',
    'frame-ancestors': '\'none\''
  },
  # Seule fonction sensible du navigateur utilisée par le site : la position,
  # pour le bouton « Me localiser » de la carte. Les autres sont désactivées.
  permissions_policy={
    'geolocation': '(self)',
    'camera': '()',
    'microphone': '()',
    'payment': '()',
    'usb': '()'
  },
  session_cookie_samesite='Strict')


def get_connection():
  # Une seule connexion à la base par requête, fermée à la fin (close_connection)
  if 'connection' not in g:
    g.connection = model.connect()
  return g.connection


@app.teardown_appcontext
def close_connection(exception):
  # Python ne ferme pas tout de suite une connexion abandonnée. Si une écriture a
  # échoué en route, sa transaction resterait ouverte et la base verrouillée pour
  # les requêtes suivantes (« database is locked ») : on ferme donc à chaque fois.
  connection = g.pop('connection', None)
  if connection is not None:
    connection.close()


@app.before_request
def forget_deleted_user():
  # Si la base a été recréée (init_db.py), les comptes ont de nouveaux identifiants :
  # une session ouverte avant ne correspond plus à aucun compte, on la ferme.
  if request.endpoint in ('static', 'photo') or 'user' not in session:
    return
  if not model.user_exists(get_connection(), session['user']['id']):
    session.clear()
    flash('Votre session a expiré : reconnectez-vous.', 'info')


def login_required(func):
  @wraps(func)
  def wrapper(*args, **kwargs):
    if 'user' not in session:
      flash('Vous devez être connecté pour accéder à cette page.', 'info')
      # « next » permet de revenir sur la page demandée une fois connecté
      next_page = request.full_path.rstrip('?') if request.method == 'GET' else None
      return redirect(url_for('login', next=next_page))
    return func(*args, **kwargs)
  return wrapper


def is_local_path(target: str) -> bool:
  # Après la connexion on ne redirige que vers une page du site : un chemin
  # qui commence par un seul « / », jamais une adresse choisie par un tiers.
  return (target.startswith('/') and not target.startswith('//')
          and '\\' not in target and ' ' not in target and target.isprintable())


def get_place_or_404(place_id: int) -> dict:
  connection = get_connection()
  try:
    return model.place(connection, place_id)
  except model.UnknownPlace:
    abort(404)


def get_owned_place(place_id: int) -> dict:
  place = get_place_or_404(place_id)
  if place['user_id'] != session['user']['id']:
    abort(403)
  return place


def photo_url(place: dict):
  if place.get('photo') is None:
    return None
  return url_for('photo', filename=place['photo'])


def marker(place: dict) -> dict:
  # Données envoyées à Leaflet (static/map.js) pour placer les marqueurs
  average = place['average_rating']
  return {
    'name': place['name'],
    'category': category_key(place['category']),
    'category_label': category_label(place['category']),
    'address': place['address'],
    'latitude': place['latitude'],
    'longitude': place['longitude'],
    # Note déjà mise en forme (« 4.5 »), pour afficher exactement la même que dans les listes
    'rating': None if average is None else '%.1f' % average,
    'review_count': place['review_count'],
    'photo': photo_url(place),
    'url': url_for('place', place_id=place['id'])
  }


def get_category():
  category = request.args.get('category')
  return category if category in model.CATEGORIES else None


def get_search():
  search = request.args.get('q', '').strip()
  return search[:100] if search != '' else None


# ---------- Affichage (valeurs et filtres communs aux templates) ----------

@app.context_processor
def template_values():
  return {
    'categories': model.CATEGORIES,
    'category_plurals': model.CATEGORY_PLURALS,
    'max_upload': MAX_UPLOAD
  }


@app.template_filter('category_key')
def category_key(category: str) -> str:
  # Clé connue, utilisable dans une classe CSS (« cat-cafe ») ou un nom d'icône
  return category if category in model.CATEGORIES else 'autre'


@app.template_filter('category_label')
def category_label(category: str) -> str:
  return model.CATEGORIES[category_key(category)]


MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
          'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']


@app.template_filter('date_fr')
def date_fr(value: str) -> str:
  # SQLite enregistre les dates en UTC : « 2025-10-12 08:30:00 » devient « 12 oct. 2025 »
  date = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
  date = date.replace(tzinfo=timezone.utc).astimezone()
  return f'{date.day} {MONTHS[date.month - 1]} {date.year}'


@app.template_filter('initials')
def initials(username: str) -> str:
  # Pastille du compte : « sara.beldi » donne « SB », « alice » donne « AL »
  parts = [part for part in re.split('[._-]+', username) if part != '']
  if len(parts) >= 2:
    return (parts[0][0] + parts[1][0]).upper()
  return username[:2].upper()


# ---------- Consultation (visiteurs et connectés) ----------

@app.route('/', methods=['GET'])
def home():
  connection = get_connection()
  best_places = model.places(connection, None, 'best')[:4]
  return render_template('home.html', best_places=best_places)


@app.route('/explore', methods=['GET'])
def explore():
  category = get_category()
  search = get_search()
  sort = request.args.get('sort', 'best')
  if sort not in model.SORTS:
    sort = 'best'
  connection = get_connection()
  places = model.places(connection, category, sort, search)
  return render_template('explore.html',
                         places=places,
                         sorts=model.SORTS,
                         category=category,
                         sort=sort,
                         search=search)


@app.route('/map', methods=['GET'])
def places_map():
  category = get_category()
  search = get_search()
  connection = get_connection()
  places = model.places(connection, category, 'name', search)
  return render_template('map.html',
                         markers=[marker(place) for place in places],
                         category=category,
                         search=search)


@app.route('/photos/<filename>', methods=['GET'])
def photo(filename: str):
  # send_from_directory refuse tout chemin qui sortirait du dossier des photos
  return send_from_directory(photos.folder(), filename)


@app.route('/credits', methods=['GET'])
def credits():
  return render_template('credits.html')


REQUIRED = 'Ce champ est obligatoire.'


def max_length(size: int):
  return validators.Length(max=size, message=f'{size} caractères maximum.')


def strip(value):
  return value.strip() if isinstance(value, str) else value


class ReviewForm(FlaskForm):
  rating = IntegerField('rating', validators=[
    validators.InputRequired('Choisissez une note entre 1 et 5.'),
    validators.NumberRange(min=1, max=5, message='Choisissez une note entre 1 et 5.')])
  comment = TextAreaField('comment', filters=[strip], validators=[
    validators.DataRequired(REQUIRED), max_length(500)])


@app.route('/place/<int:place_id>', methods=['GET', 'POST'])
def place(place_id: int):
  place = get_place_or_404(place_id)
  connection = get_connection()
  reviews = []
  user_review = None
  form = None
  if 'user' in session:
    user_id = session['user']['id']
    user_review = model.user_review(connection, place_id, user_id)
    if user_review is not None and request.method == 'POST':
      flash('Vous avez déjà donné votre avis sur ce lieu', 'error')
    if user_review is None:
      form = ReviewForm()
      if form.validate_on_submit():
        try:
          model.insert_review(connection, {
            'place_id': place_id,
            'user_id': user_id,
            'rating': form.rating.data,
            'comment': form.comment.data
          })
          flash('Votre avis a été enregistré !', 'success')
          return redirect(url_for('place', place_id=place_id, _anchor='avis'))
        except Exception as exception:
          flash(str(exception), 'error')
    # Les commentaires ne sont lus et envoyés qu'aux utilisateurs connectés
    reviews = model.place_reviews(connection, place_id)
  elif request.method == 'POST':
    return redirect(url_for('login', next=url_for('place', place_id=place_id)))
  return render_template('place.html',
                         place=place,
                         reviews=reviews,
                         user_review=user_review,
                         form=form,
                         markers=[marker(place)])


# ---------- Gestion des adresses (connectés) ----------

class PlaceForm(FlaskForm):
  name = StringField('name', filters=[strip], validators=[
    validators.DataRequired(REQUIRED), max_length(100)])
  address = StringField('address', filters=[strip], validators=[
    validators.DataRequired(REQUIRED), max_length(255)])
  category = StringField('category', validators=[
    validators.AnyOf(list(model.CATEGORIES), message='Choisissez une catégorie.')])
  description = TextAreaField('description', filters=[strip], validators=[
    validators.DataRequired(REQUIRED), max_length(1000)])
  photo = FileField('photo')
  remove_photo = BooleanField('remove_photo')


def uploaded_photo(form: PlaceForm):
  # Renvoie l'image envoyée avec le formulaire, ou None si aucun fichier n'a été choisi
  file = form.photo.data
  if not isinstance(file, FileStorage):
    return None
  return photos.read(file.stream)


@app.route('/place/create', methods=['GET', 'POST'])
@login_required
def place_create():
  form = PlaceForm()
  if form.validate_on_submit():
    try:
      image = uploaded_photo(form)
      latitude, longitude = geocoding.geocode(form.address.data)
    except photos.PhotoError as exception:
      form.photo.errors.append(str(exception))
    except geocoding.GeocodingError as exception:
      form.address.errors.append(str(exception))
    else:
      connection = get_connection()
      place_id = model.insert_place(connection, {
        'id': None,
        'user_id': session['user']['id'],
        'name': form.name.data,
        'address': form.address.data,
        'category': form.category.data,
        'description': form.description.data,
        'latitude': latitude,
        'longitude': longitude,
        'photo': photos.save(image) if image is not None else None
      })
      flash("L'adresse a été ajoutée !", 'success')
      return redirect(url_for('place', place_id=place_id))
  return render_template('place_edit.html', form=form, place=None)


@app.route('/place/<int:place_id>/edit', methods=['GET', 'POST'])
@login_required
def place_edit(place_id: int):
  place = get_owned_place(place_id)
  form = PlaceForm(data=place)
  if form.validate_on_submit():
    latitude = place['latitude']
    longitude = place['longitude']
    try:
      image = uploaded_photo(form)
      if form.address.data != place['address']:
        latitude, longitude = geocoding.geocode(form.address.data)
    except photos.PhotoError as exception:
      form.photo.errors.append(str(exception))
    except geocoding.GeocodingError as exception:
      form.address.errors.append(str(exception))
    else:
      # Nouvelle photo, photo retirée, ou photo actuelle conservée
      photo = place['photo']
      if image is not None:
        photo = photos.save(image)
      elif form.remove_photo.data:
        photo = None
      connection = get_connection()
      model.update_place(connection, {
        'id': place_id,
        'user_id': session['user']['id'],
        'name': form.name.data,
        'address': form.address.data,
        'category': form.category.data,
        'description': form.description.data,
        'latitude': latitude,
        'longitude': longitude,
        'photo': photo
      })
      if photo != place['photo']:
        photos.delete(place['photo'])
      flash("L'adresse a été modifiée !", 'success')
      return redirect(url_for('place', place_id=place_id))
  return render_template('place_edit.html', form=form, place=place)


@app.route('/place/<int:place_id>/delete', methods=['GET', 'POST'])
@login_required
def place_delete(place_id: int):
  place = get_owned_place(place_id)
  if request.method == 'POST':
    connection = get_connection()
    model.delete_place(connection, place_id, session['user']['id'])
    photos.delete(place['photo'])
    flash("L'adresse a été supprimée !", 'success')
    return redirect(url_for('my_places'))
  return render_template('place_delete.html', place=place)


@app.route('/my-places', methods=['GET'])
@login_required
def my_places():
  connection = get_connection()
  places = model.places(connection, None, 'recent', None, session['user']['id'])
  return render_template('my_places.html', places=places)


# ---------- Comptes ----------

class RegisterForm(FlaskForm):
  username = StringField('username', validators=[
    validators.DataRequired(REQUIRED),
    validators.Length(min=3, max=32, message='Entre 3 et 32 caractères.'),
    validators.Regexp(r'^[A-Za-z0-9_.-]+$',
      message='Lettres, chiffres, points, tirets et underscores uniquement.')])
  password = PasswordField('password', validators=[
    validators.DataRequired(REQUIRED),
    validators.Length(min=8, max=128, message='Entre 8 et 128 caractères.')])
  confirm = PasswordField('confirm', validators=[
    validators.EqualTo('password', message='Les mots de passe ne correspondent pas.')])


@app.route('/register', methods=['GET', 'POST'])
def register():
  form = RegisterForm()
  if form.validate_on_submit():
    try:
      connection = get_connection()
      model.add_user(connection, form.username.data, form.password.data)
      flash('Votre compte a été créé, vous pouvez vous connecter.', 'success')
      return redirect(url_for('login'))
    except Exception as exception:
      form.username.errors.append(str(exception))
  return render_template('register.html', form=form)


class LoginForm(FlaskForm):
  username = StringField('username', validators=[validators.DataRequired(REQUIRED)])
  password = PasswordField('password', validators=[validators.DataRequired(REQUIRED)])


@app.route('/login', methods=['GET', 'POST'])
def login():
  form = LoginForm()
  if form.validate_on_submit():
    try:
      connection = get_connection()
      user = model.get_user(connection, form.username.data, form.password.data)
    except Exception:
      flash("Nom d'utilisateur ou mot de passe incorrect.", 'error')
    else:
      # Nouvel identifiant de session à la connexion (contre la fixation de session)
      app.session_interface.regenerate(session)
      session['user'] = user
      flash('Vous êtes bien connecté !', 'success')
      next_page = request.args.get('next', '')
      if is_local_path(next_page):
        return redirect(next_page)
      return redirect(url_for('explore'))
  return render_template('login.html', form=form)


@app.route('/logout', methods=['POST'])
def logout():
  session.clear()
  flash('Vous êtes déconnecté !', 'success')
  return redirect(url_for('home'))


# ---------- Pages d'erreur ----------

ERRORS = {
  400: ('Formulaire expiré',
        'La page est restée ouverte trop longtemps ou le formulaire est incomplet. '
        'Revenez en arrière, rechargez la page puis réessayez.'),
  403: ('Accès refusé',
        "Cette adresse a été ajoutée par quelqu'un d'autre : "
        'vous ne pouvez ni la modifier ni la supprimer.'),
  404: ('Page introuvable',
        "Cette page n'existe pas, ou l'adresse a été supprimée."),
  405: ('Action impossible',
        "Cette page ne s'utilise pas de cette façon."),
  413: ('Photo trop lourde',
        'La photo ne doit pas dépasser 10 Mo. Choisissez une image plus légère.'),
  # Erreur imprévue : le détail reste dans le journal du serveur, jamais dans la page
  500: ('Erreur du serveur',
        'Un problème est survenu de notre côté. Réessayez dans un instant.')
}


def error_page(error):
  title, message = ERRORS[error.code]
  return render_template('error.html', code=error.code,
                         title=title, message=message), error.code


for code in ERRORS:
  app.register_error_handler(code, error_page)
