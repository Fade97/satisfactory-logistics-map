// Layout für das Produktionsketten-Diagramm (geschichteter Graph, Sankey-Stil).
//
// Warum nicht einfach „Rohstoffe links, Ziel rechts“: Bei verzweigten Ketten (Uranium Fuel Rod) liefen so alle
// Quellen aus Spalte 0 quer über das Bild zu Verbrauchern weit rechts. Hier stattdessen:
//   1. Mengen je Kante aufteilen (mehrere Erzeuger einer Ware → anteilig), Zielknoten ganz rechts.
//   2. Schichten per längstem Weg, dann jeden Knoten so weit nach rechts ziehen, wie seine Abnehmer erlauben —
//      Quellen stehen direkt vor ihrem ersten Verbraucher.
//   3. Reihenfolge je Schicht per Baryzentrum (mehrere Durchläufe hin und zurück) → wenige Kreuzungen.
//   4. Anschlusspunkte je Knoten nach Lage der Gegenstelle verteilt, Linienstärke nach Menge.

export interface FNode { id: string; kind: 'raw' | 'sur' | 'step' | 'target'; label: string; sub: string; layer: number; order: number;
  x: number; y: number; data?: any }
export interface FEdge { id: string; a: FNode; b: FNode; item: string; rate: number; kind: 'raw' | 'sur' | 'mid';
  y1: number; y2: number; w: number; label?: boolean }

export const W = 210, H = 58, GX = 120, GY = 22;
/** Platz für eine Kantenbeschriftung vor dem Zielkasten (≈ 6 px je Zeichen bei 11 px Schrift) */
export const LABEL_CHARS = Math.floor((GX - 14) / 6);

export function layout(res: any, fmt: (n: number) => string) {
  const nodes: FNode[] = [];
  const add = (n: Omit<FNode, 'layer' | 'order' | 'x' | 'y'>) => { const f = { ...n, layer: 0, order: 0, x: 0, y: 0 }; nodes.push(f); return f; };
  const prod = new Map<string, { n: FNode; amt: number }[]>();          // Ware → Erzeuger
  const cons: { n: FNode; item: string; amt: number }[] = [];            // Verbrauch je Knoten
  const addProd = (item: string, n: FNode, amt: number) => { if (!prod.has(item)) prod.set(item, []); prod.get(item)!.push({ n, amt }); };

  for (const r of res.raw) addProd(r.item, add({ id: 'raw:' + r.item, kind: 'raw', label: r.item, sub: fmt(r.rate) + '/min Rohstoff' }), r.rate);
  for (const u of res.surplus_used) addProd(u.item, add({ id: 'sur:' + u.item, kind: 'sur', label: u.item, sub: fmt(u.rate) + '/min aus Überschuss' }), u.rate);
  res.steps.forEach((s: any, i: number) => {
    const n = add({ id: 'step:' + i, kind: 'step', label: s.recipe, sub: `${fmt(s.machines)}× ${s.building}`, data: s });
    s.out.forEach((o: any) => addProd(o.item, n, o.rate));
    s.inp.forEach((x: any) => cons.push({ n, item: x.item, amt: x.rate }));
  });
  // Ziel: Hat genau ein Schritt die Zielware als Produkt, wird dieser Schritt selbst zum Zielkasten —
  // ein eigener Kasten dahinter wäre nur eine Wiederholung. Sonst (mehrere Erzeuger, Überschuss) eigener Kasten.
  for (const t of res.targets) {
    const ps = (prod.get(t.item) || []).filter(p => p.n.kind === 'step');
    if (ps.length === 1 && !(prod.get(t.item) || []).some(p => p.n.kind !== 'step')) {
      const n = ps[0].n;
      n.kind = 'target'; n.sub = fmt(t.rate) + '/min Ziel · ' + n.sub;
      continue;
    }
    const n = add({ id: 'target:' + t.item, kind: 'target', label: t.item, sub: fmt(t.rate) + '/min Ziel' });
    cons.push({ n, item: t.item, amt: t.rate });
  }

  // 1. Kanten mit anteiliger Menge; Eigenkreislauf (Blender gibt Schwefelsäure zurück) nicht zeichnen
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

  // 2. Schichten: längster Weg von links (mit Zyklenschutz) …
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
  // … dann nach rechts ziehen: so nah wie möglich an den nächsten Abnehmer
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

  // 3. Reihenfolge: Baryzentrum der Nachbarn, abwechselnd von links und von rechts
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

  // Koordinaten: Spalten vertikal zentriert
  const colH = (l: FNode[]) => l.length * H + Math.max(0, l.length - 1) * GY;
  const height = Math.max(...layers.map(colH));
  layers.forEach((l, li) => {
    const off = (height - colH(l)) / 2;
    l.forEach((n, i) => { n.x = li * (W + GX); n.y = off + i * (H + GY); });
  });

  // 4. Anschlüsse: je Seite nach Lage der Gegenstelle sortiert verteilen, Stärke nach Menge
  const maxRate = Math.max(1e-9, ...edges.map(e => e.rate));
  for (const e of edges) e.w = 1.5 + 6 * Math.sqrt(e.rate / maxRate);
  const spread = (list: FEdge[], other: (e: FEdge) => FNode, set: (e: FEdge, y: number) => void, n: FNode, mark = false) => {
    const s = [...list].sort((p, q) => other(p).y - other(q).y || other(p).x - other(q).x);
    const pad = 10, span = H - 2 * pad;
    s.forEach((e, i) => set(e, n.y + pad + (s.length === 1 ? span / 2 : (span * i) / (s.length - 1))));
    // Beschriftung am Eingang nur, wenn die Anschlüsse weit genug auseinander liegen (sonst überlappen sie);
    // die Menge steht dann im Tooltip und im Baum
    if (mark) { const gap = s.length > 1 ? span / (s.length - 1) : 99; s.forEach(e => (e.label = gap >= 12)); }
  };
  for (const n of nodes) {
    spread(outs.get(n)!, e => e.b, (e, y) => (e.y1 = y), n);
    spread(ins.get(n)!, e => e.a, (e, y) => (e.y2 = y), n, true);
  }
  return { nodes, edges, width: layers.length * (W + GX) - GX, height, ins, outs };
}

/** Kantenpfad: horizontale Tangenten, bei übersprungenen Spalten sanfter Bogen. */
export function edgePath(e: FEdge) {
  const x1 = e.a.x + W, x2 = e.b.x, dx = Math.max(40, (x2 - x1) * 0.5);
  return `M${x1},${e.y1} C${x1 + dx},${e.y1} ${x2 - dx},${e.y2} ${x2},${e.y2}`;
}
