// Améliorations des pages. Tout le site fonctionne sans ce fichier : il ajoute seulement
// du confort (fenêtre « Laisser un avis », aperçu de la photo, filtres immédiats...).
//
// La politique de sécurité du site (CSP) interdit les scripts écrits dans le HTML :
// les pages désignent donc ce qu'il faut améliorer avec des attributs « data-... ».

// La classe « js » permet à la feuille de style d'adapter les pages quand JavaScript est actif
document.documentElement.classList.add('js');

document.addEventListener('DOMContentLoaded', () => {
  setupFlashes();
  setupMenu();
  setupAutosubmit();
  setupBackLinks();
  setupShare();
  setupDialogs();
  setupStarPickers();
  setupCounters();
  setupPasswordToggles();
  setupDropzones();
});

// Messages « flash » : un bouton pour les fermer
function setupFlashes() {
  document.querySelectorAll('[data-dismiss]').forEach((button) => {
    button.hidden = false;
    button.addEventListener('click', () => {
      const flash = button.closest('.flash');
      const list = flash.parentElement;
      flash.remove();
      if (list.children.length === 0) {
        list.remove();
      }
    });
  });
}

// Menu du compte (petits écrans) : il se referme avec Échap ou d'un clic en dehors
function setupMenu() {
  const menu = document.querySelector('details.menu');
  if (menu === null) {
    return;
  }
  document.addEventListener('click', (event) => {
    if (menu.open && !menu.contains(event.target)) {
      menu.open = false;
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menu.open) {
      menu.open = false;
      menu.querySelector('summary').focus();
    }
  });
}

// Filtres de la page « Explorer » : sur grand écran, la feuille de style masque le bouton
// « Appliquer » et le formulaire part dès qu'une liste change. Sur téléphone le bouton reste
// affiché : on ne fait rien.
function setupAutosubmit() {
  document.querySelectorAll('form[data-autosubmit]').forEach((form) => {
    const button = form.querySelector('button[type="submit"]');
    form.querySelectorAll('select').forEach((select) => {
      select.addEventListener('change', () => {
        // offsetParent vaut null pour un élément qui n'est pas affiché
        if (button === null || button.offsetParent === null) {
          form.submit();
        }
      });
    });
  });
}

// Liens « Retour » : l'attribut data-back liste les pages vers lesquelles on revient
// avec l'historique du navigateur (les filtres et la position dans la liste sont conservés).
// Dans les autres cas, le lien mène simplement à son adresse.
function setupBackLinks() {
  if (document.referrer === '') {
    return;
  }
  const previous = new URL(document.referrer);
  document.querySelectorAll('[data-back]').forEach((link) => {
    const paths = link.dataset.back.split(' ');
    if (previous.origin !== location.origin || !paths.includes(previous.pathname)) {
      return;
    }
    link.addEventListener('click', (event) => {
      event.preventDefault();
      history.back();
    });
  });
}

// Bouton « Partager » : partage du téléphone ou de l'ordinateur s'il existe, sinon copie du lien
function setupShare() {
  const canShare = typeof navigator.share === 'function';
  const canCopy = navigator.clipboard !== undefined && typeof navigator.clipboard.writeText === 'function';
  if (!canShare && !canCopy) {
    return;
  }
  document.querySelectorAll('[data-share]').forEach((button) => {
    const label = button.querySelector('span');
    const initial = label.textContent;
    const url = location.origin + location.pathname;
    const say = (text) => {
      label.textContent = text;
      setTimeout(() => {
        label.textContent = initial;
      }, 2500);
    };
    button.hidden = false;
    button.addEventListener('click', () => {
      if (canShare) {
        // La promesse est rejetée quand la personne annule le partage : rien à signaler
        navigator.share({title: button.dataset.share, url: url}).catch(() => {});
      } else {
        navigator.clipboard.writeText(url).then(() => say('Lien copié !'), () => say('Copie impossible'));
      }
    });
  });
}

// Fenêtre « Laisser un avis » : un élément <dialog> ouvert en fenêtre modale.
// (Sans JavaScript, la feuille de style l'affiche quand l'adresse se termine par son ancre.)
function setupDialogs() {
  document.querySelectorAll('dialog.modal').forEach((dialog) => {
    const anchor = '#' + dialog.id;
    const open = () => {
      if (!dialog.open) {
        dialog.showModal();
      }
    };

    document.querySelectorAll('[data-open-dialog="' + dialog.id + '"]').forEach((opener) => {
      opener.addEventListener('click', (event) => {
        event.preventDefault();
        open();
      });
    });
    dialog.querySelectorAll('[data-close-dialog]').forEach((closer) => {
      closer.addEventListener('click', (event) => {
        event.preventDefault();
        dialog.close();
      });
    });

    // Un clic en dehors du cadre ferme la fenêtre. Le <dialog> couvre tout l'écran : la cible
    // du clic est le <dialog> lui-même quand on clique à côté du cadre. On vérifie aussi où
    // le bouton de la souris a été enfoncé, pour ne pas fermer la fenêtre quand une sélection
    // de texte commencée dans le formulaire se termine en dehors.
    let pressedOutside = false;
    dialog.addEventListener('mousedown', (event) => {
      pressedOutside = event.target === dialog;
    });
    dialog.addEventListener('click', (event) => {
      if (pressedOutside && event.target === dialog) {
        dialog.close();
      }
    });

    // L'ancre ne sert qu'à ouvrir la fenêtre : on la retire de l'adresse à la fermeture
    dialog.addEventListener('close', () => {
      if (location.hash === anchor) {
        history.replaceState(null, '', location.pathname + location.search);
      }
    });

    // Ouverture dès l'arrivée sur la page : formulaire refusé par le serveur (data-open) ou ancre
    if (dialog.hasAttribute('data-open') || location.hash === anchor) {
      open();
    }
    // ... ou plus tard, si l'ancre est ajoutée à l'adresse de la page déjà affichée
    window.addEventListener('hashchange', () => {
      if (location.hash === anchor) {
        open();
      }
    });
  });
}

// Note choisie, écrite à côté des étoiles : « 4 / 5 »
function setupStarPickers() {
  document.querySelectorAll('[data-star-output]').forEach((output) => {
    const picker = output.closest('fieldset');
    const update = () => {
      const checked = picker.querySelector('input:checked');
      output.hidden = checked === null;
      output.textContent = checked === null ? '' : checked.value + ' / 5';
    };
    picker.addEventListener('change', update);
    update();
  });
}

// Compteur de caractères sous une zone de texte : « 12/500 »
function setupCounters() {
  document.querySelectorAll('textarea[data-counter]').forEach((textarea) => {
    const counter = document.getElementById(textarea.dataset.counter);
    const update = () => {
      counter.textContent = textarea.value.length + '/' + textarea.maxLength;
    };
    counter.hidden = false;
    textarea.addEventListener('input', update);
    update();
  });
}

// Bouton « œil » : affiche ou masque le ou les mots de passe désignés par data-toggle-password
function setupPasswordToggles() {
  document.querySelectorAll('[data-toggle-password]').forEach((button) => {
    const inputs = button.dataset.togglePassword.split(' ').map((id) => document.getElementById(id));
    const use = button.querySelector('use');
    button.hidden = false;
    button.addEventListener('click', () => {
      const show = button.getAttribute('aria-pressed') !== 'true';
      inputs.forEach((input) => {
        input.type = show ? 'text' : 'password';
      });
      button.setAttribute('aria-pressed', String(show));
      use.setAttribute('href', show ? '#i-eye-off' : '#i-eye');
    });
  });
}

// Photo d'une adresse : contrôle du fichier, aperçu et glisser-déposer.
// Le serveur refait tous les contrôles (photos.py) ; ceux-ci évitent seulement un envoi inutile.
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function setupDropzones() {
  document.querySelectorAll('[data-dropzone]').forEach((zone) => {
    const field = zone.closest('.field');
    const input = zone.querySelector('input[type="file"]');
    const title = zone.querySelector('.dropzone-title');
    const icon = zone.querySelector('.dropzone-icon');
    const preview = zone.querySelector('.dropzone-preview');
    const error = field.querySelector('[data-dropzone-error]');
    const clear = field.querySelector('[data-dropzone-clear]');
    const initialTitle = title.textContent;
    const maxSize = Number(zone.dataset.maxSize);

    // Revient à l'état de départ, avec éventuellement un message d'erreur
    const reset = (message) => {
      input.value = '';
      title.textContent = initialTitle;
      preview.hidden = true;
      icon.hidden = false;
      clear.hidden = true;
      error.hidden = message === undefined;
      error.querySelector('span').textContent = message || '';
    };

    input.addEventListener('change', () => {
      const file = input.files[0];
      if (file === undefined) {
        reset();
      } else if (!PHOTO_TYPES.includes(file.type)) {
        reset('Format non accepté : choisissez une image JPEG, PNG ou WebP.');
      } else if (file.size > maxSize) {
        reset('Photo trop lourde : ' + Math.round(maxSize / 1048576) + ' Mo maximum.');
      } else {
        error.hidden = true;
        clear.hidden = false;
        title.textContent = file.name;
        drawPreview(file, preview).then(() => {
          // Entre-temps, une autre photo a pu être choisie
          if (input.files[0] === file) {
            preview.hidden = false;
            icon.hidden = true;
          }
        }, () => {
          preview.hidden = true;
          icon.hidden = false;
        });
      }
    });
    clear.addEventListener('click', () => reset());

    // Le champ « fichier » recouvre toute la zone (voir style.css) : le navigateur gère donc
    // lui-même le dépôt d'un fichier. Il reste à mettre la zone en valeur pendant le survol.
    ['dragenter', 'dragover'].forEach((type) => {
      zone.addEventListener(type, () => zone.classList.add('is-dragover'));
    });
    ['dragleave', 'drop'].forEach((type) => {
      zone.addEventListener(type, () => zone.classList.remove('is-dragover'));
    });
  });
}

// Dessine la photo choisie dans le <canvas> d'aperçu, recadrée pour le remplir.
// La CSP du site refuse les images en « blob: » (l'adresse habituelle d'un fichier choisi) :
// plutôt que d'assouplir la règle, on dessine directement le fichier.
function drawPreview(file, canvas) {
  if (typeof createImageBitmap !== 'function') {
    return Promise.reject(new Error('aperçu indisponible'));
  }
  return createImageBitmap(file).then((bitmap) => {
    const scale = Math.max(canvas.width / bitmap.width, canvas.height / bitmap.height);
    const width = bitmap.width * scale;
    const height = bitmap.height * scale;
    const context = canvas.getContext('2d');
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, (canvas.width - width) / 2, (canvas.height - height) / 2, width, height);
    bitmap.close();
  });
}
