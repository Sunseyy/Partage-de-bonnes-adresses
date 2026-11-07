(function () {
  var container = document.getElementById('map');
  if (container === null) {
    return;
  }
  var markers = JSON.parse(container.dataset.places);

  var map = L.map('map');
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);

  // Le contenu du popup est construit avec le DOM (textContent) pour éviter toute injection HTML
  function popupContent(item) {
    var div = document.createElement('div');
    var link = document.createElement('a');
    link.href = item.url;
    link.textContent = item.name;
    link.className = 'fw-bold';
    div.appendChild(link);
    div.appendChild(document.createElement('br'));
    var rating = item.average_rating === null
      ? 'Pas encore noté'
      : item.average_rating.toFixed(1) + ' / 5';
    div.appendChild(document.createTextNode(item.category + ' \u00b7 ' + rating));
    return div;
  }

  var points = [];
  markers.forEach(function (item) {
    var point = [item.latitude, item.longitude];
    points.push(point);
    L.marker(point).addTo(map).bindPopup(popupContent(item));
  });

  if (points.length > 0) {
    map.fitBounds(L.latLngBounds(points).pad(0.2), { maxZoom: 16 });
  } else {
    map.setView([46.6, 2.4], 5);
  }
})();
