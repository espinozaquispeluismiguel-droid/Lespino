// Histórico de auditoría con filtros por fecha, usuario, calle, paquete y tipo de evento.
import { api } from '../api.js';
import { $, accion, cargando, esc, fecha, layoutRecordado, vacio } from '../ui.js';

const TIPOS = {
  paquete_registrado: 'Paquete registrado', paquete_recontado: 'Reconteo', paquete_no_catalogado: 'Sobrante',
  inicio_conteo: 'Inicio de conteo', calle_finalizada: 'Calle finalizada', calle_reabierta: 'Calle reabierta',
  calle_asignada: 'Asignación', calle_creada: 'Calle creada',
};
const COLOR = {
  paquete_registrado: 'bg-green-100 text-green-800', paquete_recontado: 'bg-slate-200 text-slate-700',
  paquete_no_catalogado: 'bg-violet-100 text-violet-800', inicio_conteo: 'bg-amber-100 text-amber-800',
  calle_finalizada: 'bg-blue-100 text-blue-800', calle_reabierta: 'bg-red-100 text-red-800',
  calle_asignada: 'bg-sky-100 text-sky-800', calle_creada: 'bg-slate-100 text-slate-600',
};
const POR_PAGINA = 50;

export async function render(el) {
  el.innerHTML = cargando();
  const [usuarios, layouts] = await Promise.all([api('/usuarios'), api('/layouts')]);
  const idLayout = layouts.some(l => l.id === layoutRecordado.get()) ? layoutRecordado.get() : layouts[0]?.id;
  const detalle = idLayout ? await api(`/layouts/${idLayout}`) : { areas: [] };
  const calles = detalle.areas.flatMap(a => a.calles.map(c => ({ ...c, area: a.nombre })));
  let offset = 0;

  el.innerHTML = `
    <h1 class="text-xl font-bold mb-4">Histórico de auditoría</h1>
    <form id="f-filtros" class="card p-4 grid sm:grid-cols-2 lg:grid-cols-6 gap-3 mb-4 items-end">
      <div><label class="label">Desde</label><input type="datetime-local" id="f-desde" class="input"></div>
      <div><label class="label">Hasta</label><input type="datetime-local" id="f-hasta" class="input"></div>
      <div><label class="label">Usuario</label><select id="f-usuario" class="input"><option value="">Todos</option>
        ${usuarios.map(u => `<option value="${u.id}">${esc(u.nombre_completo)}</option>`).join('')}</select></div>
      <div><label class="label">Calle ${layouts.length > 1 ? `<span class="normal-case">(${esc(detalle.nombre || '')})</span>` : ''}</label>
        <select id="f-calle" class="input"><option value="">Todas</option>
        ${calles.map(c => `<option value="${c.id}">${esc(c.codigo)} · ${esc(c.area)}</option>`).join('')}</select></div>
      <div><label class="label">Paquete</label><input id="f-paquete" class="input font-mono uppercase" placeholder="Nº paquete"></div>
      <div><label class="label">Tipo</label><select id="f-tipo" class="input"><option value="">Todos</option>
        ${Object.entries(TIPOS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></div>
      <div class="sm:col-span-2 lg:col-span-6 flex gap-2 justify-end">
        <button type="button" id="btn-reset" class="btn btn-secondary">Limpiar</button>
        <button id="btn-buscar" class="btn btn-primary">Buscar</button>
      </div>
    </form>
    <div class="card overflow-hidden">
      <div class="overflow-x-auto"><div id="resultados">${cargando()}</div></div>
      <div class="flex items-center justify-between px-4 py-3 border-t border-slate-100 text-sm">
        <span id="info-pag" class="text-slate-500"></span>
        <div class="flex gap-2"><button id="pag-ant" class="btn btn-secondary">‹ Anterior</button><button id="pag-sig" class="btn btn-secondary">Siguiente ›</button></div>
      </div>
    </div>`;

  const iso = (v) => v ? new Date(v).toISOString() : undefined;

  async function buscar() {
    $('#resultados').innerHTML = cargando();
    const r = await api('/historial', {
      params: {
        desde: iso($('#f-desde').value), hasta: iso($('#f-hasta').value), id_usuario: $('#f-usuario').value,
        id_calle: $('#f-calle').value, numero_de_paquete: $('#f-paquete').value.trim(), tipo_evento: $('#f-tipo').value,
        limit: POR_PAGINA, offset,
      },
    });
    $('#info-pag').textContent = r.total ? `${offset + 1}–${offset + r.items.length} de ${r.total}` : '';
    $('#pag-ant').disabled = offset === 0;
    $('#pag-sig').disabled = offset + POR_PAGINA >= r.total;
    if (!r.items.length) { $('#resultados').innerHTML = vacio('No hay eventos con esos filtros.'); return; }
    $('#resultados').innerHTML = `<table class="tabla"><thead><tr><th>Fecha</th><th>Evento</th><th>Calle</th><th>Usuario</th><th>Paquete</th><th>Detalle</th></tr></thead>
      <tbody>${r.items.map(e => `<tr>
        <td class="whitespace-nowrap text-xs">${fecha(e.fecha)}</td>
        <td><span class="badge ${COLOR[e.tipo_evento] || ''}">${esc(TIPOS[e.tipo_evento] || e.tipo_evento)}</span></td>
        <td class="font-medium">${esc(e.codigo_calle)}</td>
        <td>${esc(e.usuario || '—')}</td>
        <td class="font-mono text-xs">${e.numero_de_paquete ? `<button class="text-marca-600 hover:underline filtro-paq">${esc(e.numero_de_paquete)}</button>` : '—'}</td>
        <td class="text-xs text-slate-600">${esc(e.descripcion)}</td></tr>`).join('')}</tbody></table>`;
    el.querySelectorAll('.filtro-paq').forEach(b => b.onclick = () => { $('#f-paquete').value = b.textContent; offset = 0; buscar(); });
  }

  $('#f-filtros').onsubmit = accion($('#btn-buscar'), () => { offset = 0; return buscar(); });
  $('#btn-reset').onclick = () => { $('#f-filtros').reset(); offset = 0; buscar(); };
  $('#pag-ant').onclick = () => { offset = Math.max(0, offset - POR_PAGINA); buscar(); };
  $('#pag-sig').onclick = () => { offset += POR_PAGINA; buscar(); };
  await buscar();
}
