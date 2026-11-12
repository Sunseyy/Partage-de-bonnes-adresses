import os
import shutil
from uuid import uuid4
from PIL import Image, ImageOps

# Formats acceptés à l'envoi. Tout est ensuite réenregistré en JPEG.
FORMATS = ['JPEG', 'PNG', 'WEBP']
MAX_SIDE = 1600          # plus grand côté conservé, en pixels
MAX_PIXELS = 50_000_000  # au-delà on refuse de décoder l'image

EXAMPLES = os.path.join(os.path.dirname(__file__), 'example_photos')


class PhotoError(Exception):
  pass


def folder() -> str:
  # Les photos envoyées sont rangées hors de static/ et servies par la route /photos
  path = os.path.abspath(os.getenv('UPLOAD_FOLDER', 'uploads'))
  os.makedirs(path, exist_ok=True)
  return path


def read(file) -> Image.Image:
  # On ne se fie ni au nom du fichier ni au type annoncé par le navigateur :
  # c'est Pillow qui dit si le contenu est vraiment une image.
  try:
    image = Image.open(file, formats=FORMATS)
    if image.width * image.height > MAX_PIXELS:
      raise PhotoError('Cette image est trop grande.')
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    # Les téléphones enregistrent l'orientation à part : on l'applique à l'image
    image = ImageOps.exif_transpose(image)
    if image.mode in ('RGBA', 'LA', 'PA') or 'transparency' in image.info:
      # Le JPEG n'a pas de transparence : on pose l'image sur un fond blanc
      image = image.convert('RGBA')
      background = Image.new('RGB', image.size, 'white')
      background.paste(image, mask=image.getchannel('A'))
      return background
    return image.convert('RGB')
  except PhotoError:
    raise
  except Exception:
    # Fichier illisible, tronqué ou qui n'est pas une image
    raise PhotoError("Ce fichier n'est pas une image valide (JPEG, PNG ou WebP).")


def save(image : Image.Image) -> str:
  # Le nom est tiré au hasard, jamais repris de celui fourni par l'utilisateur.
  # Réenregistrer l'image supprime aussi ses métadonnées (position GPS, appareil...).
  filename = uuid4().hex + '.jpg'
  image.save(os.path.join(folder(), filename), 'JPEG',
             quality=82, optimize=True, progressive=True)
  return filename


def delete(filename : str) -> None:
  if filename is None:
    return
  path = os.path.join(folder(), os.path.basename(filename))
  if os.path.isfile(path):
    os.remove(path)


def install_example(filename : str) -> str:
  # Photos des données de test : copiées telles quelles dans le dossier des photos
  if filename is None:
    return None
  shutil.copyfile(os.path.join(EXAMPLES, filename),
                  os.path.join(folder(), filename))
  return filename
