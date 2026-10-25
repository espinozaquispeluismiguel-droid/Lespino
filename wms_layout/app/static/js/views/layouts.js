// Administración: layouts, áreas y calles con editor de plano (arrastrar para mover).
import { api } from '../api.js';
import { renderPlano } from '../plano.js';
import { $, $$, accion, cargando, confirmar, esc, layoutRecordado, toast, vacio } from '../ui.js';

const COLORES = ['#A6192E', '#475569', '#0f766e', '#1d4ed8', '#a16207', '#7c3aed'];

export async function render(el) {
  let layouts = await api('/layouts');
  let idLayout = layouts.some(l => l.id === layoutRecordado.get()) ? layoutRecordado.get() : layouts[0]?.id;
  let detalle = null;
  let calleEdit = null;

  el.innerHTML = `
    <h1 class="text-xl font-bold mb-4">Layouts, áreas y calles</h1>
    <div class="grid lg:grid-cols-4 gap-4">
      <aside class="space-y-4">
        <div class="card">
          <div class="px-4 py-3 border-b border-slate-100 font-semibold">Layouts</div>
          <ul id="lista-layouts" class="divide-y divide-slate-100 text-sm"></ul>
          <form id="f-layout" class="p-4 border-t border-slate-100 space-y-2">
            <input id="l-nombre" class="input" placeholder="Nuevo layout" required maxlength="120">
            <button id="btn-l" class="btn btn-primary w-full">Crear layout</button>
          </form>
        </div>
      </aside>
      <section id="editor" class="lg:col-span-3 space-y-4"></section>
    </div>`;

  function pintarLista() {
    $('#lista-layouts').innerHTML = layouts.map(l => `
      <li><button data-id="${l.id}" class="sel-l w-full text-left px-4 py-3 hover:bg-slate-50 ${l.id === idLayout ? 'bg-marca-50 text-marca-700 font-medium' : ''}">
        ${esc(l.nombre)}<div class="text-xs text-slate-500 font-normal">${l.n_areas} áreas · ${l.n_calles} calles</div></button></li>`).join('')
      || `<li>${vacio('Crea tu primer layout')}</li>`;
    $$('.sel-l').forEach(b => b.onclick = () => { idLayout = +b.dataset.id; layoutRecordado.set(idLayout); pintarLista(); cargar(); });
  }

  function pintarEditor() {
    const ed = $('#editor');
    if (!detalle) { ed.innerHTML = `<div class="card">${vacio('Selecciona o crea un layout')}</div>`; return; }
    ed.innerHTML = `
      <div class="card p-4">
        <div class="flex flex-wrap items-center gap-2 mb-3">
          <h2 class="font-semibold mr-auto">${esc(detalle.nombre)}</h2>
          <span class="text-xs text-slate-500">Arrastra una calle para moverla · haz clic para editarla</span>
        </div>
        <div id="plano" class="plano"></div>
      </div>

      <div id="panel-edit" class="${calleEdit ? '' : 'hidden'} card p-4"></div>

      <div class="grid md:grid-cols-2 gap-4">
        <form id="f-area" class="card p-4 space-y-3">
          <h3 class="font-semibold">Nueva área</h3>
          <input id="a-nombre" class="input" placeholder='Ej.: "Muro", "Andamio"' required maxlength="80">
          <div class="flex gap-2 items-center">${COLORES.map((c, i) => `
            <label class="cursor-pointer"><input type="radio" name="a-color" value="${c}" class="peer hidden" ${i === 0 ? 'checked' : ''}>
            <span class="block w-7 h-7 rounded-full border-2 border-white ring-2 ring-transparent peer-checked:ring-slate-800" style="background:${c}"></span></label>`).join('')}
          </div>
          <button id="btn-a" class="btn btn-primary w-full">Crear área</button>
        </form>

        <form id="f-calles" class="card p-4 space-y-3">
          <h3 class="font-semibold">Nuevas calles</h3>
          <select id="c-area" class="input" required>
            ${detalle.areas.map(a => `<option value="${a.id}">${esc(a.nombre)}</option>`).join('') || '<option value="">Primero crea un área</option>'}
          </select>
          <div class="grid grid-cols-3 gap-2">
            <div><label class="label">Prefijo</label><input id="c-pref" class="input uppercase" value="A" maxlength="10"></div>
            <div><label class="label">Desde</label><input id="c-desde" type="number" min="0" class="input" value="1"></div>
            <div><label class="label">Hasta</label><input id="c-hasta" type="number" min="0" class="input" value="5"></div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div><label class="label">Ancho</label><input id="c-ancho" type="number" min="1" step="0.5" class="input" value="8"></div>
            <div><label class="label">Largo</label><input id="c-alto" type="number" min="1" step="0.5" class="input" value="40"></div>
          </div>
          <p id="c-preview" class="text-xs text-slate-500"></p>
          <button id="btn-c" class="btn btn-primary w-full" ${detalle.areas.length ? '' : 'disabled'}>Crear calles</button>
        </form>
      </div>

      <div class="card overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 font-semibold">Áreas</div>
        <ul class="divide-y divide-slate-100 text-sm">${detalle.areas.map(a => `
          <li class="px-4 py-3 flex items-center gap-3">
            <span class="w-3 h-3 rounded-full" style="background:${esc(a.color || '#64748b')}"></span>
            <span class="font-medium">${esc(a.nombre)}</span>
            <span class="text-slate-500 text-xs">${a.calles.map(c => esc(c.codigo)).join(', ') || 'sin calles'}</span>
            <button class="ml-auto btn-ghost text-xs px-2 py-1 rounded del-area" data-id="${a.id}" data-n="${esc(a.nombre)}">Eliminar</button>
          </li>`).join('') || `<li>${vacio('Sin áreas')}</li>`}</ul>
      </div>`;

    renderPlano($('#plano'), detalle, {
      arrastrable: true,
      seleccion: new Set(calleEdit ? [calleEdit.id] : []),
      onClick: (c) => { calleEdit = c; pintarEditor(); },
      onMover: async (c, x, y) => {
        try { await api(`/calles/${c.id}`, { method: 'PATCH', json: { coord_x: x, coord_y: y } }); Object.assign(c, { coord_x: x, coord_y: y }); }
        catch (e) { toast(e.message, 'error'); }
        pintarEditor();
      },
    });
    if (calleEdit) pintarPanelEdicion();

    const prev = () => { const p = $('#c-pref').value.toUpperCase(), d = +$('#c-desde').value, h = +$('#c-hasta').value;
      $('#c-preview').textContent = h >= d ? `Se crearán ${h - d + 1} calles: ${p}${d} … ${p}${h}` : 'Rango inválido'; };
    ['#c-pref', '#c-desde', '#c-hasta'].forEach(s => $(s).oninput = prev); prev();

    $('#f-area').onsubmit = accion($('#btn-a'), async () => {
      await api(`/layouts/${idLayout}/areas`, { method: 'POST', json: { nombre: $('#a-nombre').value.trim(), color: $('input[name=a-color]:checked').value } });
      toast('Área creada', 'ok'); await recargarTodo();
    });
    $('#f-calles').onsubmit = accion($('#btn-c'), async () => {
      const r = await api(`/areas/${$('#c-area').value}/calles`, { method: 'POST', json: {
        prefijo: $('#c-pref').value.trim(), desde: +$('#c-desde').value, hasta: +$('#c-hasta').value,
        ancho: +$('#c-ancho').value, alto: +$('#c-alto').value } });
      toast(`${r.length} calles creadas`, 'ok'); await recargarTodo();
    });
    $$('.del-area').forEach(b => b.onclick = accion(b, async () => {
      if (!await confirmar('Eliminar área', `Se eliminará el área <b>${esc(b.dataset.n)}</b> con todas sus calles.`, { ok: 'Eliminar', peligro: true })) return;
      await api(`/areas/${b.dataset.id}`, { method: 'DELETE' }); toast('Área eliminada', 'ok'); calleEdit = null; await recargarTodo();
    }));
  }

  function pintarPanelEdicion() {
    const c = calleEdit;
    $('#panel-edit').innerHTML = `
      <form id="f-edit" class="flex flex-wrap items-end gap-3">
        <h3 class="font-semibold w-full">Editar calle ${esc(c.codigo)}</h3>
        <div class="w-24"><label class="label">Código</label><input id="e-cod" class="input uppercase" value="${esc(c.codigo)}" maxlength="20"></div>
        ${['coord_x', 'coord_y', 'ancho', 'alto'].map(k => `<div class="w-24"><label class="label">${{ coord_x: 'X', coord_y: 'Y', ancho: 'Ancho', alto: 'Largo' }[k]}</label>
          <input data-k="${k}" type="number" step="0.5" class="input e-num" value="${c[k] ?? ''}"></div>`).join('')}
        <button type="button" id="e-rotar" class="btn btn-secondary" title="Intercambiar ancho y largo">↻ Girar</button>
        <button id="e-guardar" class="btn btn-primary">Guardar</button>
        <button type="button" id="e-borrar" class="btn btn-ghost text-red-600">Eliminar</button>
        <button type="button" id="e-cerrar" class="btn btn-secondary ml-auto">Cerrar</button>
      </form>`;
    $('#e-rotar').onclick = () => { const a = $('[data-k=ancho]'), l = $('[data-k=alto]'); [a.value, l.value] = [l.value, a.value]; };
    $('#e-cerrar').onclick = () => { calleEdit = null; pintarEditor(); };
    $('#f-edit').onsubmit = accion($('#e-guardar'), async () => {
      const json = { codigo: $('#e-cod').value.trim() };
      $$('.e-num').forEach(i => { if (i.value !== '') json[i.dataset.k] = +i.value; });
      Object.assign(c, await api(`/calles/${c.id}`, { method: 'PATCH', json }));
      toast('Calle actualizada', 'ok'); pintarEditor();
    });
    $('#e-borrar').onclick = accion($('#e-borrar'), async () => {
      if (!await confirmar('Eliminar calle', `¿Eliminar la calle <b>${esc(c.codigo)}</b>?`, { ok: 'Eliminar', peligro: true })) return;
      await api(`/calles/${c.id}`, { method: 'DELETE' }); calleEdit = null; toast('Calle eliminada', 'ok'); await recargarTodo();
    });
  }

  async function cargar() {
    calleEdit = null;
    if (!idLayout) { detalle = null; pintarEditor(); return; }
    $('#editor').innerHTML = cargando();
    detalle = await api(`/layouts/${idLayout}`);
    pintarEditor();
  }

  async function recargarTodo() {
    layouts = await api('/layouts');
    pintarLista();
    detalle = await api(`/layouts/${idLayout}`);
    if (calleEdit) calleEdit = detalle.areas.flatMap(a => a.calles).find(c => c.id === calleEdit.id) || null;
    pintarEditor();
  }

  $('#f-layout').onsubmit = accion($('#btn-l'), async () => {
    const l = await api('/layouts', { method: 'POST', json: { nombre: $('#l-nombre').value.trim() } });
    $('#f-layout').reset();
    idLayout = l.id; layoutRecordado.set(l.id);
    toast('Layout creado', 'ok');
    await recargarTodo();
  });

  pintarLista();
  await cargar();
}
