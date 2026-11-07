import json
import urllib.error
import urllib.parse
import urllib.request

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'progweb-bonnes-adresses/1.0 (projet universitaire)'


class GeocodingError(Exception):
  pass


def geocode(address: str) -> tuple:
  '''Transforme une adresse en (latitude, longitude) avec l'API Nominatim.'''
  query = urllib.parse.urlencode({'q': address, 'format': 'json', 'limit': 1})
  request = urllib.request.Request(
    NOMINATIM_URL + '?' + query,
    headers={'User-Agent': USER_AGENT})
  try:
    with urllib.request.urlopen(request, timeout=5) as response:
      results = json.load(response)
  except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
    raise GeocodingError(
      'Le service de localisation est indisponible, réessayez plus tard.')
  if len(results) == 0:
    raise GeocodingError('Adresse introuvable, vérifiez la saisie.')
  try:
    return float(results[0]['lat']), float(results[0]['lon'])
  except (KeyError, TypeError, ValueError):
    raise GeocodingError('Réponse inattendue du service de localisation.')
