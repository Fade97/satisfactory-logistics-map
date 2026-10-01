// Layout for the production chain diagram (layered graph, Sankey style).
//
// Why not simply "raw materials left, target right": with branching chains (Uranium Fuel Rod) all sources
// in column 0 would run across the whole picture to consumers far to the right. Instead:
//   1. Split rates per edge (several producers of an item → proportionally), target nodes far right.
//   2. Layers by longest path, then pull every node as far right as its consumers allow —
//      sources sit directly before their first consumer.
//   3. Order per layer by barycentre (several passes back and forth) → few crossings.
//   4. Ports per node distributed by the position of the opposite end, line width by rate.

import { tr } from './i18n';

export interface FNode { id: string; kind: 'raw' | 'sur' | 'step' | 'target'; label: string; sub: string; layer: number; order: number;
  x: number; y: number; data?: any }
export interface FEdge { id: string; a: FNode; b: FNode; item: string; rate: number; kind: 'raw' | 'sur' | 'mid';
  y1: number; y2: number; w: number; label?: boolean }

export const W = 210, H = 58, GX = 120, GY = 22;
/** Space for an edge label before the target box (≈ 6 px per char at 11 px font) */
export const LABEL_CHARS = Math.floor((GX - 14) / 6);

export function layout(res: any, fmt: (n: number) => string) {
  const nodes: FNode[] = [];
  const add = (n: Omit<FNode, 'layer' | 'order' | 'x' | 'y'>) => { const f = { ...n, layer: 0, order: 0, x: 0, y: 0 }; nodes.push(f); return f; };
  const prod = new Map<string, { n: FNode; amt: number }[]>();          // item → producers
  const cons: { n: FNode; item: string; amt: number }[] = [];            // consumption per node
  const addProd = (item: string, n: FNode, amt: number) => { if (!prod.has(item)) prod.set(item, []); prod.get(item)!.push({ n, amt }); };

  for (const r of res.raw) addProd(r.item, add({ id: 'raw:' + r.item, kind: 'raw', label: r.item, sub: tr('{rate}/min raw', { rate: fmt(r.rate) }) }), r.rate);
  for (const u of res.surplus_used) addProd(u.item, add({ id: 'sur:' + u.item, kind: 'sur', label: u.item, sub: tr('{rate}/min from surplus', { rate: fmt(u.rate) }) }), u.rate);
  res.steps.forEach((s: any, i: number) => {
    const n = add({ id: 'step:' + i, kind: 'step', label: s.recipe, sub: `${fmt(s.machines)}× ${s.building}`, data: s });
    s.out.forEach((o: any) => addProd(o.item, n, o.rate));
    s.inp.forEach((x: any) => cons.push({ n, item: x.item, amt: x.rate }));
  });
  // Target: if exactly one step produces the target item, that step itself becomes the target box —
  // a separate box behind it would just repeat it. Otherwise (several producers, surplus) a separate box.
  for (const t of res.targets) {
    const ps = (prod.get(t.item) || []).filter(p => p.n.kind === 'step');
    if (ps.length === 1 && !(prod.get(t.item) || []).some(p => p.n.kind !== 'step')) {
      const n = ps[0].n;
      n.kind = 'target'; n.sub = tr('{rate}/min target', { rate: fmt(t.rate) }) + ' · ' + n.sub;
      continue;
    }
    const n = add({ id: 'target:' + t.item, kind: 'target', label: t.item, sub: tr('{rate}/min target', { rate: fmt(t.rate) }) });
    cons.push({ n, item: t.item, amt: t.rate });
  }

  // 1. Edges with proportional rate; don't draw self-loops (Blender returning Sulfuric Acid)
  const edges: FEdge[] = [];
  for (const c of cons) {
    const ps = (prod.get(c.item) || []).filter(p => p.n !== c.n);
    const tot = ps.reduce((a, p) => a + p.amt, 0);
    if (!tot) continue;
    for (const p of ps) {
      const rate = c.amt * p.amt / tot;
      if (rate < 1e-3) continue;
      edges.push({ id: p.n.id + '>' + c.n.id + ':' + c.item, a: p.n, b: c.n, item: c.item, rate,
        kind: p.n.kind === 'raw' ? 'raw' : p.n.kind === 'sur' ? 'sur' : 'mid', y1: 0, y2: 0, w: 0 });
    }
  }
  const ins = new Map<FNode, FEdge[]>(), outs = new Map<FNode, FEdge[]>();
  for (const n of nodes) { ins.set(n, []); outs.set(n, []); }
  for (const e of edges) { outs.get(e.a)!.push(e); ins.get(e.b)!.push(e); }

  // 2. Layers: longest path from the left (with cycle guard) …
  const L = new Map<FNode, number>();
  const visiting = new Set<FNode>();
  const lay = (n: FNode): number => {
    if (L.has(n)) return L.get(n)!;
    if (visiting.has(n)) return 0;
    visiting.add(n);
    let m = 0;
    for (const e of ins.get(n)!) m = Math.max(m, lay(e.a) + 1);
    visiting.delete(n); L.set(n, m); return m;
  };
  nodes.forEach(lay);
  const maxL = Math.max(...nodes.map(n => L.get(n)!));
  for (const n of nodes) if (n.kind === 'target') L.set(n, maxL);
  // … then pull right: as close as possible to the nearest consumer
  for (let pass = 0; pass < nodes.length; pass++) {
    let moved = false;
    for (const n of nodes) {
      if (n.kind === 'target' || !outs.get(n)!.length) continue;
      const lim = Math.min(...outs.get(n)!.map(e => L.get(e.b)!)) - 1;
      if (lim > L.get(n)!) { L.set(n, lim); moved = true; }
    }
    if (!moved) break;
  }
  const layers: FNode[][] = [];
  for (const n of nodes) { n.layer = L.get(n)!; (layers[n.layer] ||= []).push(n); }
  for (let i = 0; i < layers.length; i++) layers[i] ||= [];

  // 3. Order: barycentre of neighbours, alternating from left and right
  layers.forEach(l => l.forEach((n, i) => (n.order = i)));
  const bary = (n: FNode, side: 'in' | 'out') => {
    const es = side === 'in' ? ins.get(n)! : outs.get(n)!;
    if (!es.length) return n.order;
    let s = 0, w = 0;
    for (const e of es) { const o = side === 'in' ? e.a : e.b; s += o.order * e.rate; w += e.rate; }
    return s / w;
  };
  for (let it = 0; it < 12; it++) {
    const ltr = it % 2 === 0;
    const seq = ltr ? layers.slice(1) : layers.slice(0, -1).reverse();
    for (const l of seq) {
      const key = new Map(l.map(n => [n, bary(n, ltr ? 'in' : 'out')]));
      l.sort((a, b) => key.get(a)! - key.get(b)!);
      l.forEach((n, i) => (n.order = i));
    }
  }

  // Coordinates: columns vertically centred
  const colH = (l: FNode[]) => l.length * H + Math.max(0, l.length - 1) * GY;
  const height = Math.max(...layers.map(colH));
  layers.forEach((l, li) => {
    const off = (height - colH(l)) / 2;
    l.forEach((n, i) => { n.x = li * (W + GX); n.y = off + i * (H + GY); });
  });

  // 4. Ports: per side, distributed sorted by the opposite end's position; width by rate
  const maxRate = Math.max(1e-9, ...edges.map(e => e.rate));
  for (const e of edges) e.w = 1.5 + 6 * Math.sqrt(e.rate / maxRate);
  const spread = (list: FEdge[], other: (e: FEdge) => FNode, set: (e: FEdge, y: number) => void, n: FNode, mark = false) => {
    const s = [...list].sort((p, q) => other(p).y - other(q).y || other(p).x - other(q).x);
    const pad = 10, span = H - 2 * pad;
    s.forEach((e, i) => set(e, n.y + pad + (s.length === 1 ? span / 2 : (span * i) / (s.length - 1))));
    // Label at the input only if the ports are far enough apart (otherwise they overlap);
    // the rate is then shown in the tooltip and the tree
    if (mark) { const gap = s.length > 1 ? span / (s.length - 1) : 99; s.forEach(e => (e.label = gap >= 12)); }
  };
  for (const n of nodes) {
    spread(outs.get(n)!, e => e.b, (e, y) => (e.y1 = y), n);
    spread(ins.get(n)!, e => e.a, (e, y) => (e.y2 = y), n, true);
  }
  return { nodes, edges, width: layers.length * (W + GX) - GX, height, ins, outs };
}

/** Edge path: horizontal tangents, gentle curve across skipped columns. */
export function edgePath(e: FEdge) {
  const x1 = e.a.x + W, x2 = e.b.x, dx = Math.max(40, (x2 - x1) * 0.5);
  return `M${x1},${e.y1} C${x1 + dx},${e.y1} ${x2 - dx},${e.y2} ${x2},${e.y2}`;
}
