// Map overlays drawn on top of the static layer every frame. The getters read the page's current state.
import type { Overlay } from '../mapview';
import type { Factory, Pin } from '../types';
import type { Draft } from './draw';
import { C, fmtDist } from '../fmt';

/** Heat map of machines missing input (stopped, output not full): yellow for low, red for high density */
export function heatOverlay(getFactory: () => Factory | null): Overlay {
  let heatKey = '', heatCv: HTMLCanvasElement | null = null, heatBox = { x: 0, y: 0, k: 1 };
  return { key: 'heat', layer: 'heat', draw: (c, v) => {
    const f = getFactory();
    const ms = (f?.machines || []).filter(m => m.state === 'stopped' && m.block !== 'full');
    if (!ms.length) return;
    // render the heat map in world coordinates once per data snapshot (4 m/px), then just draw it scaled
    const key = (f?.at || 0) + ':' + ms.length;
    if (key !== heatKey) {
      heatKey = key;
      const xs = ms.map(m => m.pos[0]), ys = ms.map(m => m.pos[1]), pad = 120, res = 4;
      const x0 = Math.min(...xs) - pad, y0 = Math.min(...ys) - pad;
      const w = Math.ceil((Math.max(...xs) + pad - x0) / res), h = Math.ceil((Math.max(...ys) + pad - y0) / res);
      heatCv = document.createElement('canvas'); heatCv.width = w; heatCv.height = h;
      const hc = heatCv.getContext('2d')!;
      for (const m of ms) {
        const px = (m.pos[0] - x0) / res, py = (m.pos[1] - y0) / res, r = 40 / res;
        const g = hc.createRadialGradient(px, py, 0, px, py, r);
        g.addColorStop(0, 'rgba(0,0,0,.22)'); g.addColorStop(1, 'rgba(0,0,0,0)');
        hc.fillStyle = g; hc.fillRect(px - r, py - r, 2 * r, 2 * r);
      }
      // density (alpha) → colour: yellow for low, red for high
      const img = hc.getImageData(0, 0, w, h), d = img.data;
      for (let i = 0; i < d.length; i += 4) {
        const a = d[i + 3] / 255; if (!a) continue;
        const t = Math.min(1, a * 1.6);
        d[i] = 229; d[i + 1] = Math.round(185 - 113 * t); d[i + 2] = Math.round(59 + 18 * t); d[i + 3] = Math.round(Math.min(.75, a * 1.4) * 255);
      }
      hc.putImageData(img, 0, 0);
      heatBox = { x: x0, y: y0, k: res };
    }
    if (heatCv) c.drawImage(heatCv, v.sx(heatBox.x), v.sy(heatBox.y), heatCv.width * heatBox.k * v.k, heatCv.height * heatBox.k * v.k);
  } };
}

/** Measuring: dashed polyline, points, length label per segment */
export function measureOverlay(getPts: () => number[][] | null): Overlay {
  return { key: 'measure', layer: 'measure', draw: (c, v) => {
    const m = getPts(); if (!m || !m.length) return;
    c.strokeStyle = C.accent; c.lineWidth = 2; c.setLineDash([8, 5]); c.beginPath();
    m.forEach((q, i) => (i ? c.lineTo : c.moveTo).call(c, v.sx(q[0]), v.sy(q[1])));
    c.stroke(); c.setLineDash([]);
    c.font = '600 12px "Barlow Condensed", sans-serif'; c.textAlign = 'center';
    for (let i = 0; i < m.length; i++) {
      const x = v.sx(m[i][0]), y = v.sy(m[i][1]);
      c.fillStyle = C.accent; c.beginPath(); c.arc(x, y, 4, 0, Math.PI * 2); c.fill();
      if (i) {                                         // label the segment length at its midpoint
        const d = Math.hypot(m[i][0] - m[i - 1][0], m[i][1] - m[i - 1][1]);
        const mx = (x + v.sx(m[i - 1][0])) / 2, my = (y + v.sy(m[i - 1][1])) / 2;
        c.strokeStyle = 'rgba(12,13,14,.9)'; c.lineWidth = 3.5; const t = fmtDist(d);
        c.strokeText(t, mx, my - 6); c.fillStyle = C.light; c.fillText(t, mx, my - 6);
      }
    }
  } };
}

/** Player trails: [t, x, y] per player, older segments fainter (gone after 2 h) */
export function trailsOverlay(getTrails: () => Record<string, number[][]>): Overlay {
  return { key: 'trails', layer: 'trails', draw: (c, v) => {
    const T = getTrails(); c.lineWidth = 2; c.lineJoin = 'round';
    for (const n in T) {
      const pts = T[n]; if (pts.length < 2) continue;
      const now = Date.now() / 1000;
      for (let i = 1; i < pts.length; i++) {
        c.globalAlpha = Math.max(.12, 1 - (now - pts[i][0]) / 7200) * .8;
        c.strokeStyle = C.accent; c.beginPath();
        c.moveTo(v.sx(pts[i - 1][1]), v.sy(pts[i - 1][2])); c.lineTo(v.sx(pts[i][1]), v.sy(pts[i][2])); c.stroke();
      }
    }
    c.globalAlpha = 1;
  } };
}

/** Line/area notes (point notes are map objects) plus the note currently being drawn */
export function pinsOverlay(getPins: () => Pin[], getDraft: () => Draft | null): Overlay {
  return { key: 'pins', layer: 'pins', draw: (c, v) => {
    for (const p of getPins()) {
      if (p.shape === 'point') continue;
      c.strokeStyle = p.color; c.fillStyle = p.color; c.lineWidth = 2.5; c.beginPath();
      p.geom.forEach((q, i) => (i ? c.lineTo : c.moveTo).call(c, v.sx(q[0]), v.sy(q[1])));
      if (p.shape === 'area') { c.closePath(); c.globalAlpha = .15; c.fill(); c.globalAlpha = 1; c.setLineDash([6, 4]); }
      c.stroke(); c.setLineDash([]);
    }
    const draw = getDraft();
    if (draw && draw.pts.length) {
      c.strokeStyle = C.light; c.lineWidth = 2; c.setLineDash([4, 4]); c.beginPath();
      draw.pts.forEach((q, i) => (i ? c.lineTo : c.moveTo).call(c, v.sx(q[0]), v.sy(q[1])));
      if (draw.shape === 'area' && draw.pts.length > 2) c.closePath();
      c.stroke(); c.setLineDash([]);
      for (const q of draw.pts) { c.fillStyle = C.light; c.fillRect(v.sx(q[0]) - 3, v.sy(q[1]) - 3, 6, 6); }
    }
  } };
}
