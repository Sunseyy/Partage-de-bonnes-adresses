import io
import json
import urllib.error
import pytest
from flask_app import geocoding


class FakeResponse(io.BytesIO):
  def __enter__(self):
    return self
  def __exit__(self, *args):
    return False


def fake_urlopen(content):
  return lambda request, timeout: FakeResponse(json.dumps(content).encode())


def test_geocode_ok(monkeypatch):
  monkeypatch.setattr('urllib.request.urlopen',
                      fake_urlopen([{'lat': '43.29', 'lon': '5.37'}]))
  assert geocoding.geocode('Marseille') == (43.29, 5.37)


def test_geocode_not_found(monkeypatch):
  monkeypatch.setattr('urllib.request.urlopen', fake_urlopen([]))
  with pytest.raises(geocoding.GeocodingError) as exception_info:
    geocoding.geocode('azertyuiop')
  assert str(exception_info.value) == 'Adresse introuvable, vérifiez la saisie.'


def test_geocode_service_down(monkeypatch):
  def broken(request, timeout):
    raise urllib.error.URLError('hors ligne')
  monkeypatch.setattr('urllib.request.urlopen', broken)
  with pytest.raises(geocoding.GeocodingError):
    geocoding.geocode('Marseille')
