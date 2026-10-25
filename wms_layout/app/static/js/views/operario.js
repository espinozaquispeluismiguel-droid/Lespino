import { api } from '../api.js';
import { badgeCalle, cargando, esc, vacio } from '../ui.js';

export async function render(el) {
  el.innerHTML = `
    <div class="max-w-2xl mx-auto">
      <h1 class="text-xl font-bold mb-1">Mis calles</h1>
      <p class="text-sm text-slate-500 mb-4">Elige una calle para empezar a contar.</p>
      <div id="lista">${cargando()}</div>
    </div>`;
  const calles = await api('/inventario/mis-calles');
  const lista = el.querySelector('#lista');
  if (!calles.length) {
    lista.innerHTML = `<div class="card">${vacio('No tienes calles asignadas. Pide a tu supervisor que te asigne una.')}</div>`;
    return;
  }
  const porLayout = Object.groupBy ? Object.groupBy(calles, c => c.layout)
    : calles.reduce((m, c) => ((m[c.layout] ||= []).push(c), m), {});
  lista.innerHTML = Object.entries(porLayout).map(([layout, cs]) => `
    <h2 class="text-xs uppercase tracking-wide text-slate-500 font-medium mt-5 mb-2">${esc(layout)}</h2>
    <div class="grid gap-3">
      ${cs.map(c => `
        <a href="#/operario/calle/${c.id_calle}" class="card p-4 flex items-center gap-4 hover:border-marca-600 transition">
          <div class="w-14 h-14 rounded-xl bg-marca-50 text-marca-700 font-bold text-lg flex items-center justify-center">${esc(c.codigo)}</div>
          <div class="flex-1 min-w-0">
            <div class="font-medium">Calle ${esc(c.codigo)} <span class="text-slate-400 font-normal">· ${esc(c.area)}</span></div>
            <div class="text-sm text-slate-500">${c.paquetes_contados} paquetes contados${c.equipo ? ` · ${esc(c.equipo)}` : ''}</div>
          </div>
          ${badgeCalle(c.estado)}
          <span class="text-slate-300 text-xl">›</span>
        </a>`).join('')}
    </div>`).join('');
}
