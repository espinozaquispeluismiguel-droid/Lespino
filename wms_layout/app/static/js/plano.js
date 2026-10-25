// Renderiza el plano del layout en SVG: áreas como contenedores y calles coloreadas por estado.
import { ESTADO_CALLE, esc } from './ui.js';

const NS = 'http://www.w3.org/2000/svg';

function cajaArea(area) {
  const cs = area.calles.filter(c => c.coord_x != null && c.coord_y != null);
  if (!cs.length) {
    const x = area.coord_x ?? 0, y = area.coord_y ?? 0;
    return { x, y, w: 60, h: 40 };
  }
  const x0 = Math.min(...cs.map(c => c.coord_x)) - 4;
  const y0 = Math.min(...cs.map(c => c.coord_y)) - 10;
  const x1 = Math.max(...cs.map(c => c.coord_x + (c.ancho || 8))) + 4;
  const y1 = Math.max(...cs.map(c => c.coord_y + (c.alto || 40))) + 4;
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/**
 * @param {HTMLElement} cont
 * @param {object} detalle  respuesta de GET /layouts/{id}
 * @param {object} opts { seleccion:Set, onClick(calle), arrastrable, onMover(calle,x,y), etiqueta(calle) }
 */
export function renderPlano(cont, detalle, opts = {}) {
  const { seleccion = new Set(), onClick, arrastrable = false, onMover, etiqueta } = opts;
  const areas = detalle.areas || [];
  if (!areas.some(a => a.calles.length)) {
    cont.innerHTML = `<div class="text-center text-slate-500 text-sm py-12">Este layout aún no tiene calles.</div>`;
    return;
  }
  const cajas = areas.map(cajaArea);
  const minX = Math.min(...cajas.map(b => b.x)) - 6;
  const minY = Math.min(...cajas.map(b => b.y)) - 6;
  const maxX = Math.max(...cajas.map(b => b.x + b.w)) + 6;
  const maxY = Math.max(...cajas.map(b => b.y + b.h)) + 6;

  let svg = `<svg xmlns="${NS}" viewBox="${minX} ${minY} ${maxX - minX} ${maxY - minY}" role="img" aria-label="Plano del layout">`;
  areas.forEach((a, i) => {
    const b = cajas[i];
    const color = a.color || '#64748b';
    svg += `<g class="area"><rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" rx="2"
      fill="${esc(color)}" fill-opacity=".06" stroke="${esc(color)}" stroke-opacity=".6" stroke-width=".4" stroke-dasharray="2 1"/>
      <text x="${b.x + 2}" y="${b.y + 6}" font-size="4.5" font-weight="600" fill="${esc(color)}">${esc(a.nombre)}</text></g>`;
    a.calles.forEach(c => {
      if (c.coord_x == null) return;
      const w = c.ancho || 8, h = c.alto || 40;
      const vertical = h > w * 1.5;
      const fs = Math.max(2.2, Math.min(w, h) * 0.38);
      const cx = c.coord_x + w / 2, cy = c.coord_y + h / 2;
      const est = ESTADO_CALLE[c.estado] || ESTADO_CALLE.pendiente;
      const extra = etiqueta ? etiqueta(c) : '';
      svg += `<g class="calle ${seleccion.has(c.id) ? 'sel' : ''}" data-id="${c.id}">
        <title>${esc(c.codigo)} · ${esc(est.txt)}${c.paquetes_contados != null ? ` · ${c.paquetes_contados} paq.` : ''}${c.asignacion ? ` · ${esc(c.asignacion.usuario || c.asignacion.equipo)}` : ''}</title>
        <rect x="${c.coord_x}" y="${c.coord_y}" width="${w}" height="${h}" rx="1" fill="${est.fill}" stroke="#475569" stroke-width=".3"/>
        <text x="${cx}" y="${cy}" font-size="${fs}" font-weight="700" fill="#1e293b" text-anchor="middle" dominant-baseline="central"
          ${vertical ? `transform="rotate(-90 ${cx} ${cy})"` : ''}>${esc(c.codigo)}</text>
        ${extra ? (vertical
          ? `<text x="${cx}" y="${c.coord_y + h - 2}" font-size="${fs * 0.7}" fill="#334155" text-anchor="middle">${esc(extra)}</text>`
          : `<text x="${c.coord_x + w - 1.5}" y="${cy}" font-size="${fs * 0.7}" fill="#334155" text-anchor="end" dominant-baseline="central">${esc(extra)}</text>`) : ''}
      </g>`;
    });
  });
  svg += '</svg>';
  cont.innerHTML = svg;
  cont.classList.toggle('arrastrable', arrastrable);

  const indice = new Map(areas.flatMap(a => a.calles).map(c => [c.id, c]));
  const svgEl = cont.querySelector('svg');

  if (!arrastrable) {
    cont.querySelectorAll('.calle').forEach(g => g.addEventListener('click', () => onClick?.(indice.get(+g.dataset.id))));
    return;
  }

  // Arrastrar calles (modo edición): convierte coordenadas de pantalla a coordenadas del viewBox
  const aSvg = (ev) => { const p = svgEl.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY; return p.matrixTransform(svgEl.getScreenCTM().inverse()); };
  cont.querySelectorAll('.calle').forEach(g => {
    g.addEventListener('pointerdown', (ev) => {
      const calle = indice.get(+g.dataset.id);
      const ini = aSvg(ev), ox = calle.coord_x, oy = calle.coord_y;
      let movido = false;
      g.setPointerCapture(ev.pointerId);
      const mover = (e) => {
        const p = aSvg(e);
        const dx = Math.round(p.x - ini.x), dy = Math.round(p.y - ini.y);
        if (Math.abs(dx) + Math.abs(dy) > 0) movido = true;
        g.setAttribute('transform', `translate(${dx} ${dy})`);
        g._d = [dx, dy];
      };
      const soltar = () => {
        g.removeEventListener('pointermove', mover);
        g.removeEventListener('pointerup', soltar);
        if (movido && g._d) onMover?.(calle, ox + g._d[0], oy + g._d[1]);
        else onClick?.(calle);
      };
      g.addEventListener('pointermove', mover);
      g.addEventListener('pointerup', soltar);
    });
  });
}

export function leyenda() {
  return `<div class="flex flex-wrap gap-3 text-xs text-slate-600">${Object.values(ESTADO_CALLE).map(e =>
    `<span class="inline-flex items-center gap-1.5"><span class="w-3 h-3 rounded-sm border border-slate-400" style="background:${e.fill}"></span>${esc(e.txt)}</span>`).join('')}</div>`;
}
