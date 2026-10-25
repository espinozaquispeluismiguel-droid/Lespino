// Cliente HTTP: añade el JWT, normaliza errores y redirige al login si la sesión caduca.
const BASE = '/api/v1';
const K_TOKEN = 'wms_token';
const K_USER = 'wms_user';

function leer(k) { try { return localStorage.getItem(k); } catch { return null; } }
function escribir(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* modo privado */ } }

export const sesion = {
  get token() { return leer(K_TOKEN); },
  get usuario() { try { return JSON.parse(leer(K_USER) || 'null'); } catch { return null; } },
  guardar(token, usuario) { escribir(K_TOKEN, token); escribir(K_USER, JSON.stringify(usuario)); },
  cerrar() { escribir(K_TOKEN, null); escribir(K_USER, null); },
};

export class ApiError extends Error {
  constructor(status, body) {
    const det = body?.detail;
    const msg = typeof det === 'string' ? det
      : Array.isArray(det) ? det.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join(' · ')
      : `Error ${status}`;
    super(msg);
    this.status = status;
    this.body = body;
    this.codigo = body?.codigo;
    this.contexto = body?.contexto;
  }
}

export async function api(ruta, { method = 'GET', json, form, params, raw = false } = {}) {
  let url = BASE + ruta;
  if (params) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') q.append(k, v); });
    if ([...q].length) url += '?' + q;
  }
  const headers = {};
  if (sesion.token) headers.Authorization = `Bearer ${sesion.token}`;
  let body;
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
  else if (form) body = form;

  const res = await fetch(url, { method, headers, body });
  if (res.status === 401 && !ruta.startsWith('/auth/login')) {
    sesion.cerrar();
    location.hash = '#/login';
    throw new ApiError(401, { detail: 'Sesión expirada' });
  }
  if (raw) { if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => ({}))); return res; }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export async function login(username, password) {
  const form = new URLSearchParams({ username, password });
  const res = await fetch(BASE + '/auth/login', { method: 'POST', body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data);
  sesion.guardar(data.access_token, { id: data.id_usuario, nombre: data.nombre, rol: data.rol });
  return data;
}

export function wsUrl(idLayout) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws/layouts/${idLayout}?token=${encodeURIComponent(sesion.token)}`;
}
