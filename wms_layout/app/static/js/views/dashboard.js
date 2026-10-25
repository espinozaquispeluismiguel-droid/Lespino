// Vista supervisor: plano en tiempo real (WebSocket), KPIs y feed de eventos.
import { api, wsUrl } from '../api.js';
import { leyenda, renderPlano } from '../plano.js';
import {
  $, ESTADO_CALLE, METODO, accion, badgeCalle, badgeConteo, cargando, confirmar, esc, hora, layoutRecordado, num,
  selectorLayout, toast, vacio,
} from '../ui.js';

export async function render(el) {
  el.innerHTML = cargando();
  const layouts = await api('/layouts');
  if (!layouts.length) {
    el.innerHTML = `<div class="card">${vacio('No hay layouts. Un administrador debe crearlos en la sección Layouts.')}</div>`;
    return;
  }
  let idLayout = layouts.some(l => l.id === layoutRecordado.get()) ? layoutRecordado.get() : layouts[0].id;
  let detalle = null, ws = null, reintento = null, ping = null, cerrado = false, calleSel = null;

  el.innerHTML = `
    <div class="flex flex-wrap items-center gap-3 mb-4">
      <h1 class="text-xl font-bold mr-auto">Monitoreo en tiempo real</h1>
      <span id="conexion" class="badge bg-slate-200 text-slate-600">Conectando…</span>
      ${selectorLayout(layouts, idLayout)}
    </div>

    <div id="kpis" class="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4"></div>

    <div class="grid lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2 card p-4">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 class="font-semibold">Plano</h2>${leyenda()}
        </div>
        <div id="plano" class="plano"></div>
        <div id="resumen-estados" class="flex flex-wrap gap-2 mt-3 text-xs"></div>
      </div>
      <div class="space-y-4">
        <div id="panel-calle" class="card hidden"></div>
        <div class="card">
          <div class="px-4 py-3 border-b border-slate-100 font-semibold">Actividad</div>
          <ul id="feed" class="divide-y divide-slate-100 max-h-[60vh] overflow-y-auto text-sm">
            <li class="px-4 py-6 text-center text-slate-400" id="feed-vacio">Esperando eventos…</li>
          </ul>
        </div>
      </div>
    </div>`;

  function kpis(a) {
    const tarjeta = (titulo, valor, sub = '', color = 'text-slate-900') => `
      <div class="card p-4"><div class="text-xs uppercase tracking-wide text-slate-500">${titulo}</div>
      <div class="text-2xl font-bold ${color} mt-1">${valor}</div><div class="text-xs text-slate-500">${sub}</div></div>`;
    $('#kpis').innerHTML =
      `<div class="card p-4 col-span-2 lg:col-span-1">
        <div class="text-xs uppercase tracking-wide text-slate-500">Avance</div>
        <div class="text-2xl font-bold mt-1">${num(a.porcentaje_avance, 1)}%</div>
        <div class="h-2 bg-slate-100 rounded-full mt-2 overflow-hidden"><div class="h-full bg-marca-600 transition-all duration-500" style="width:${Math.min(100, a.porcentaje_avance)}%"></div></div>
      </div>` +
      tarjeta('Contados', `${a.contados}`, `de ${a.total_catalogados} catalogados`) +
      tarjeta('Coinciden', a.coinciden, '', 'text-green-700') +
      tarjeta('Diferencias', a.diferencias, '', 'text-amber-700') +
      tarjeta('Sobrantes', a.no_catalogados, 'no catalogados', 'text-violet-700');
  }

  function calles() { return detalle.areas.flatMap(a => a.calles); }

  function pintarPlano() {
    renderPlano($('#plano'), detalle, {
      seleccion: new Set(calleSel ? [calleSel] : []),
      onClick: (c) => abrirCalle(c.id),
      etiqueta: (c) => c.paquetes_contados ? String(c.paquetes_contados) : '',
    });
    const cuenta = {};
    calles().forEach(c => cuenta[c.estado] = (cuenta[c.estado] || 0) + 1);
    $('#resumen-estados').innerHTML = Object.entries(ESTADO_CALLE).map(([k, e]) =>
      `<span class="badge ${e.cls}">${e.txt}: ${cuenta[k] || 0}</span>`).join('');
  }

  function pulso(id) {
    const g = document.querySelector(`#plano .calle[data-id="${id}"]`);
    if (g) { g.classList.remove('pulso'); void g.offsetWidth; g.classList.add('pulso'); }
  }

  function actualizarCalle(id, cambios) {
    const c = calles().find(x => x.id === id);
    if (!c) return;
    Object.assign(c, cambios);
    pintarPlano();
    pulso(id);
    if (calleSel === id) abrirCalle(id, false);
  }

  function alFeed(html) {
    $('#feed-vacio')?.remove();
    const li = document.createElement('li');
    li.className = 'px-4 py-3 feed-item';
    li.innerHTML = html;
    $('#feed').prepend(li);
    while ($('#feed').children.length > 80) $('#feed').lastChild.remove();
  }

  function onEvento({ evento, data }) {
    if (evento === 'snapshot') { kpis(data.avance); return; }
    if (evento === 'paquete_registrado') {
      kpis(data.avance);
      actualizarCalle(data.calle.id, {
        estado: data.calle.estado, paquetes_contados: data.calle.paquetes_contados,
        diferencias: data.calle.diferencias, no_catalogados: data.calle.no_catalogados,
      });
      const dif = data.cantidad_esperada != null ? ` · ${num(data.cantidad_contada)}/${num(data.cantidad_esperada)}` : ` · ${num(data.cantidad_contada)}`;
      alFeed(`<div class="flex items-center gap-2"><span class="font-mono font-medium">${esc(data.numero_de_paquete)}</span>${badgeConteo(data.estado)}
        ${data.es_reconteo ? '<span class="badge bg-slate-200 text-slate-700">Reconteo</span>' : ''}<span class="ml-auto text-xs text-slate-400">${hora(data.fecha_registro)}</span></div>
        <div class="text-xs text-slate-500 mt-0.5">Calle ${esc(data.codigo_calle)} · ${esc(data.usuario)} · ${esc(METODO[data.metodo_ingreso])}${dif}</div>`);
      return;
    }
    if (evento === 'calle_finalizada' || evento === 'calle_actualizada') {
      actualizarCalle(data.id, { estado: data.estado, paquetes_contados: data.paquetes_contados,
        diferencias: data.diferencias, no_catalogados: data.no_catalogados });
      alFeed(`<div class="flex items-center gap-2">Calle <b>${esc(data.codigo)}</b> ${badgeCalle(data.estado)}<span class="ml-auto text-xs text-slate-400">${hora(new Date())}</span></div>`);
      return;
    }
    if (evento === 'calles_asignadas') {
      data.calles.forEach(c => actualizarCalle(c.id, { estado: c.estado, asignacion: c.asignacion }));
      alFeed(`<div>Asignación actualizada: ${data.calles.map(c => `<b>${esc(c.codigo)}</b>`).join(', ')}</div>`);
    }
  }

  function estadoConexion(txt, cls) { const b = $('#conexion'); if (b) { b.textContent = txt; b.className = `badge ${cls}`; } }

  function conectar() {
    if (cerrado) return;
    ws = new WebSocket(wsUrl(idLayout));
    ws.onopen = () => {
      estadoConexion('● En vivo', 'bg-green-100 text-green-800');
      ping = setInterval(() => ws.readyState === 1 && ws.send('ping'), 25000);
    };
    ws.onmessage = (e) => { if (e.data !== 'pong') onEvento(JSON.parse(e.data)); };
    ws.onclose = () => {
      clearInterval(ping);
      if (cerrado) return;
      estadoConexion('Reconectando…', 'bg-amber-100 text-amber-800');
      reintento = setTimeout(conectar, 3000);
    };
  }

  function desconectar() {
    clearTimeout(reintento); clearInterval(ping);
    if (ws) { ws.onclose = null; ws.close(); ws = null; }
  }

  async function abrirCalle(id, cargarRegs = true) {
    calleSel = id;
    const c = calles().find(x => x.id === id);
    const panel = $('#panel-calle');
    panel.classList.remove('hidden');
    document.querySelectorAll('#plano .calle').forEach(g => g.classList.toggle('sel', +g.dataset.id === id));
    const cerrada = ['verificada', 'con_incidencias'].includes(c.estado);
    panel.innerHTML = `
      <div class="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
        <h3 class="font-semibold">Calle ${esc(c.codigo)}</h3>${badgeCalle(c.estado)}
        <button id="cerrar-panel" class="ml-auto text-slate-400 hover:text-slate-700 text-lg" aria-label="Cerrar">×</button>
      </div>
      <div class="p-4 text-sm space-y-1">
        <div>Asignada a: <b>${esc(c.asignacion ? (c.asignacion.usuario || c.asignacion.equipo) : 'nadie')}</b></div>
        <div>Paquetes: <b>${c.paquetes_contados || 0}</b> · diferencias <b class="text-amber-700">${c.diferencias || 0}</b> · sobrantes <b class="text-violet-700">${c.no_catalogados || 0}</b></div>
        ${cerrada ? '<button id="btn-reabrir" class="btn btn-secondary text-sm mt-2">Reabrir calle</button>' : ''}
      </div>
      <div id="regs-calle" class="border-t border-slate-100 max-h-72 overflow-y-auto">${cargarRegs ? cargando() : ''}</div>`;
    $('#cerrar-panel').onclick = () => { calleSel = null; panel.classList.add('hidden'); pintarPlano(); };
    if (cerrada) {
      $('#btn-reabrir').onclick = accion($('#btn-reabrir'), async () => {
        if (!await confirmar('Reabrir calle', `La calle ${esc(c.codigo)} volverá a estado "en proceso" para recontar.`, { ok: 'Reabrir' })) return;
        await api(`/inventario/calles/${c.id}/reabrir`, { method: 'POST' });
        toast('Calle reabierta', 'ok');
      });
    }
    const regs = await api(`/inventario/calles/${id}/registros`, { params: { limit: 100 } });
    const cont = $('#regs-calle');
    if (!cont) return;
    cont.innerHTML = regs.length ? `<table class="tabla"><thead><tr><th>Paquete</th><th class="text-right">Cont./Esp.</th><th>Estado</th></tr></thead><tbody>
      ${regs.map(r => `<tr><td class="font-mono text-xs">${esc(r.numero_de_paquete)}<div class="text-slate-400">${esc(r.usuario)}</div></td>
        <td class="text-right">${num(r.cantidad_contada)} / ${num(r.cantidad_esperada)}</td><td>${badgeConteo(r.estado)}</td></tr>`).join('')}
      </tbody></table>` : vacio('Sin conteos');
  }

  async function cargarLayout() {
    desconectar();
    calleSel = null;
    $('#panel-calle').classList.add('hidden');
    $('#plano').innerHTML = cargando();
    [detalle] = await Promise.all([api(`/layouts/${idLayout}`), api(`/layouts/${idLayout}/avance`).then(kpis)]);
    pintarPlano();
    conectar();
  }

  $('#sel-layout').onchange = (e) => { idLayout = Number(e.target.value); layoutRecordado.set(idLayout); cargarLayout(); };
  await cargarLayout();

  return () => { cerrado = true; desconectar(); };
}
