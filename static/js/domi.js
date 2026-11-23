document.addEventListener('DOMContentLoaded', function () {
  // Mostrar / ocultar contraseña
  document.querySelectorAll('input[type="password"]').forEach(function (input) {
    var group = document.createElement('div');
    group.className = 'input-group';
    input.parentNode.insertBefore(group, input);
    group.appendChild(input);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-secondary';
    btn.setAttribute('aria-label', 'Mostrar u ocultar contraseña');
    btn.innerHTML = '<i class="bi bi-eye"></i>';
    btn.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = '<i class="bi ' + (show ? 'bi-eye-slash' : 'bi-eye') + '"></i>';
    });
    group.appendChild(btn);
  });

  // Mensajes que se cierran solos
  document.querySelectorAll('.alert-auto').forEach(function (el) {
    setTimeout(function () {
      el.classList.remove('show');
      setTimeout(function () { el.remove(); }, 300);
    }, 4500);
  });

  // Evitar doble envío de formularios
  document.querySelectorAll('form[data-once]').forEach(function (form) {
    form.addEventListener('submit', function () {
      var b = form.querySelector('button[type="submit"]');
      if (b) { b.disabled = true; b.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando...'; }
    });
  });

  // Menú: búsqueda y filtro por categoría en vivo
  var search = document.getElementById('menu-search');
  var chips = document.querySelectorAll('[data-cat-chip]');
  var items = document.querySelectorAll('[data-product]');
  var counter = document.getElementById('menu-count');
  var empty = document.getElementById('menu-empty');
  if (items.length) {
    var activeCat = '';
    function apply() {
      var q = search ? search.value.trim().toLowerCase() : '';
      var visible = 0;
      items.forEach(function (it) {
        var ok = (!activeCat || it.dataset.cat === activeCat) &&
                 (!q || it.dataset.name.indexOf(q) !== -1);
        it.classList.toggle('d-none', !ok);
        if (ok) visible++;
      });
      if (counter) counter.textContent = visible + (visible === 1 ? ' producto' : ' productos');
      if (empty) empty.classList.toggle('d-none', visible !== 0);
    }
    if (search) search.addEventListener('input', apply);
    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        chips.forEach(function (c) { c.classList.remove('active'); });
        chip.classList.add('active');
        activeCat = chip.dataset.catChip;
        apply();
      });
    });
    apply();
  }
});
