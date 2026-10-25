// Vista supervisor: asignar calles a operarios o equipos, y gestionar equipos.
import { api } from '../api.js';
import { leyenda, renderPlano } from '../plano.js';
import { $, $$, accion, badgeCalle, cargando, confirmar, esc, layoutRecordado, selectorLayout, toast, vacio } from '../ui.js';

export async function render(el) {
  el.innerHTML = cargando();
  const [layouts, operarios, equiposIni] = await Promise.all([
    api('/layouts'), api('/usuarios', { params: { rol: 'operario' } }), api('/equipos'),
  ]);
  let equipos = equiposIni;
  if (!layouts.length) { el.innerHTML = `<div class="card">${vacio('No hay layouts creados.')}</div>`; return; }
  let idLayout = layouts.some(l => l.id === layoutRecordado.get()) ? layoutRecordado.get() : layouts[0].id;
  let detalle = null;
  const sel = new Set();

  el.innerHTML = `
    <div class="flex flex-wrap items-center gap-3 mb-4">
      <h1 class="text-xl font-bold mr-auto">Asignación de calles</h1>
      ${selectorLayout(layouts, idLayout)}
    </div>
    <div class="grid lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2 space-y-4">
        <div class="card p-4">
          <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
            <h2 class="font-semibold">Toca las calles para seleccionarlas</h2>${leyenda()}
          </div>
          <div id="plano" class="plano"></div>
        </div>
        <div class="card overflow-hidden">
          <div class="overflow-x-auto max-h-[50vh]"><table class="tabla" id="tabla-calles"></table></div>
        </div>
      </div>

      <div class="space-y-4">
        <form id="f-asignar" class="card p-4 space-y-3 lg:sticky lg:top-4">
          <h2 class="font-semibold">Asignar <span id="n-sel" class="text-marca-600"></span></h2>
          <div class="flex gap-2 text-sm">
            <label class="flex items-center gap-1.5"><input type="radio" name="tipo" value="usuario" checked> Operario</label>
            <label class="flex items-center gap-1.5"><input type="radio" name="tipo" value="equipo"> Equipo</label>
          </div>
          <select id="sel-destino" class="input"></select>
          <div class="flex gap-2">
            <button id="btn-asignar" class="btn btn-primary flex-1">Asignar</button>
            <button type="button" id="btn-limpiar" class="btn btn-secondary">Limpiar</button>
          </div>
          <div class="flex gap-2 text-xs">
            <button type="button" id="sel-pend" class="btn-ghost px-2 py-1 rounded">Seleccionar pendientes</button>
          </div>
        </form>

        <div class="card">
          <div class="px-4 py-3 border-b border-slate-100 flex items-center">
            <h2 class="font-semibold">Equipos</h2>
            <button id="btn-nuevo-eq" class="btn btn-ghost text-sm ml-auto">+ Nuevo</button>
          </div>
          <form id="f-equipo" class="hidden p-4 space-y-3 border-b border-slate-100">
            <input id="eq-nombre" class="input" placeholder="Nombre del equipo" required maxlength="100">
            <div class="max-h-40 overflow-y-auto space-y-1 text-sm">
              ${operarios.map(o => `<label class="flex items-center gap-2"><input type="checkbox" value="${o.id}" class="eq-miembro"> ${esc(o.nombre_completo)}</label>`).join('') || '<span class="text-slate-500">No hay operarios</span>'}
            </div>
            <p class="text-xs text-slate-500">El primero marcado será el líder.</p>
            <button id="btn-crear-eq" class="btn btn-primary w-full">Crear equipo</button>
          </form>
          <ul id="lista-equipos" class="divide-y divide-slate-100 text-sm"></ul>
        </div>
      </div>
    </div>`;

  function pintarDestinos() {
    const tipo = $('input[name=tipo]:checked').value;
    const opciones = tipo === 'usuario'
      ? operarios.filter(o => o.activo).map(o => `<option value="${o.id}">${esc(o.nombre_completo)} (${esc(o.username)})</option>`)
      : equipos.filter(e => e.activo).map(e => `<option value="${e.id}">${esc(e.nombre)} · ${e.miembros.length} miembros</option>`);
    $('#sel-destino').innerHTML = opciones.join('') || '<option value="">— No hay opciones —</option>';
  }

  function pintarEquipos() {
    $('#lista-equipos').innerHTML = equipos.map(e => `
      <li class="px-4 py-3"><div class="font-medium">${esc(e.nombre)}</div>
      <div class="text-xs text-slate-500">${e.miembros.map(m => esc(m.nombre_completo) + (m.es_lider ? ' ★' : '')).join(', ') || 'Sin miembros'}</div></li>`).join('')
      || `<li>${vacio('Sin equipos')}</li>`;
  }

  const todas = () => detalle.areas.flatMap(a => a.calles.map(c => ({ ...c, area: a.nombre })));

  function pintar() {
    $('#n-sel').textContent = sel.size ? `(${sel.size} calle${sel.size > 1 ? 's' : ''})` : '';
    renderPlano($('#plano'), detalle, {
      seleccion: sel,
      onClick: (c) => { sel.has(c.id) ? sel.delete(c.id) : sel.add(c.id); pintar(); },
      // Iniciales del asignado (el nombre completo está en la tabla y en el tooltip)
      etiqueta: (c) => c.asignacion ? (c.asignacion.usuario || c.asignacion.equipo || '').split(/\s+/).map(p => p[0]).join('').slice(0, 3).toUpperCase() : '',
    });
    const filas = todas();
    $('#tabla-calles').innerHTML = `
      <thead><tr><th class="w-8"><input type="checkbox" id="chk-todas"></th><th>Calle</th><th>Área</th><th>Estado</th><th>Asignada a</th><th></th></tr></thead>
      <tbody>${filas.map(c => `
        <tr><td><input type="checkbox" class="chk-calle" value="${c.id}" ${sel.has(c.id) ? 'checked' : ''}></td>
        <td class="font-medium">${esc(c.codigo)}</td><td>${esc(c.area)}</td><td>${badgeCalle(c.estado)}</td>
        <td>${c.asignacion ? `${esc(c.asignacion.usuario || '')}${c.asignacion.equipo ? `<span class="text-slate-500"> ${c.asignacion.usuario ? '· ' : ''}${esc(c.asignacion.equipo)}</span>` : ''}` : '<span class="text-slate-400">—</span>'}</td>
        <td class="text-right">${c.asignacion ? `<button class="btn-ghost text-xs px-2 py-1 rounded btn-quitar" data-a="${c.asignacion.id}" data-c="${esc(c.codigo)}">Quitar</button>` : ''}</td></tr>`).join('')}
      </tbody>`;
    $$('.chk-calle').forEach(ch => ch.onchange = () => { ch.checked ? sel.add(+ch.value) : sel.delete(+ch.value); pintar(); });
    $('#chk-todas').checked = filas.length > 0 && filas.every(c => sel.has(c.id));
    $('#chk-todas').onchange = (e) => { filas.forEach(c => e.target.checked ? sel.add(c.id) : sel.delete(c.id)); pintar(); };
    $$('.btn-quitar').forEach(b => b.onclick = accion(b, async () => {
      if (!await confirmar('Quitar asignación', `La calle ${esc(b.dataset.c)} quedará sin asignar.`, { ok: 'Quitar', peligro: true })) return;
      await api(`/asignaciones/${b.dataset.a}`, { method: 'DELETE' });
      toast('Asignación retirada', 'ok');
      await cargar();
    }));
  }

  async function cargar() {
    detalle = await api(`/layouts/${idLayout}`);
    const ids = new Set(todas().map(c => c.id));
    [...sel].forEach(id => ids.has(id) || sel.delete(id));
    pintar();
  }

  $$('input[name=tipo]').forEach(r => r.onchange = pintarDestinos);
  $('#btn-limpiar').onclick = () => { sel.clear(); pintar(); };
  $('#sel-pend').onclick = () => { todas().filter(c => c.estado === 'pendiente').forEach(c => sel.add(c.id)); pintar(); };
  $('#sel-layout').onchange = async (e) => { idLayout = +e.target.value; layoutRecordado.set(idLayout); sel.clear(); await cargar(); };

  $('#f-asignar').onsubmit = accion($('#btn-asignar'), async () => {
    if (!sel.size) { toast('Selecciona al menos una calle', 'aviso'); return; }
    const destino = +$('#sel-destino').value;
    if (!destino) { toast('Elige un operario o equipo', 'aviso'); return; }
    const tipo = $('input[name=tipo]:checked').value;
    const r = await api('/asignaciones', { method: 'POST', json: { ids_calle: [...sel], [tipo === 'usuario' ? 'id_usuario' : 'id_equipo']: destino } });
    toast(`${r.asignadas} calle(s) asignada(s)`, 'ok');
    sel.clear();
    await cargar();
  });

  $('#btn-nuevo-eq').onclick = () => $('#f-equipo').classList.toggle('hidden');
  $('#f-equipo').onsubmit = accion($('#btn-crear-eq'), async () => {
    const miembros = $$('.eq-miembro').filter(c => c.checked).map(c => +c.value);
    const eq = await api('/equipos', { method: 'POST', json: { nombre: $('#eq-nombre').value.trim(), miembros } });
    equipos = [...equipos, eq].sort((a, b) => a.nombre.localeCompare(b.nombre));
    $('#f-equipo').reset(); $('#f-equipo').classList.add('hidden');
    pintarEquipos(); pintarDestinos();
    toast(`Equipo "${eq.nombre}" creado`, 'ok');
  });

  pintarDestinos();
  pintarEquipos();
  await cargar();
}
