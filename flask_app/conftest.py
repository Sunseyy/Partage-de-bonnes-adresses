import pytest


@pytest.fixture(autouse=True)
def upload_folder(tmp_path, monkeypatch):
  # Pendant les tests, les photos vont dans un dossier temporaire (jamais dans uploads/)
  folder = tmp_path / 'uploads'
  monkeypatch.setenv('UPLOAD_FOLDER', str(folder))
  return folder
