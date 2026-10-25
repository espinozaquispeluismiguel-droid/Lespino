// Vista operario: captura de paquetes (manual, QR/barras, foto IA) con validación inmediata.
import { api, sesion } from '../api.js';
import {
  $, $$, ESTADO_CONTEO, METODO, accion, badgeCalle, badgeConteo, cargando, confirmar, esc, hora, num, toast, vacio,
} from '../ui.js';

const LIB_QR = 'vendor/html5-qrcode.min.js'; // v2.3.8, incluida localmente (sin CDN)

function cargarScript(src) {
  return new Promise((ok, ko) => {
    if (document.querySelector(`script[src="${src}"]`)) return ok();
    const s = document.createElement('script');
    s.src = src; s.onload = ok; s.onerror = () => ko(new Error('No se pudo cargar el lector de códigos'));
    document.head.appendChild(s);
  });
}

/** El QR puede traer solo el nº de paquete o un JSON {"numero_de_paquete":..., "cantidad":...}. */
function interpretarCodigo(texto) {
  try {
    const o = JSON.parse(texto);
    if (o && typeof o === 'object') {
      return { numero: o.numero_de_paquete || o.paquete || o.pkg || '', cantidad: o.cantidad ?? o.qty ?? null,
               articulo: o.articulo || null };
    }
  } catch { /* texto plano */ }
  return { numero: texto.trim(), cantidad: null };
}

export async function render(el, idCalle) {
  idCalle = Number(idCalle);
  const esOperario = sesion.usuario?.rol === 'operario';
  let metodo = 'manual';
  let ocrConfianza = null;
  let lector = null;

  el.innerHTML = cargando();
  const mias = await api('/inventario/mis-calles');
  const info = mias.find(c => c.id_calle === idCalle);

  el.innerHTML = `
    <div class="max-w-2xl mx-auto space-y-4">
      <div class="flex items-center gap-3">
        <a href="#/operario" class="btn btn-secondary px-3" aria-label="Volver">‹</a>
        <div class="flex-1 min-w-0">
          <h1 class="text-xl font-bold leading-tight">Calle ${esc(info?.codigo ?? idCalle)}</h1>
          <div class="text-sm text-slate-500">${esc(info ? `${info.layout} · ${info.area}` : '')}</div>
        </div>
        <span id="estado-calle">${info ? badgeCalle(info.estado) : ''}</span>
      </div>

      <div class="card overflow-hidden">
        <div class="flex border-b border-slate-200" role="tablist">
          <button class="tab active" data-m="manual">Manual</button>
          <button class="tab" data-m="qr">Escanear</button>
          <button class="tab" data-m="foto_ia">Foto</button>
        </div>

        <div id="panel-qr" class="hidden p-4 border-b border-slate-100">
          <div id="lector" class="max-w-sm mx-auto"></div>
          <p class="text-xs text-slate-500 text-center mt-2">Apunta la cámara al código QR o de barras del paquete.</p>
        </div>

        <div id="panel-foto" class="hidden p-4 border-b border-slate-100 text-center">
          <label class="btn btn-secondary cursor-pointer">
            📷 Tomar foto de la etiqueta
            <input id="in-foto" type="file" accept="image/*" capture="environment" class="hidden">
          </label>
          <p id="foto-estado" class="text-xs text-slate-500 mt-2">Se leerán los datos y podrás revisarlos antes de registrar.</p>
        </div>

        <form id="f-paquete" class="p-4 space-y-4" autocomplete="off">
          <div>
            <label class="label" for="in-paquete">Nº de paquete</label>
            <input id="in-paquete" class="input text-lg font-mono uppercase" required maxlength="80"
                   placeholder="Escanea o escribe" autofocus inputmode="text">
          </div>
          <div>
            <label class="label" for="in-cantidad">Cantidad contada</label>
            <input id="in-cantidad" class="input text-lg" type="number" min="0" step="0.001" required inputmode="decimal">
          </div>
          <details class="text-sm">
            <summary class="cursor-pointer text-slate-500">Datos adicionales (solo si el paquete no está en el maestro)</summary>
            <div class="grid sm:grid-cols-2 gap-3 mt-3">
              <div><label class="label">Artículo</label><input id="in-articulo" class="input" maxlength="60"></div>
              <div><label class="label">Unidad</label><input id="in-um" class="input" maxlength="20" placeholder="UND"></div>
              <div class="sm:col-span-2"><label class="label">Nombre / descripción</label><input id="in-nombre" class="input" maxlength="255"></div>
              <div class="sm:col-span-2"><label class="label">Observaciones</label><input id="in-obs" class="input"></div>
            </div>
          </details>
          <div class="flex items-center gap-2 text-xs text-slate-500">
            Método: <span id="lbl-metodo" class="badge bg-slate-100 text-slate-700">Manual</span>
          </div>
          <button id="btn-registrar" class="btn btn-primary w-full py-3 text-base">Registrar paquete</button>
        </form>
      </div>

      <div id="resultado"></div>

      <div class="card">
        <div class="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <h2 class="font-semibold">Contados en esta calle <span id="n-reg" class="text-slate-400 font-normal"></span></h2>
          <button id="btn-finalizar" class="btn btn-ghost text-sm whitespace-nowrap">Finalizar calle</button>
        </div>
        <div id="registros">${cargando()}</div>
      </div>
    </div>`;

  const inPaquete = $('#in-paquete'), inCantidad = $('#in-cantidad');

  function fijarMetodo(m) {
    metodo = m;
    $('#lbl-metodo').textContent = METODO[m];
  }

  async function pararLector() {
    if (lector) { try { await lector.stop(); lector.clear(); } catch { /* */ } lector = null; }
  }

  async function iniciarLector() {
    try {
      await cargarScript(LIB_QR);
      lector = new window.Html5Qrcode('lector');
      await lector.start({ facingMode: 'environment' }, { fps: 10, qrbox: { width: 250, height: 160 } }, async (texto) => {
        const d = interpretarCodigo(texto);
        if (!d.numero) return;
        navigator.vibrate?.(80);
        inPaquete.value = d.numero;
        if (d.cantidad != null) inCantidad.value = d.cantidad;
        if (d.articulo) $('#in-articulo').value = d.articulo;
        fijarMetodo('qr');
        await pararLector();
        inCantidad.focus();
        toast(`Código leído: ${d.numero}`, 'ok', 2000);
      });
    } catch (e) {
      const msg = String(e?.message || e);
      $('#lector').innerHTML = `<div class="text-sm text-red-700 bg-red-50 rounded-lg p-3">
        No se pudo abrir la cámara: ${esc(msg)}.<br>
        <span class="text-slate-600">La cámara solo funciona en <b>https://</b> o en <b>localhost</b>. Puedes usar un lector USB/Bluetooth en la pestaña Manual.</span></div>`;
    }
  }

  $$('.tab').forEach(t => t.onclick = async () => {
    $$('.tab').forEach(x => x.classList.toggle('active', x === t));
    const m = t.dataset.m;
    $('#panel-qr').classList.toggle('hidden', m !== 'qr');
    $('#panel-foto').classList.toggle('hidden', m !== 'foto_ia');
    fijarMetodo(m);
    if (m === 'qr') await iniciarLector(); else await pararLector();
    if (m === 'manual') inPaquete.focus();
  });

  // Si el usuario escribe a mano después de escanear, vuelve a "manual"
  inPaquete.addEventListener('input', () => { if (metodo === 'qr') fijarMetodo('manual'); });

  $('#in-foto').onchange = async (ev) => {
    const archivo = ev.target.files[0];
    if (!archivo) return;
    const est = $('#foto-estado');
    est.textContent = 'Leyendo etiqueta…';
    try {
      const fd = new FormData(); fd.append('foto', archivo);
      const d = await api('/inventario/ocr', { method: 'POST', form: fd });
      if (d.numero_de_paquete) inPaquete.value = d.numero_de_paquete;
      if (d.cantidad != null) inCantidad.value = d.cantidad;
      if (d.articulo) $('#in-articulo').value = d.articulo;
      if (d.unidad_de_medida) $('#in-um').value = d.unidad_de_medida;
      ocrConfianza = d.confianza;
      fijarMetodo('foto_ia');
      est.innerHTML = d.numero_de_paquete
        ? `Leído con ${num(d.confianza, 0)}% de confianza${d.producto_encontrado ? ` · <b>${esc(d.nombre_catalogo)}</b>` : ' · no está en el maestro'}. <b>Revisa los datos y registra.</b>`
        : 'No se encontró el nº de paquete en la foto. Escríbelo a mano.';
      inCantidad.focus();
    } catch (e) {
      est.textContent = e.status === 501 ? 'El OCR no está instalado en el servidor (Tesseract).' : e.message;
    } finally { ev.target.value = ''; }
  };

  function mostrarResultado(r) {
    const e = ESTADO_CONTEO[r.estado];
    const detalle = r.cantidad_esperada != null
      ? `Contado ${num(r.cantidad_contada)} · esperado ${num(r.cantidad_esperada)} · diferencia ${num(r.diferencia)}`
      : `Contado ${num(r.cantidad_contada)} ${esc(r.unidad_de_medida || '')}`;
    $('#resultado').innerHTML = `
      <div class="card border-l-4 ${e.card} p-4 flex gap-4 items-start feed-item">
        <div class="w-10 h-10 rounded-full bg-white flex items-center justify-center font-bold text-lg shrink-0">${e.icono}</div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-mono font-semibold">${esc(r.numero_de_paquete)}</span>${badgeConteo(r.estado)}
            ${r.es_reconteo ? '<span class="badge bg-slate-200 text-slate-700">Reconteo</span>' : ''}
          </div>
          <div class="text-sm mt-1">${esc(r.mensaje)}</div>
          <div class="text-xs text-slate-500 mt-1">${esc(r.nombre || '')} ${r.nombre ? '·' : ''} ${detalle}</div>
          <div class="text-xs text-slate-500 mt-1">Avance del layout: ${r.avance.contados}/${r.avance.total_catalogados} (${num(r.avance.porcentaje_avance, 1)}%)</div>
        </div>
      </div>`;
  }

  function mostrarDuplicado(err, payload) {
    const c = err.contexto || {};
    $('#resultado').innerHTML = `
      <div class="card border-l-4 border-red-500 bg-red-50 p-4 feed-item">
        <div class="font-semibold text-red-800">Este paquete ya fue contado</div>
        <div class="text-sm mt-1">Calle <b>${esc(c.codigo_calle)}</b> · ${esc(c.usuario)} · ${num(c.cantidad_contada)} uds · ${hora(c.fecha_registro)}</div>
        <div class="flex gap-2 mt-3">
          <button id="btn-reconteo" class="btn btn-primary text-sm">Sustituir por este conteo</button>
          <button id="btn-cancelar-dup" class="btn btn-secondary text-sm">Cancelar</button>
        </div>
      </div>`;
    $('#btn-cancelar-dup').onclick = () => { $('#resultado').innerHTML = ''; limpiarForm(); };
    $('#btn-reconteo').onclick = accion($('#btn-reconteo'), () => enviar({ ...payload, reconteo: true }));
  }

  function limpiarForm() {
    $('#f-paquete').reset();
    ocrConfianza = null;
    if (metodo !== 'manual') fijarMetodo(metodo);
    inPaquete.focus();
  }

  async function enviar(payload) {
    try {
      const r = await api('/inventario/registrar', { method: 'POST', json: payload });
      navigator.vibrate?.(r.coincide ? 60 : [80, 60, 80]);
      mostrarResultado(r);
      $('#estado-calle').innerHTML = badgeCalle(r.estado_calle);
      limpiarForm();
      await cargarRegistros();
      if (metodo === 'qr') await iniciarLector();
    } catch (e) {
      if (e.codigo === 'paquete_ya_contado') return mostrarDuplicado(e, payload);
      throw e;
    }
  }

  $('#f-paquete').onsubmit = accion($('#btn-registrar'), () => {
    const v = (id) => $(id).value.trim() || null;
    return enviar({
      id_calle: idCalle,
      numero_de_paquete: inPaquete.value.trim(),
      cantidad_contada: inCantidad.value,
      metodo_ingreso: metodo,
      articulo: v('#in-articulo'), nombre: v('#in-nombre'), unidad_de_medida: v('#in-um'), observaciones: v('#in-obs'),
      ocr_confianza: metodo === 'foto_ia' ? ocrConfianza : null,
    });
  });

  async function cargarRegistros() {
    const cont = $('#registros');
    try {
      const regs = await api(`/inventario/calles/${idCalle}/registros`);
      $('#n-reg').textContent = `(${regs.length})`;
      if (!regs.length) { cont.innerHTML = vacio('Aún no hay paquetes contados en esta calle.'); return; }
      cont.innerHTML = `<ul class="divide-y divide-slate-100">${regs.map(r => `
        <li class="px-4 py-3 flex items-center gap-3">
          <div class="flex-1 min-w-0">
            <div class="font-mono text-sm font-medium truncate">${esc(r.numero_de_paquete)}</div>
            <div class="text-xs text-slate-500 truncate">${esc(r.nombre || r.articulo || '—')} · ${esc(METODO[r.metodo_ingreso])} · ${hora(r.fecha_registro)}${esOperario ? '' : ` · ${esc(r.usuario)}`}</div>
          </div>
          <div class="text-right">
            <div class="font-semibold">${num(r.cantidad_contada)}${r.cantidad_esperada != null ? `<span class="text-slate-400 font-normal"> / ${num(r.cantidad_esperada)}</span>` : ''}</div>
            ${badgeConteo(r.estado)}
          </div>
        </li>`).join('')}</ul>`;
    } catch (e) {
      cont.innerHTML = `<div class="p-4 text-sm text-red-700">${esc(e.message)}</div>`;
    }
  }

  $('#btn-finalizar').onclick = accion($('#btn-finalizar'), async () => {
    const ok = await confirmar('Finalizar calle', 'Se cerrará el conteo de esta calle. Para volver a contar, un supervisor tendrá que reabrirla.', { ok: 'Finalizar' });
    if (!ok) return;
    const r = await api(`/inventario/calles/${idCalle}/finalizar`, { method: 'POST' });
    $('#estado-calle').innerHTML = badgeCalle(r.estado);
    toast(r.estado === 'verificada' ? 'Calle verificada sin incidencias' : `Calle cerrada con ${r.diferencias} diferencias y ${r.no_catalogados} sobrantes`,
      r.estado === 'verificada' ? 'ok' : 'aviso', 5000);
  });

  await cargarRegistros();
  return () => pararLector();
}
