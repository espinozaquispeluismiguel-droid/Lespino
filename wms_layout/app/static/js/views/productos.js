// Administración: carga masiva del maestro de productos desde Excel.
import { api } from '../api.js';
import { $, accion, cargando, esc, layoutRecordado, num, selectorLayout, toast, vacio } from '../ui.js';

export async function render(el) {
  el.innerHTML = cargando();
  const layouts = await api('/layouts');
  if (!layouts.length) { el.innerHTML = `<div class="card">${vacio('Primero crea un layout en la sección Layouts.')}</div>`; return; }
  const idIni = layouts.some(l => l.id === layoutRecordado.get()) ? layoutRecordado.get() : layouts[0].id;

  el.innerHTML = `
    <div class="flex flex-wrap items-center gap-3 mb-4">
      <h1 class="text-xl font-bold mr-auto">Maestro de productos</h1>
      <button id="btn-plantilla" class="btn btn-secondary">⬇ Descargar plantilla</button>
    </div>
    <div class="grid lg:grid-cols-3 gap-4">
      <form id="f-import" class="card p-5 space-y-4">
        <h2 class="font-semibold">Importar Excel</h2>
        <div><label class="label">Layout destino</label>${selectorLayout(layouts, idIni)}</div>
        <label id="zona" class="block border-2 border-dashed border-slate-300 rounded-xl p-6 text-center cursor-pointer hover:border-marca-600 transition">
          <input id="in-archivo" type="file" accept=".xlsx,.xlsm" class="hidden" required>
          <div class="text-3xl mb-1">📄</div>
          <div id="nombre-archivo" class="text-sm text-slate-600">Haz clic o arrastra aquí el archivo .xlsx</div>
        </label>
        <div><label class="label">Modo</label>
          <select id="in-modo" class="input">
            <option value="upsert">Añadir y actualizar</option>
            <option value="reemplazar">Reemplazar (inactiva los que no vengan en el archivo)</option>
          </select></div>
        <label class="flex items-center gap-2 text-sm"><input id="in-dry" type="checkbox" checked> Solo validar (no guarda cambios)</label>
        <label class="flex items-center gap-2 text-sm"><input id="in-parcial" type="checkbox" checked> Guardar las filas válidas aunque haya errores</label>
        <button id="btn-importar" class="btn btn-primary w-full py-3">Validar archivo</button>
        <p class="text-xs text-slate-500">Columnas: <b>articulo, nombre, numero_de_paquete, cantidad</b> (obligatorias), unidad_de_medida, estado.
          Se aceptan cabeceras como "Nº Paquete", "Descripción" o "UM".</p>
      </form>
      <div class="lg:col-span-2" id="resultado">
        <div class="card">${vacio('Sube un archivo para ver el resultado de la validación.')}</div>
      </div>
    </div>`;

  const inArchivo = $('#in-archivo'), zona = $('#zona');
  const actualizarBoton = () => { $('#btn-importar').textContent = $('#in-dry').checked ? 'Validar archivo' : 'Importar productos'; };
  $('#in-dry').onchange = actualizarBoton;
  inArchivo.onchange = () => { $('#nombre-archivo').innerHTML = inArchivo.files[0] ? `<b>${esc(inArchivo.files[0].name)}</b> · ${num(inArchivo.files[0].size / 1024, 0)} KB` : ''; };
  ['dragover', 'dragenter'].forEach(e => zona.addEventListener(e, ev => { ev.preventDefault(); zona.classList.add('border-marca-600'); }));
  ['dragleave', 'drop'].forEach(e => zona.addEventListener(e, () => zona.classList.remove('border-marca-600')));
  zona.addEventListener('drop', ev => { ev.preventDefault(); inArchivo.files = ev.dataTransfer.files; inArchivo.onchange(); });
  $('#sel-layout').onchange = (e) => layoutRecordado.set(+e.target.value);

  $('#btn-plantilla').onclick = accion($('#btn-plantilla'), async () => {
    const res = await api('/productos/plantilla', { raw: true });
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement('a'), { href: url, download: 'plantilla_productos.xlsx' });
    a.click(); URL.revokeObjectURL(url);
  });

  $('#f-import').onsubmit = accion($('#btn-importar'), async () => {
    if (!inArchivo.files[0]) { toast('Selecciona un archivo', 'aviso'); return; }
    const fd = new FormData();
    fd.append('id_layout', $('#sel-layout').value);
    fd.append('modo', $('#in-modo').value);
    fd.append('dry_run', $('#in-dry').checked);
    fd.append('permitir_parcial', $('#in-parcial').checked);
    fd.append('archivo', inArchivo.files[0]);
    $('#resultado').innerHTML = `<div class="card">${cargando('Procesando archivo…')}</div>`;
    try {
      const r = await api('/productos/importar', { method: 'POST', form: fd });
      pintarResultado(r);
      toast(r.aplicado ? 'Importación completada' : r.dry_run ? 'Validación completada (sin guardar)' : 'Importación revertida por errores',
        r.aplicado ? 'ok' : r.dry_run ? 'info' : 'aviso');
    } catch (e) {
      $('#resultado').innerHTML = `<div class="card p-5 border-l-4 border-red-500 text-red-800">${esc(e.message)}</div>`;
    }
  });

  function pintarResultado(r) {
    const k = (t, v, c = '') => `<div class="card p-4"><div class="text-xs uppercase text-slate-500">${t}</div><div class="text-2xl font-bold ${c}">${v}</div></div>`;
    $('#resultado').innerHTML = `
      <div class="card p-4 mb-4 flex flex-wrap items-center gap-3 ${r.aplicado ? 'border-l-4 border-green-500' : 'border-l-4 border-amber-500'}">
        <div class="font-semibold">${r.aplicado ? 'Cambios guardados' : r.dry_run ? 'Simulación: no se guardó nada' : 'No se guardó nada (hubo errores)'}</div>
        <div class="text-sm text-slate-500">${esc(r.archivo)} · ${r.total_filas} filas · ${r.duracion_ms} ms</div>
        ${r.dry_run && r.filas_validas ? '<button id="btn-confirmar" class="btn btn-primary ml-auto">Importar ahora</button>' : ''}
      </div>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        ${k('Nuevos', r.insertados, 'text-green-700')}${k('Actualizados', r.actualizados, 'text-blue-700')}
        ${k('Sin cambios', r.sin_cambios)}${k('Inactivados', r.inactivados, 'text-slate-500')}${k('Con error', r.filas_con_error, r.filas_con_error ? 'text-red-700' : '')}
      </div>
      ${r.errores.length ? `<div class="card overflow-hidden"><div class="px-4 py-3 border-b border-slate-100 font-semibold">Filas con error${r.errores_truncados ? ' (primeras 500)' : ''}</div>
        <div class="max-h-[50vh] overflow-y-auto"><table class="tabla"><thead><tr><th>Fila</th><th>Paquete</th><th>Errores</th></tr></thead><tbody>
        ${r.errores.map(e => `<tr><td>${e.fila}</td><td class="font-mono text-xs">${esc(e.numero_de_paquete || '—')}</td><td class="text-red-700 text-xs">${e.errores.map(esc).join('<br>')}</td></tr>`).join('')}
        </tbody></table></div></div>` : ''}`;
    $('#btn-confirmar')?.addEventListener('click', () => { $('#in-dry').checked = false; actualizarBoton(); $('#f-import').requestSubmit(); });
  }
}
