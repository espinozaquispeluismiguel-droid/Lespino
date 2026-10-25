// Router hash + navegación por rol.
import { sesion } from './api.js';
import { $, esc, toast } from './ui.js';

const RUTAS = [
  { re: /^#\/login$/, vista: 'login', publica: true },
  { re: /^#\/operario$/, vista: 'operario', roles: ['operario', 'supervisor', 'administrador'] },
  { re: /^#\/operario\/calle\/(\d+)$/, vista: 'captura', roles: ['operario', 'supervisor', 'administrador'] },
  { re: /^#\/dashboard$/, vista: 'dashboard', roles: ['supervisor', 'administrador'] },
  { re: /^#\/asignaciones$/, vista: 'asignaciones', roles: ['supervisor', 'administrador'] },
  { re: /^#\/historial$/, vista: 'historial', roles: ['supervisor', 'administrador'] },
  { re: /^#\/layouts$/, vista: 'layouts', roles: ['administrador'] },
  { re: /^#\/productos$/, vista: 'productos', roles: ['administrador'] },
  { re: /^#\/usuarios$/, vista: 'usuarios', roles: ['administrador'] },
];

const MENU = {
  operario: [['#/operario', 'Mis calles']],
  supervisor: [['#/dashboard', 'Tiempo real'], ['#/asignaciones', 'Asignaciones'], ['#/historial', 'Historial']],
  administrador: [['#/dashboard', 'Tiempo real'], ['#/layouts', 'Layouts'], ['#/productos', 'Productos'],
    ['#/asignaciones', 'Asignaciones'], ['#/historial', 'Historial'], ['#/usuarios', 'Usuarios']],
};

const INICIO = { operario: '#/operario', supervisor: '#/dashboard', administrador: '#/dashboard' };

let limpiar = null; // cleanup de la vista anterior (WebSocket, cámara…)

function pintarNav(usuario) {
  const top = $('#topbar');
  if (!usuario) { top.classList.add('hidden'); return; }
  top.classList.remove('hidden');
  $('#user-label').textContent = `${usuario.nombre} · ${usuario.rol}`;
  const links = (MENU[usuario.rol] || []).map(([h, t]) =>
    `<a href="${h}" class="nav-link ${location.hash.startsWith(h) ? 'active' : ''}">${esc(t)}</a>`).join('');
  $('#nav').innerHTML = links;
  $('#nav-mobile').innerHTML = links;
}

async function navegar() {
  const hash = location.hash || '#/';
  const usuario = sesion.usuario;

  if (hash === '#/' || hash === '#') {
    location.replace(usuario ? INICIO[usuario.rol] : '#/login');
    return;
  }
  const ruta = RUTAS.find(r => r.re.test(hash));
  if (!ruta) { location.replace('#/'); return; }
  if (!ruta.publica && !usuario) { location.replace('#/login'); return; }
  if (ruta.roles && !ruta.roles.includes(usuario.rol)) {
    toast('No tiene permisos para esa vista', 'aviso');
    location.replace(INICIO[usuario.rol]);
    return;
  }

  if (typeof limpiar === 'function') { try { limpiar(); } catch { /* */ } }
  limpiar = null;
  $('#nav-mobile').classList.add('hidden');
  pintarNav(ruta.publica ? null : usuario);

  const el = $('#view');
  const params = hash.match(ruta.re).slice(1);
  try {
    const mod = await import(`./views/${ruta.vista}.js`);
    limpiar = await mod.render(el, ...params);
  } catch (e) {
    console.error(e);
    el.innerHTML = `<div class="card p-6 text-red-700">No se pudo cargar la vista: ${esc(e.message)}</div>`;
  }
}

$('#btn-logout').onclick = () => { sesion.cerrar(); location.hash = '#/login'; };
$('#btn-menu').onclick = () => $('#nav-mobile').classList.toggle('hidden');
window.addEventListener('hashchange', navegar);
navegar();
