// Baut aus den Stores die Kartenobjekte (MapObj/Lines) — getrennt von der Seite, damit Kiosk sie mitnutzt.
import type { MapView, MapObj } from './mapview';
import type { Stations, Live, Factory, Geo, Node, Pin } from './types';
import { C, machineColor } from './fmt';

export const LAYERS: [string, string, boolean][] = [
  ['mapimg', 'Spielkarte', true], ['detail', 'Fundamente & Wände (ab Zoom)', true], ['rails', 'Gleisnetz', true], ['pipes', 'Rohrleitungen', false],
  ['belts', 'Förderbänder', false], ['power', 'Stromleitungen', false],
  ['stations', 'Stationen', true], ['routes', 'Zugrouten', true], ['vehicles', 'Fahrzeuge', true],
  ['players', 'Spieler', true], ['trails', 'Spielerspuren (2 h)', true],
  ['factories', 'Fabriken (Umriss nach Zustand)', true], ['heat', 'Heatmap: Materialmangel', false],
  ['machines', 'Maschinen', false], ['starved', 'Maschinen mit Materialmangel', false],
  ['generators', 'Generatoren', false], ['nopower', 'Ohne Stromanschluss', true], ['nodes', 'Rohstoffknoten', false], ['pins', 'Notizen', true],
  ['c_somersloop', 'Somersloops (fehlend)', false], ['c_mercer', 'Mercer Spheres (fehlend)', false],
  ['c_slug', 'Power Slugs (fehlend)', false], ['c_droppod', 'Absturzstellen (offen)', false],
];

export const CIRCUIT_COLORS = ['#e2b93b', '#b58be8', '#4cc38a', '#e07b9b', '#6cc4d8', '#c9a26b'];

export function stationsObjs(st: Stations): MapObj[] {
  const out: MapObj[] = [];
  for (const s of [...st.trains.map(x => ({ ...x, kind: 'train' as const })), ...st.trucks.map(x => ({ ...x, kind: 'truck' as const }))]) {
    const fill = s.kind === 'truck' ? s.fill : (s.platforms || []).filter(p => p.fill != null).reduce((a, p, _i, arr) => a + (p.fill! / arr.length), 0);
    out.push({
      kind: 'station', key: 'station:' + s.id.split('.').pop(), x: s.pos[0] / 100, y: s.pos[1] / 100, z: Math.round((s.pos[2] ?? 0) / 100),
      r: s.kind === 'train' ? 6.5 : 5, shape: s.kind === 'train' ? 'square' : 'circle', color: C[s.mode] || C.none,
      label: s.name, prio: 5, layer: 'stations', data: s,
      fill: s.kind === 'truck' || (s.platforms || []).some(p => p.fill != null) ? fill ?? null : null,
    });
  }
  return out;
}

export function liveObjs(lv: Live): MapObj[] {
  const out: MapObj[] = [];
  const stale = lv.source === 'save';
  for (const p of lv.players) out.push({
    kind: 'player', key: 'player:' + p.name, x: p.pos[0] / 100, y: p.pos[1] / 100, r: 6.5, shape: 'circle',
    color: '#f59a23', ring: '#f5f2ea', label: p.name, prio: 9, layer: 'players', data: p, dim: p.online === false,
  });
  for (const t of lv.trains) out.push({
    kind: 'train', key: 'train:' + t.name, x: t.pos[0] / 100, y: t.pos[1] / 100, r: 5.5, shape: 'square',
    color: t.derailed ? C.bad : C.train, ring: '#f5f2ea', label: t.name, prio: 7, layer: 'vehicles', data: t, dim: stale,
  });
  for (const v of lv.trucks) out.push({
    kind: 'truck', key: 'truck:' + (v.id || v.name), x: v.pos[0] / 100, y: v.pos[1] / 100, r: 5, shape: 'diamond',
    color: v.fuel === false ? C.bad : C.truck, ring: '#f5f2ea', label: v.name, prio: 6, layer: 'vehicles', data: v, dim: stale,
  });
  return out;
}

export function factoryObjs(f: Factory): MapObj[] {
  const out: MapObj[] = [];
  for (const m of f.machines) {
    const starved = m.state === 'steht' && m.block !== 'voll';
    if (m.nopower) {                                  // eigene, standardmäßig sichtbare Ebene: sofort auffällig
      out.push({ kind: 'machine', key: 'machine:' + m.id, x: m.pos[0], y: m.pos[1], z: m.z, r: 4.5, shape: 'diamond',
        color: '#e5484d', ring: '#f5f2ea', label: m.name + ' ohne Strom', prio: 3, layer: 'nopower', data: m });
      continue;
    }
    out.push({
      kind: 'machine', key: 'machine:' + m.id, x: m.pos[0], y: m.pos[1], z: m.z, r: 3.2, shape: 'square',
      color: machineColor(m), label: m.recipe || m.name, prio: 1,
      layer: starved ? 'starved' : 'machines', data: m,
    });
  }
  for (const g of f.generators) out.push({
    kind: 'generator', key: 'generator:' + g.id, x: g.pos[0], y: g.pos[1], r: 4.5, shape: 'tri',
    color: g.producing ? '#e2b93b' : '#6f6b64', label: g.name, prio: 2, layer: 'generators', data: g,
  });
  for (const c of f.factories) out.push({
    kind: 'factory', key: 'factory:' + c.key, x: c.center[0], y: c.center[1], r: 0.01, shape: 'circle',
    color: 'transparent', label: c.name, prio: 4, layer: 'factories', data: c, minK: .25,
  });
  return out;
}

export function nodeObjs(ns: Node[]): MapObj[] {
  const P: Record<string, string> = { pure: '#4cc38a', normal: '#e2b93b', impure: '#e5484d' };
  return ns.map(n => ({
    kind: 'node', key: 'node:' + n.id, x: n.pos[0], y: n.pos[1], r: 4, shape: 'tri' as const,
    color: n.used ? '#6f6b64' : P[n.purity || ''] || '#9a968e', ring: n.used ? undefined : '#0c0d0e',
    label: (n.item || '?') + (n.purity ? ' · ' + { pure: 'rein', normal: 'normal', impure: 'unrein' }[n.purity] : ''),
    prio: 1, layer: 'nodes', data: n,
  }));
}

export function pinObjs(ps: Pin[]): MapObj[] {
  return ps.map(p => {
    const g = p.geom, cx = g.reduce((a, q) => a + q[0], 0) / g.length, cy = g.reduce((a, q) => a + q[1], 0) / g.length;
    const [x, y] = p.shape === 'point' ? g[0] : [cx, cy];
    return { kind: 'pin', key: 'pin:' + p.id, x, y, r: 6, shape: 'pin' as const, color: p.color, ring: '#0c0d0e',
      label: p.text.split('\n')[0].slice(0, 40), prio: 8, layer: 'pins', data: p };
  });
}

export function applyGeo(v: MapView, g: Geo | null, lines: number[][] | null, st: Stations | null) {
  v.lines = [];
  if (g) {
    v.lines.push({ key: 'belts', layer: 'belts', color: '#8d8a84', width: 1.1, alpha: .6, paths: g.belts });
    v.lines.push({ key: 'pipes', layer: 'pipes', color: '#5b9bd5', width: 1.4, alpha: .75, paths: g.pipes });
    v.lines.push({ key: 'rails', layer: 'rails', color: '#cfcac0', width: 1.6, alpha: .8, paths: g.rails });
  }
  if (st) {                          // Zugrouten als Luftlinie zwischen den Halten
    const byIdent: Record<string, number[]> = {};
    st.trains.forEach(s => (byIdent[s.ident!] = [s.pos[0] / 100, s.pos[1] / 100]));
    const paths = st.routes.map(r => r.stops.map(s => byIdent[s.ident]).filter(Boolean)).filter(p => p.length > 1).map(p => [...p, p[0]]);
    v.lines.push({ key: 'routes', layer: 'routes', color: '#f59a23', width: 1.4, alpha: .55, paths });
  }
  v.segs = lines ? [{ key: 'power', layer: 'power', width: 1, alpha: .7, segs: lines,
    color: s => s[4] == null ? '#6f6b64' : CIRCUIT_COLORS[Math.abs(s[4]) % CIRCUIT_COLORS.length] }] : [];
}

/** Fabrik-Umriss: grün = läuft, gelb = teils Mangel, rot = viel Mangel; volle Ausgänge zählen nicht als Problem. */
export function factoryColor(f: { n: number; starved: number; states: Record<string, number> }) {
  const bad = f.starved / Math.max(1, f.n), run = ((f.states['läuft'] || 0) + (f.states['teilweise'] || 0)) / Math.max(1, f.n);
  return bad > .3 ? '#e5484d' : bad > .08 ? '#e2b93b' : run > .2 ? '#4cc38a' : '#8a857c';
}

const CCOL: Record<string, [string, string, 'circle' | 'diamond' | 'tri' | 'square']> = {
  somersloop: ['#e5484d', 'c_somersloop', 'diamond'], mercer: ['#b58be8', 'c_mercer', 'circle'],
  slug1: ['#5b9bd5', 'c_slug', 'tri'], slug2: ['#e2b93b', 'c_slug', 'tri'], slug3: ['#b58be8', 'c_slug', 'tri'],
  droppod: ['#f59a23', 'c_droppod', 'square'],
};
export function collectibleObjs(c: any): MapObj[] {
  const out: MapObj[] = [];
  for (const [k, list] of Object.entries(c?.open || {}) as [string, number[][]][]) {
    const [color, layer, shape] = CCOL[k] || ['#9a968e', 'c_slug', 'circle'];
    list.forEach((p, i) => out.push({ kind: 'collectible', key: 'c:' + k + ':' + i, x: p[0], y: p[1], z: p[2], r: k === 'somersloop' ? 5 : 3.5,
      shape, color, ring: '#0c0d0e', label: c.labels?.[k], prio: 1, layer, data: { kind: k, label: c.labels?.[k], pos: p }, minK: k.startsWith('slug') ? .15 : 0 }));
  }
  return out;
}
