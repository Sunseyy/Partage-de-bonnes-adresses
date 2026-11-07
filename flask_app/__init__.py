import os
from functools import wraps
from flask import Flask, abort, flash, render_template, redirect, request, session, url_for
from flask_app import model
from flask_app import geocoding
from flask_session import Session
from flask_talisman import Talisman
from flask_wtf import CSRFProtect, FlaskForm
from wtforms import StringField, SelectField, PasswordField, TextAreaField, validators

app = Flask(__name__)
app.config['WTF_CSRF_ENABLED'] = True
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SESSION_COOKIE_SECURE'] = True
Session(app)
CSRFProtect(app)
# Leaflet est servi depuis /static (donc 'self'), les tuiles viennent d'OpenStreetMap
Talisman(app, content_security_policy={
    'default-src' : '\'none\'',
    'style-src': [ 'https://cdn.jsdelivr.net/npm/bootstrap@5.2.0/dist/css/bootstrap.min.css',
                   '\'self\'' ],
    'img-src' : ['\'self\'', 'https://tile.openstreetmap.org'],
    'script-src' : '\'self\''
  },
  session_cookie_samesite='Strict')


def login_required(func):
  @wraps(func)
  def wrapper(*args, **kwargs):
    if 'user' not in session:
      flash('Vous devez être connecté pour accéder à cette page.')
      return redirect(url_for('login'))
    return func(*args, **kwargs)
  return wrapper


def get_place_or_404(place_id: int) -> dict:
  connection = model.connect()
  try:
    return model.place(connection, place_id)
  except model.UnknownPlace:
    abort(404)


def get_owned_place(place_id: int) -> dict:
  place = get_place_or_404(place_id)
  if place['user_id'] != session['user']['id']:
    abort(403)
  return place


def marker(place: dict) -> dict:
  # Données envoyées à Leaflet (static/map.js) pour placer les marqueurs
  return {
    'name': place['name'],
    'category': place['category'],
    'latitude': place['latitude'],
    'longitude': place['longitude'],
    'average_rating': place['average_rating'],
    'url': url_for('place', place_id=place['id'])
  }


def get_category():
  category = request.args.get('category')
  return category if category in model.CATEGORIES else None


# ---------- Consultation (visiteurs et connectés) ----------

@app.route('/', methods=['GET'])
def home():
  category = get_category()
  sort = request.args.get('sort', 'name')
  if sort not in model.SORTS:
    sort = 'name'
  connection = model.connect()
  places = model.places(connection, category, sort)
  return render_template('places.html',
                         places=places,
                         categories=model.CATEGORIES,
                         sorts=model.SORTS,
                         category=category,
                         sort=sort)


@app.route('/map', methods=['GET'])
def places_map():
  category = get_category()
  connection = model.connect()
  places = model.places(connection, category)
  return render_template('map.html',
                         markers=[marker(place) for place in places],
                         categories=model.CATEGORIES,
                         category=category)


REQUIRED = 'Ce champ est obligatoire.'


def max_length(size: int):
  return validators.Length(max=size, message=f'{size} caractères maximum.')


class ReviewForm(FlaskForm):
  rating = SelectField('rating', coerce=int, choices=[
    (5, '5 : Excellent'), (4, '4 : Très bien'), (3, '3 : Bien'),
    (2, '2 : Moyen'), (1, '1 : Décevant')])
  comment = TextAreaField('comment', validators=[
    validators.DataRequired(REQUIRED), max_length(1000)])


@app.route('/place/<int:place_id>', methods=['GET', 'POST'])
def place(place_id: int):
  place = get_place_or_404(place_id)
  connection = model.connect()
  reviews = []
  user_review = None
  form = None
  if 'user' in session:
    user_id = session['user']['id']
    user_review = model.user_review(connection, place_id, user_id)
    if user_review is not None and request.method == 'POST':
      flash('Vous avez déjà donné votre avis sur ce lieu')
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
          flash('Votre avis a été enregistré !')
          return redirect(url_for('place', place_id=place_id))
        except Exception as exception:
          flash(str(exception))
    # Les commentaires ne sont lus et envoyés qu'aux utilisateurs connectés
    reviews = model.place_reviews(connection, place_id)
  elif request.method == 'POST':
    return redirect(url_for('login'))
  return render_template('place.html',
                         place=place,
                         reviews=reviews,
                         user_review=user_review,
                         form=form,
                         markers=[marker(place)])


# ---------- Gestion des adresses (connectés) ----------

class PlaceForm(FlaskForm):
  name = StringField('name', validators=[
    validators.DataRequired(REQUIRED), max_length(100)])
  address = StringField('address', validators=[
    validators.DataRequired(REQUIRED), max_length(255)])
  category = SelectField('category', choices=[(c, c) for c in model.CATEGORIES])
  description = TextAreaField('description', validators=[
    validators.DataRequired(REQUIRED), max_length(1000)])


@app.route('/place/create', methods=['GET', 'POST'])
@login_required
def place_create():
  form = PlaceForm()
  if form.validate_on_submit():
    try:
      latitude, longitude = geocoding.geocode(form.address.data)
    except geocoding.GeocodingError as exception:
      flash(str(exception))
    else:
      connection = model.connect()
      place_id = model.insert_place(connection, {
        'id': None,
        'user_id': session['user']['id'],
        'name': form.name.data,
        'address': form.address.data,
        'category': form.category.data,
        'description': form.description.data,
        'latitude': latitude,
        'longitude': longitude
      })
      flash("L'adresse a été ajoutée !")
      return redirect(url_for('place', place_id=place_id))
  return render_template('place_edit.html', form=form, title='Ajouter une adresse')


@app.route('/place/<int:place_id>/edit', methods=['GET', 'POST'])
@login_required
def place_edit(place_id: int):
  place = get_owned_place(place_id)
  form = PlaceForm(data=place)
  if form.validate_on_submit():
    latitude = place['latitude']
    longitude = place['longitude']
    try:
      if form.address.data != place['address']:
        latitude, longitude = geocoding.geocode(form.address.data)
    except geocoding.GeocodingError as exception:
      flash(str(exception))
    else:
      connection = model.connect()
      model.update_place(connection, {
        'id': place_id,
        'user_id': session['user']['id'],
        'name': form.name.data,
        'address': form.address.data,
        'category': form.category.data,
        'description': form.description.data,
        'latitude': latitude,
        'longitude': longitude
      })
      flash("L'adresse a été modifiée !")
      return redirect(url_for('place', place_id=place_id))
  return render_template('place_edit.html', form=form, title="Modifier l'adresse")


@app.route('/place/<int:place_id>/delete', methods=['GET', 'POST'])
@login_required
def place_delete(place_id: int):
  place = get_owned_place(place_id)
  if request.method == 'POST':
    connection = model.connect()
    model.delete_place(connection, place_id, session['user']['id'])
    flash("L'adresse a été supprimée !")
    return redirect(url_for('home'))
  return render_template('place_delete.html', place=place)


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
      connection = model.connect()
      model.add_user(connection, form.username.data, form.password.data)
      flash('Votre compte a été créé, vous pouvez vous connecter.')
      return redirect(url_for('login'))
    except Exception as exception:
      flash(str(exception))
  return render_template('register.html', form=form)


class LoginForm(FlaskForm):
  username = StringField('username', validators=[validators.DataRequired(REQUIRED)])
  password = PasswordField('password', validators=[validators.DataRequired(REQUIRED)])


@app.route('/login', methods=['GET', 'POST'])
def login():
  form = LoginForm()
  if form.validate_on_submit():
    try:
      connection = model.connect()
      user = model.get_user(connection, form.username.data, form.password.data)
      session['user'] = user
      flash('Vous êtes bien connecté !')
      return redirect(url_for('home'))
    except Exception:
      flash("Nom d'utilisateur ou mot de passe incorrect.")
  return render_template('login.html', form=form)


@app.route('/logout', methods=['POST'])
def logout():
  session.clear()
  flash('Vous êtes déconnecté !')
  return redirect(url_for('home'))
