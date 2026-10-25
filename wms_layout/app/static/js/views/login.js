import { login } from '../api.js';
import { $, esc } from '../ui.js';

const INICIO = { operario: '#/operario', supervisor: '#/dashboard', administrador: '#/dashboard' };

export async function render(el) {
  el.innerHTML = `
    <div class="min-h-[80vh] flex items-center justify-center">
      <div class="w-full max-w-sm">
        <div class="text-center mb-6">
          <div class="inline-flex w-14 h-14 rounded-2xl bg-marca-600 text-white items-center justify-center text-2xl font-bold mb-3">W</div>
          <h1 class="text-2xl font-bold">WMS · Inventario</h1>
          <p class="text-slate-500 text-sm">Gestión de layouts y conteo por paquete</p>
        </div>
        <form id="f-login" class="card p-6 space-y-4">
          <div>
            <label class="label" for="u">Usuario</label>
            <input id="u" class="input" autocomplete="username" autocapitalize="none" required autofocus>
          </div>
          <div>
            <label class="label" for="p">Contraseña</label>
            <input id="p" type="password" class="input" autocomplete="current-password" required>
          </div>
          <div id="err" class="hidden text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2"></div>
          <button id="btn-entrar" class="btn btn-primary w-full py-3">Entrar</button>
        </form>
      </div>
    </div>`;

  $('#f-login').onsubmit = async (ev) => {
    ev.preventDefault();
    const btn = $('#btn-entrar');
    btn.disabled = true;
    $('#err').classList.add('hidden');
    try {
      const r = await login($('#u').value.trim(), $('#p').value);
      location.hash = INICIO[r.rol] || '#/';
    } catch (e) {
      $('#err').innerHTML = esc(e.message) + (e.body?.error ? `<div class="text-xs mt-1 opacity-75 font-mono break-all">${esc(e.body.error)}</div>` : '');
      $('#err').classList.remove('hidden');
    } finally {
      btn.disabled = false;
    }
  };
}
