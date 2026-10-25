// Administración: usuarios de la delegación.
import { api } from '../api.js';
import { $, $$, accion, cargando, esc, fecha, toast } from '../ui.js';

const ROL = { administrador: 'bg-marca-100 text-marca-800', supervisor: 'bg-blue-100 text-blue-800', operario: 'bg-slate-100 text-slate-700' };

export async function render(el) {
  el.innerHTML = `
    <h1 class="text-xl font-bold mb-4">Usuarios</h1>
    <div class="grid lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2 card overflow-hidden"><div class="overflow-x-auto" id="tabla">${cargando()}</div></div>
      <form id="f-usuario" class="card p-5 space-y-3 self-start">
        <h2 class="font-semibold">Nuevo usuario</h2>
        <div><label class="label">Usuario</label><input id="u-user" class="input" required minlength="3" maxlength="60" autocapitalize="none"></div>
        <div><label class="label">Nombre completo</label><input id="u-nombre" class="input" required maxlength="150"></div>
        <div><label class="label">Email</label><input id="u-email" type="email" class="input"></div>
        <div><label class="label">Rol</label><select id="u-rol" class="input">
          <option value="operario">Operario</option><option value="supervisor">Supervisor</option><option value="administrador">Administrador</option></select></div>
        <div><label class="label">Contraseña inicial</label><input id="u-pass" type="password" class="input" required minlength="8" autocomplete="new-password"></div>
        <button id="btn-u" class="btn btn-primary w-full">Crear usuario</button>
      </form>
    </div>`;

  async function cargar() {
    const us = await api('/usuarios');
    $('#tabla').innerHTML = `<table class="tabla"><thead><tr><th>Usuario</th><th>Nombre</th><th>Rol</th><th>Estado</th><th>Último acceso</th><th></th></tr></thead><tbody>
      ${us.map(u => `<tr>
        <td class="font-mono text-xs">${esc(u.username)}</td><td>${esc(u.nombre_completo)}</td>
        <td><span class="badge ${ROL[u.rol]}">${esc(u.rol)}</span></td>
        <td>${u.bloqueado ? '<span class="badge bg-red-100 text-red-800">Bloqueado</span>' : u.activo ? '<span class="badge bg-green-100 text-green-800">Activo</span>' : '<span class="badge bg-slate-200">Inactivo</span>'}</td>
        <td class="text-xs">${fecha(u.ultimo_acceso)}</td>
        <td class="text-right">${u.bloqueado ? `<button class="btn-ghost text-xs px-2 py-1 rounded desbloquear" data-id="${u.id}">Desbloquear</button>` : ''}</td>
      </tr>`).join('')}</tbody></table>`;
    $$('.desbloquear').forEach(b => b.onclick = accion(b, async () => {
      await api(`/usuarios/${b.dataset.id}/desbloquear`, { method: 'POST' }); toast('Usuario desbloqueado', 'ok'); await cargar();
    }));
  }

  $('#f-usuario').onsubmit = accion($('#btn-u'), async () => {
    await api('/usuarios', { method: 'POST', json: {
      username: $('#u-user').value.trim(), nombre_completo: $('#u-nombre').value.trim(),
      email: $('#u-email').value.trim() || null, rol: $('#u-rol').value, password: $('#u-pass').value } });
    $('#f-usuario').reset(); toast('Usuario creado', 'ok'); await cargar();
  });

  await cargar();
}
