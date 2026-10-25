// Utilidades de interfaz compartidas.

export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export const ESTADO_CALLE = {
  pendiente:       { txt: 'Pendiente',       fill: '#e2e8f0', cls: 'bg-slate-200 text-slate-700' },
  asignada:        { txt: 'Asignada',        fill: '#bfdbfe', cls: 'bg-blue-100 text-blue-800' },
  en_proceso:      { txt: 'En proceso',      fill: '#fde68a', cls: 'bg-amber-100 text-amber-800' },
  verificada:      { txt: 'Verificada',      fill: '#86efac', cls: 'bg-green-100 text-green-800' },
  con_incidencias: { txt: 'Con incidencias', fill: '#fca5a5', cls: 'bg-red-100 text-red-800' },
};

export const ESTADO_CONTEO = {
  coincide:      { txt: 'Coincide',      cls: 'bg-green-100 text-green-800', card: 'border-green-500 bg-green-50', icono: '✓' },
  diferencia:    { txt: 'Diferencia',    cls: 'bg-amber-100 text-amber-800', card: 'border-amber-500 bg-amber-50', icono: '!' },
  no_catalogado: { txt: 'Sobrante',      cls: 'bg-violet-100 text-violet-800', card: 'border-violet-500 bg-violet-50', icono: '?' },
};

export const METODO = { manual: 'Manual', qr: 'QR / Barras', foto_ia: 'Foto IA' };

export const badgeCalle = (e) => `<span class="badge ${ESTADO_CALLE[e]?.cls || ''}">${esc(ESTADO_CALLE[e]?.txt || e)}</span>`;
export const badgeConteo = (e) => `<span class="badge ${ESTADO_CONTEO[e]?.cls || ''}">${esc(ESTADO_CONTEO[e]?.txt || e)}</span>`;

export const num = (v, dec = 3) => v == null ? '—' : Number(v).toLocaleString('es-PE', { maximumFractionDigits: dec });
// El servidor guarda en UTC; si la fecha llega sin zona (SQLite), se interpreta como UTC
const aFecha = (v) => v instanceof Date ? v : new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(v) ? v : `${v}Z`);
export const fecha = (v) => v ? aFecha(v).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'medium' }) : '—';
export const hora = (v) => v ? aFecha(v).toLocaleTimeString('es-PE') : '';

export function toast(msg, tipo = 'info', ms = 3500) {
  const colores = { info: 'bg-slate-800', ok: 'bg-green-600', error: 'bg-red-600', aviso: 'bg-amber-600' };
  const el = document.createElement('div');
  el.className = `${colores[tipo] || colores.info} text-white text-sm px-4 py-3 rounded-lg shadow-lg max-w-sm feed-item`;
  el.textContent = msg;
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), ms);
}

/** Modal de confirmación propio (evita window.confirm, que bloquea la página). */
export function confirmar(titulo, texto, { ok = 'Confirmar', peligro = false } = {}) {
  return new Promise((resolve) => {
    const root = $('#modal-root');
    root.innerHTML = `
      <div class="fixed inset-0 bg-slate-900/40 z-40 flex items-end sm:items-center justify-center p-4">
        <div class="card w-full max-w-md p-5">
          <h3 class="font-semibold text-lg mb-1">${esc(titulo)}</h3>
          <p class="text-sm text-slate-600 mb-5">${texto}</p>
          <div class="flex justify-end gap-2">
            <button data-r="0" class="btn btn-secondary">Cancelar</button>
            <button data-r="1" class="btn ${peligro ? 'btn-danger' : 'btn-primary'}">${esc(ok)}</button>
          </div>
        </div>
      </div>`;
    root.querySelectorAll('[data-r]').forEach(b => b.onclick = () => { root.innerHTML = ''; resolve(b.dataset.r === '1'); });
  });
}

export function cargando(texto = 'Cargando…') {
  return `<div class="flex items-center gap-3 text-slate-500 py-10 justify-center">
    <span class="w-5 h-5 border-2 border-slate-300 border-t-marca-600 rounded-full animate-spin"></span>${esc(texto)}</div>`;
}

export function vacio(texto) {
  return `<div class="text-center text-slate-500 py-10 text-sm">${esc(texto)}</div>`;
}

/** Envuelve un manejador async: deshabilita el botón y muestra errores. */
export function accion(btn, fn) {
  return async (ev) => {
    ev?.preventDefault?.();
    if (btn) btn.disabled = true;
    try { await fn(ev); } catch (e) { toast(e.message || String(e), 'error', 5000); console.error(e); }
    finally { if (btn) btn.disabled = false; }
  };
}

export function selectorLayout(layouts, actual) {
  return `<select id="sel-layout" class="input max-w-xs">
    ${layouts.map(l => `<option value="${l.id}" ${l.id == actual ? 'selected' : ''}>${esc(l.nombre)}</option>`).join('')}
  </select>`;
}

const K_LAYOUT = 'wms_layout_sel';
export const layoutRecordado = {
  get() { try { return Number(localStorage.getItem(K_LAYOUT)) || null; } catch { return null; } },
  set(id) { try { localStorage.setItem(K_LAYOUT, id); } catch { /* */ } },
};
