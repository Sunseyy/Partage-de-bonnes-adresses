// Cartes du site, dessinées avec la bibliothèque Leaflet sur les fonds de carte d'OpenStreetMap.
//   - Page « Carte » : un repère par adresse, à la couleur de sa catégorie. Un clic sur un repère
//     affiche la fiche du lieu en bas de la carte.
//   - Page d'un lieu : une petite carte (attribut data-mini) centrée sur l'adresse.
// Les lieux à afficher sont lus dans l'attribut data-places de la carte (JSON écrit par le serveur).
// Tout est créé avec le DOM (textContent) : aucun texte saisi par les utilisateurs n'est
// interprété comme du HTML.

(() => {
  const container = document.getElementById('map');
  // L est l'objet global défini par Leaflet (static/leaflet/leaflet.js)
  if (container === null || typeof L === 'undefined') {
    return;
  }

  const places = JSON.parse(container.dataset.places);
  const mini = 'mini' in container.dataset;
  const narrow = window.matchMedia('(max-width: 900px)').matches;

  const CATEGORIES = ['restaurant', 'cafe', 'loisirs', 'commerce', 'hebergement', 'autre'];
  const SVG = 'http://www.w3.org/2000/svg';

  // Catégorie connue : elle sert à former un nom de classe CSS (« cat-cafe ») et un nom d'icône
  function categoryKey(place) {
    return CATEGORIES.includes(place.category) ? place.category : 'autre';
  }

  // Une icône du site, comme la macro « icon » des templates (voir templates/_icons.html)
  function icon(name) {
    const svg = document.createElementNS(SVG, 'svg');
    const use = document.createElementNS(SVG, 'use');
    svg.setAttribute('class', 'icon');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    use.setAttribute('href', '#i-' + name);
    svg.appendChild(use);
    return svg;
  }


  // ---------- Carte et repères ----------

  const map = L.map(container, {
    // Les boutons de zoom de Leaflet sont remplacés par les nôtres (voir plus bas)
    zoomControl: false,
    minZoom: 3,
    // La petite carte ne doit pas retenir le défilement de la page (molette, doigt)
    scrollWheelZoom: !mini,
    dragging: !(mini && L.Browser.mobile)
  });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);

  // Repère en forme de goutte (classes .pin et .cat-... de style.css) dont la pointe,
  // en bas au milieu, désigne le lieu
  function pinIcon(place) {
    const key = categoryKey(place);
    const pin = document.createElement('span');
    pin.className = 'pin cat-' + key;
    pin.appendChild(icon('cat-' + key));
    return L.divIcon({className: 'pin-icon', html: pin, iconSize: [36, 46], iconAnchor: [18, 44]});
  }

  const points = places.map((place) => [place.latitude, place.longitude]);

  // La vue est choisie avant d'ajouter les repères : Leaflet ne les dessine qu'une fois la carte cadrée
  if (mini) {
    map.setView(points[0], 15);
  } else {
    setupLegend();
    if (points.length > 0) {
      map.fitBounds(L.latLngBounds(points), fitOptions());
    } else {
      // Aucune adresse à montrer : vue d'ensemble de la France
      map.setView([46.6, 2.4], 5);
    }
    map.on('click', closeCard);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeCard();
      }
    });
  }

  places.forEach((place, index) => {
    const marker = L.marker(points[index], {
      icon: pinIcon(place),
      title: mini ? '' : place.name,
      interactive: !mini,
      keyboard: !mini,
      riseOnHover: true
    }).addTo(map);

    if (!mini) {
      // Le repère se comporte comme un bouton : clic, ou Entrée / Espace au clavier
      const pin = marker.getElement();
      pin.setAttribute('aria-label', place.name);
      marker.on('click', () => openCard(place, marker, false));
      pin.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openCard(place, marker, true);
        }
      });
    }
  });
  setupControls();

  // Sur téléphone la légende est repliée, pour laisser la place à la carte
  function setupLegend() {
    const legend = document.querySelector('details.legend');
    if (legend !== null && narrow) {
      legend.open = false;
    }
  }

  // Marges à garder libres (en pixels) quand la carte se cadre sur les repères : la recherche
  // et la légende couvrent le haut de la carte sur téléphone, son bord droit sur grand écran.
  // Un repère mesure 46 pixels de haut, d'où la marge supplémentaire en haut.
  function fitOptions() {
    const overlay = document.querySelector('.map-overlay');
    if (narrow) {
      return {maxZoom: 16, paddingTopLeft: [30, overlay.offsetHeight + 70], paddingBottomRight: [30, 40]};
    }
    return {maxZoom: 16, paddingTopLeft: [40, 70], paddingBottomRight: [overlay.offsetWidth + 50, 40]};
  }


  // ---------- Fiche du lieu sélectionné (page « Carte ») ----------

  // Repère dont la fiche est affichée
  let selected = null;

  function openCard(place, marker, moveFocus) {
    closeCard();
    const slot = document.getElementById('map-card');
    const template = document.getElementById('map-card-template');
    const card = template.content.firstElementChild.cloneNode(true);
    const key = categoryKey(place);

    // Photo du lieu ou, sans photo, aplat de la couleur de sa catégorie
    if (place.photo !== null) {
      const photo = card.querySelector('img.map-card-photo');
      photo.src = place.photo;
      photo.hidden = false;
    } else {
      const blank = card.querySelector('span.map-card-photo');
      blank.classList.add('cat-' + key);
      blank.querySelector('use').setAttribute('href', '#i-cat-' + key);
      blank.hidden = false;
    }

    card.querySelector('.map-card-name').textContent = place.name;
    const rating = card.querySelector('.map-card-rating');
    if (place.rating !== null) {
      rating.querySelector('strong').textContent = place.rating;
      rating.querySelector('.rating-count').textContent = '(' + place.review_count + ' avis)';
    } else {
      rating.classList.add('rating-none');
      rating.querySelector('.icon').classList.remove('icon-solid');
      rating.querySelector('strong').remove();
      rating.querySelector('.rating-count').textContent = 'Pas encore d\'avis';
    }
    card.querySelector('.map-card-meta').textContent = place.category_label + ' · ' + place.address;
    card.querySelector('.map-card-link').href = place.url;
    card.querySelector('.map-card-close').addEventListener('click', closeCard);

    slot.replaceChildren(card);
    selected = marker;
    marker.getElement().classList.add('is-selected');
    marker.setZIndexOffset(1000);
    // Sur téléphone, la feuille de style remonte les boutons de la carte au-dessus de la fiche
    container.parentElement.style.setProperty('--card-height', slot.offsetHeight + 'px');
    // La fiche vient peut-être de recouvrir le repère choisi : la carte se décale si besoin
    map.panInside(marker.getLatLng(), {
      paddingTopLeft: [30, 60],
      paddingBottomRight: [30, slot.offsetHeight + 40]
    });
    if (moveFocus) {
      card.querySelector('.map-card-link').focus();
    }
  }

  function closeCard() {
    if (selected === null) {
      return;
    }
    const slot = document.getElementById('map-card');
    const pin = selected.getElement();
    // Si la fiche est fermée au clavier, on revient sur le repère
    const hadFocus = slot.contains(document.activeElement);
    pin.classList.remove('is-selected');
    selected.setZIndexOffset(0);
    selected = null;
    slot.replaceChildren();
    container.parentElement.style.setProperty('--card-height', '0px');
    if (hadFocus) {
      pin.focus();
    }
  }


  // ---------- Boutons de la carte : zoom et « Me localiser » ----------

  function controlButton(symbol, label) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'map-control';
    button.title = label;
    button.setAttribute('aria-label', label);
    button.appendChild(icon(symbol));
    return button;
  }

  function setupControls() {
    const zoomIn = controlButton('plus', 'Zoomer');
    const zoomOut = controlButton('minus', 'Dézoomer');
    const buttons = [zoomIn, zoomOut];
    zoomIn.addEventListener('click', () => map.zoomIn());
    zoomOut.addEventListener('click', () => map.zoomOut());

    // Un bouton est grisé quand le zoom ne peut pas aller plus loin
    const update = () => {
      zoomIn.disabled = map.getZoom() >= map.getMaxZoom();
      zoomOut.disabled = map.getZoom() <= map.getMinZoom();
    };
    map.on('zoomend', update);
    update();

    if (!mini) {
      buttons.push(locateButton());
    }

    const control = L.control({position: 'bottomright'});
    control.onAdd = () => {
      const box = L.DomUtil.create('div', 'map-controls');
      buttons.forEach((button) => box.appendChild(button));
      // Un clic sur un bouton n'est pas un clic sur la carte
      L.DomEvent.disableClickPropagation(box);
      return box;
    };
    control.addTo(map);
  }

  // « Me localiser » : centre la carte sur la position donnée par le navigateur,
  // qui demande d'abord son accord à la personne
  function locateButton() {
    const button = controlButton('crosshair', 'Me localiser');
    // Point bleu placé à l'endroit où se trouve la personne
    let dot = null;

    button.addEventListener('click', () => {
      button.classList.add('is-busy');
      map.locate({setView: true, maxZoom: 15, timeout: 10000});
    });
    map.on('locationfound', (event) => {
      button.classList.remove('is-busy');
      if (dot === null) {
        const here = L.divIcon({className: 'here-dot', iconSize: [20, 20]});
        dot = L.marker(event.latlng, {icon: here, interactive: false, keyboard: false}).addTo(map);
      } else {
        dot.setLatLng(event.latlng);
      }
    });
    map.on('locationerror', () => {
      button.classList.remove('is-busy');
      showMessage('Localisation impossible. Vérifiez que votre navigateur autorise ce site à connaître votre position.');
    });
    return button;
  }

  // Message temporaire posé sur la carte
  function showMessage(text) {
    const message = document.createElement('p');
    message.className = 'map-message';
    message.textContent = text;
    document.getElementById('map-messages').appendChild(message);
    setTimeout(() => message.remove(), 7000);
  }
})();
