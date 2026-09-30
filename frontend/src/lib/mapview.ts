/* Canvas-Karte: Weltkoordinaten in Metern (+x Ost, +y Süd), Ansicht = Maßstab k (px/m) + Versatz.

   Zeichnen in zwei Schichten:
   - statisch (Offscreen-Canvas): Kartenbild, Netzgeometrie, Leitungen, Maschinen — nur bei Zoom-/
     Datenänderung neu; beim Verschieben wird das fertige Bild nur versetzt geblittet.
   - dynamisch: Fahrzeuge, Spieler, Auswahl, Beschriftungen — jeden Frame, in dem sich etwas bewegt.
   Treffer werden über ein Rastergitter gesucht, nicht per DOM. */

export interface MapObj {
  kind: string; key: string; x: number; y: number; r: number; label?: string; color: string; ring?: string;
  shape: 'circle' | 'square' | 'diamond' | 'tri' | 'pin'; prio: number; minK?: number; data: any; layer: string;
  tx?: number; ty?: number; sx?: number; sy?: number; t0?: number; fill?: number | null; dim?: boolean; z?: number;
}
export interface Lines { key: string; layer: string; color: string; width: number; alpha: number; paths: number[][][]; minK?: number }
export interface Segs { key: string; layer: string; width: number; alpha: number; segs: number[][]; color: (s: number[]) => string }
export interface Overlay { key: string; layer: string; draw: (ctx: CanvasRenderingContext2D, v: MapView) => void }

export class MapView {
  cv: HTMLCanvasElement; ctx: CanvasRenderingContext2D;
  st: HTMLCanvasElement; sctx: CanvasRenderingContext2D;
  k = 0.4; dx = 0; dy = 0; w = 0; h = 0; dpr = 1;
  img: HTMLImageElement | null = null; box = { x: 0, y: 0, w: 1, h: 1 };
  objs: MapObj[] = []; lines: Lines[] = []; segs: Segs[] = []; overlays: Overlay[] = []; boxes: any[] = [];
  layers: Record<string, boolean> = {};
  hidden = new Set<string>();       // Filter: Schlüssel ausgeblendeter Objekte
  /** Warenfluss: hervorgehobene Objekte (Rest abgedunkelt) + Linienzüge der Ware, null = aus */
  flowFocus: { keys: Set<string>; paths: number[][][]; color: string } | null = null;
  sel: MapObj | null = null; hover: MapObj | null = null;
  /** Folge-Modus: Schlüssel des verfolgten Objekts + Bildschirmversatz (Detailkarte/Bottom Sheet verdecken einen Teil).
      Die Kamera hängt im Render-Loop an der interpolierten Position — gleitet also genau wie der Punkt. */
  followKey: string | null = null; followOff = { x: 0, y: 0 };
  links: [MapObj, MapObj][] = [];
  labels = true; imgAlpha = 0.85;
  private stKey = ''; private raf = 0; private dirty = true;
  onchange: () => void = () => {};

  constructor(cv: HTMLCanvasElement) {
    this.cv = cv; this.ctx = cv.getContext('2d')!;
    this.st = document.createElement('canvas'); this.sctx = this.st.getContext('2d')!;
    new ResizeObserver(() => this.resize()).observe(cv.parentElement!);
    this.resize();
    const loop = (now: number) => { this.tick(now); this.raf = requestAnimationFrame(loop); };
    this.raf = requestAnimationFrame(loop);
  }
  destroy() { cancelAnimationFrame(this.raf); }

  resize() {
    const r = this.cv.parentElement!.getBoundingClientRect();
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.w = r.width; this.h = r.height;
    this.cv.width = Math.round(r.width * this.dpr); this.cv.height = Math.round(r.height * this.dpr);
    this.cv.style.width = r.width + 'px'; this.cv.style.height = r.height + 'px';
    this.stKey = ''; this.redraw();
  }

  // ---------------------------------------------------------------- Koordinaten
  sx = (x: number) => x * this.k + this.dx;
  sy = (y: number) => y * this.k + this.dy;
  wx = (px: number) => (px - this.dx) / this.k;
  wy = (py: number) => (py - this.dy) / this.k;

  setImage(src: string, box: { x: number; y: number; w: number; h: number }) {
    this.box = box;
    const im = new Image(); im.onload = () => { this.img = im; this.stKey = ''; this.redraw(); }; im.src = src;
  }
  redraw() { this.dirty = true; }
  invalidate() { this.stKey = ''; this.dirty = true; }

  zoomAt(px: number, py: number, f: number) {
    const k = Math.max(0.02, Math.min(30, this.k * f)); f = k / this.k;
    this.k = k; this.dx = px - (px - this.dx) * f; this.dy = py - (py - this.dy) * f;
    this.redraw(); this.onchange();
  }
  pan(ddx: number, ddy: number) { this.dx += ddx; this.dy += ddy; this.redraw(); this.onchange(); }
  fit(x0: number, y0: number, x1: number, y1: number, pad = 0.9, offY = 0) {
    const k = Math.min(this.w / Math.max(1, x1 - x0), (this.h - offY) / Math.max(1, y1 - y0)) * pad;
    this.k = Math.max(0.02, Math.min(30, k));
    this.dx = this.w / 2 - this.k * (x0 + x1) / 2; this.dy = (this.h - offY) / 2 - this.k * (y0 + y1) / 2;
    this.invalidate(); this.onchange();
  }
  focus(x: number, y: number, minK = 1.2, offY = 0, offX = 0) {
    this.k = Math.max(this.k, minK);
    this.dx = (this.w - offX) / 2 - this.k * x; this.dy = (this.h - offY) / 2 - this.k * y;
    this.invalidate(); this.onchange();
  }
  center() { return { x: this.wx(this.w / 2), y: this.wy(this.h / 2) }; }

  // ---------------------------------------------------------------- Treffer
  hit(px: number, py: number, tol = 10): MapObj | null {
    let best: MapObj | null = null, bd = 1e9;
    for (const o of this.objs) {
      if (!this.visible(o)) continue;
      const d = Math.hypot(this.sx(o.x) - px, this.sy(o.y) - py);
      const lim = Math.max(tol, this.rad(o) + 3);
      if (d < lim && d - o.prio * 2 < bd) { bd = d - o.prio * 2; best = o; }
    }
    return best;
  }
  /** Detailebene (Fundamente/Wände aus dem Save): Int16-Felder, siehe lightweight.detail_binary */
  detail: { tiles: Int16Array; tmeta: Uint8Array; walls: Int16Array } | null = null;
  /** Höhenfilter in Metern [von, bis] — gilt für Objekte mit z (Maschinen, Generatoren, Stationen), null = aus */
  zRange: [number, number] | null = null;
  visible(o: MapObj) {
    if (this.zRange && o.z !== undefined && (o.z < this.zRange[0] || o.z > this.zRange[1])) return false;
    return this.layers[o.layer] !== false && !this.hidden.has(o.key) && (!o.minK || this.k >= o.minK);
  }
  rad(o: MapObj) { return o.r * (o.kind === 'machine' || o.kind === 'node' || o.kind === 'collectible' ? Math.min(1.6, Math.max(.45, this.k / 1.2)) : 1); }

  // ---------------------------------------------------------------- Zeichnen
  private tick(now: number) {
    let moving = false;
    for (const o of this.objs) {
      if (!o.t0) continue;
      const p = Math.min(1, (now - o.t0) / 4800);
      const e = p < .5 ? 2 * p * p : 1 - 2 * (1 - p) * (1 - p);
      o.x = o.sx! + (o.tx! - o.sx!) * e; o.y = o.sy! + (o.ty! - o.sy!) * e;
      if (p >= 1) o.t0 = 0;
      moving = true;
    }
    if (this.followKey) {
      const o = this.objs.find(x => x.key === this.followKey);
      if (o) {
        // Nur verschieben (dx/dy), nicht neu rendern: drawStatic erneuert die Offscreen-Fläche erst,
        // wenn der Versatz zu groß wird — so bleibt das Mitführen bei 60 fps günstig
        const dx = (this.w - this.followOff.x) / 2 - this.k * o.x, dy = (this.h - this.followOff.y) / 2 - this.k * o.y;
        if (Math.abs(dx - this.dx) > .05 || Math.abs(dy - this.dy) > .05) {
          this.dx = dx; this.dy = dy; moving = true; this.onchange();
        }
      }
    }
    if (moving) this.dirty = true;
    if (this.dirty) { this.dirty = false; this.draw(); }
  }

  private drawStatic() {
    // Statischer Teil als Bild für einen etwas größeren Ausschnitt; neu nur bei Zoom oder zu weitem Verschieben
    const key = this.k.toFixed(4) + '|' + JSON.stringify(this.layers) + '|' + this.imgAlpha + '|' + this.hidden.size + '|' + (this.flowFocus ? this.flowFocus.keys.size + ':' + this.flowFocus.paths.length : '') + '|' + (this.zRange || '');
    const W = this.w * 2, H = this.h * 2;
    // Offscreen-Fläche = Bildschirm plus je eine halbe Breite/Höhe Rand: Welt-x → x·k + ox
    const ox = this.dx + this.w / 2, oy = this.dy + this.h / 2;
    const cur = (this as any)._st as { key: string; ox: number; oy: number } | undefined;
    if (cur && cur.key === key && this.stKey && Math.abs(ox - cur.ox) < this.w / 2.2 && Math.abs(oy - cur.oy) < this.h / 2.2) return cur;
    const d = this.dpr, c = this.sctx;
    this.st.width = Math.round(W * d); this.st.height = Math.round(H * d);
    c.setTransform(d, 0, 0, d, 0, 0);
    c.fillStyle = '#16171a'; c.fillRect(0, 0, W, H);
    const k = this.k;
    const X = (x: number) => x * k + ox, Y = (y: number) => y * k + oy;
    if (this.img && this.layers.mapimg !== false) {
      c.globalAlpha = this.imgAlpha; c.imageSmoothingQuality = 'high';
      c.drawImage(this.img, X(this.box.x), Y(this.box.y), this.box.w * k, this.box.h * k);
      c.globalAlpha = 1;
    }
    c.lineCap = 'round'; c.lineJoin = 'round';
    const vx0 = -ox / k, vy0 = -oy / k, vx1 = (W - ox) / k, vy1 = (H - oy) / k;
    if (this.detail && this.layers.detail !== false && k >= 0.8) this.drawDetail(c, X, Y, k, vx0, vy0, vx1, vy1);
    for (const s of this.segs) {
      if (this.layers[s.layer] === false) continue;
      c.globalAlpha = s.alpha; c.lineWidth = s.width;
      const by: Record<string, number[][]> = {};
      for (const g of s.segs) (by[s.color(g)] ||= []).push(g);
      for (const col in by) {
        c.strokeStyle = col; c.beginPath();
        for (const g of by[col]) {
          if (Math.max(g[0], g[2]) < vx0 || Math.min(g[0], g[2]) > vx1 || Math.max(g[1], g[3]) < vy0 || Math.min(g[1], g[3]) > vy1) continue;
          c.moveTo(X(g[0]), Y(g[1])); c.lineTo(X(g[2]), Y(g[3]));
        }
        c.stroke();
      }
    }
    for (const l of this.lines) {
      if (this.layers[l.layer] === false || (l.minK && k < l.minK)) continue;
      c.globalAlpha = this.flowFocus ? l.alpha * .25 : l.alpha; c.strokeStyle = l.color; c.lineWidth = l.width * Math.min(2.2, Math.max(.7, k / 1.5));
      c.beginPath();
      for (const p of l.paths) {
        let inView = false;
        for (const q of p) if (q[0] > vx0 && q[0] < vx1 && q[1] > vy0 && q[1] < vy1) { inView = true; break; }
        if (!inView && p.length < 3) continue;
        c.moveTo(X(p[0][0]), Y(p[0][1]));
        for (let i = 1; i < p.length; i++) c.lineTo(X(p[i][0]), Y(p[i][1]));
      }
      c.stroke();
    }
    if (this.flowFocus) {                              // Warenfluss: Bänder/Rohre der Ware kräftig darüber
      c.globalAlpha = .95; c.strokeStyle = this.flowFocus.color; c.lineWidth = Math.min(4, Math.max(1.6, k * 1.6));
      c.beginPath();
      for (const p of this.flowFocus.paths) {
        c.moveTo(X(p[0][0]), Y(p[0][1]));
        for (let i = 1; i < p.length; i++) c.lineTo(X(p[i][0]), Y(p[i][1]));
      }
      c.stroke();
    }
    c.globalAlpha = 1;
    for (const b of this.boxes) {                 // Fabrik-Cluster als Umriss
      if (this.layers[b.layer] === false) continue;
      const x = X(b.box[0] - 12), y = Y(b.box[1] - 12), w = (b.box[2] - b.box[0] + 24) * k, h = (b.box[3] - b.box[1] + 24) * k;
      c.strokeStyle = b.color; c.globalAlpha = .55; c.lineWidth = 1; c.setLineDash([4, 3]); c.strokeRect(x, y, w, h); c.setLineDash([]);
      c.globalAlpha = .06; c.fillStyle = b.color; c.fillRect(x, y, w, h); c.globalAlpha = 1;
    }
    // statische Objekte (Maschinen, Knoten, Generatoren) mit in die Offscreen-Fläche
    for (const o of this.objs) {
      if (o.t0 !== undefined || o.kind === 'player' || o.kind === 'train' || o.kind === 'truck' || o.kind === 'station' || o.kind === 'pin') continue;
      if (!this.visible(o)) continue;
      const x = X(o.x), y = Y(o.y);
      if (x < -20 || y < -20 || x > W + 20 || y > H + 20) continue;
      this.shape(c, o, x, y, this.rad(o));
    }
    const res = { key, ox, oy };
    (this as any)._st = res; this.stKey = key;
    return res;
  }

  /** Fundamente als 8×8-m-Kacheln (Farbe nach Material, obere Etagen heller), Wände als Linien darüber. */
  private drawDetail(c: CanvasRenderingContext2D, X: (x: number) => number, Y: (y: number) => number, k: number,
                     x0: number, y0: number, x1: number, y1: number) {
    const d = this.detail!, T = d.tiles, M = d.tmeta, n = M.length, zr = this.zRange;
    const MAT = ['#8f8a82', '#5f6368', '#b3aea6', '#7d8590', '#6cc4d8', '#6f6450'];   // sonstig, Asphalt, Beton, Metall, Glas, Teer
    const half = 4 * k;
    const byCol = new Map<string, number[]>();
    for (let i = 0; i < n; i++) {
      const x = T[3 * i], y = T[3 * i + 1], z = T[3 * i + 2];
      if (x < x0 - 8 || x > x1 + 8 || y < y0 - 8 || y > y1 + 8) continue;
      if (zr && (z < zr[0] - 1 || z > zr[1] + 1)) continue;
      const col = MAT[M[i] >> 2] || MAT[0];
      if (!byCol.has(col)) byCol.set(col, []);
      byCol.get(col)!.push(i);
    }
    c.globalAlpha = this.flowFocus ? .18 : .55;
    for (const [col, ids] of byCol) {
      c.fillStyle = col; c.beginPath();
      for (const i of ids) {
        // 8×8-Kachel achsparallel: Drehungen um 90° ändern das Quadrat nicht, schräge Bauten sind selten
        const cx = X(T[3 * i]), cy = Y(T[3 * i + 1]);
        c.rect(cx - half, cy - half, 2 * half, 2 * half);
      }
      c.fill();
    }
    if (k >= 1.6) {                                        // Fugen erst bei starkem Zoom
      c.globalAlpha = .35; c.strokeStyle = '#16171a'; c.lineWidth = 1; c.beginPath();
      for (const ids of byCol.values()) for (const i of ids) {
        const cx = X(T[3 * i]), cy = Y(T[3 * i + 1]); c.rect(cx - half, cy - half, 2 * half, 2 * half);
      }
      c.stroke();
    }
    const Wl = d.walls, nw = Wl.length / 5;
    c.globalAlpha = this.flowFocus ? .2 : .8; c.strokeStyle = '#d8d3ca'; c.lineWidth = Math.max(1, Math.min(2.5, k * .6)); c.beginPath();
    for (let i = 0; i < nw; i++) {
      const ax = Wl[5 * i] / 2, ay = Wl[5 * i + 1] / 2, bx = Wl[5 * i + 2] / 2, by = Wl[5 * i + 3] / 2, z = Wl[5 * i + 4];
      if (Math.max(ax, bx) < x0 || Math.min(ax, bx) > x1 || Math.max(ay, by) < y0 || Math.min(ay, by) > y1) continue;
      if (zr && (z < zr[0] - 1 || z > zr[1] + 5)) continue;
      c.moveTo(X(ax), Y(ay)); c.lineTo(X(bx), Y(by));
    }
    c.stroke(); c.globalAlpha = 1;
  }

  shape(c: CanvasRenderingContext2D, o: MapObj, x: number, y: number, r: number) {
    c.globalAlpha = o.dim ? .3 : 1;
    if (this.flowFocus && !this.flowFocus.keys.has(o.key) && o.kind !== 'player') c.globalAlpha = .12;
    c.fillStyle = o.color; c.strokeStyle = o.ring || '#0c0d0e'; c.lineWidth = o.ring ? 2 : 1.2;
    c.beginPath();
    if (o.shape === 'circle') c.arc(x, y, r, 0, Math.PI * 2);
    else if (o.shape === 'square') { c.rect(x - r, y - r, 2 * r, 2 * r); }
    else if (o.shape === 'diamond') { c.moveTo(x, y - r * 1.25); c.lineTo(x + r * 1.25, y); c.lineTo(x, y + r * 1.25); c.lineTo(x - r * 1.25, y); c.closePath(); }
    else if (o.shape === 'tri') { c.moveTo(x, y - r * 1.2); c.lineTo(x + r * 1.1, y + r * .8); c.lineTo(x - r * 1.1, y + r * .8); c.closePath(); }
    else if (o.shape === 'pin') { c.moveTo(x, y); c.lineTo(x - r * .8, y - r * 1.6); c.arc(x, y - r * 1.9, r * .9, Math.PI * .8, Math.PI * .2); c.closePath(); }
    c.fill(); c.stroke();
    c.globalAlpha = 1;
  }

  draw() {
    const c = this.ctx, d = this.dpr;
    const s = this.drawStatic();
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.fillStyle = '#16171a'; c.fillRect(0, 0, this.cv.width, this.cv.height);
    c.drawImage(this.st, Math.round((this.dx - s.ox) * d), Math.round((this.dy - s.oy) * d));
    c.setTransform(d, 0, 0, d, 0, 0);
    for (const ov of this.overlays) if (this.layers[ov.layer] !== false) ov.draw(c, this);
    // Verbindungslinien zur Auswahl
    if (this.links.length) {
      c.setLineDash([7, 5]); c.lineWidth = 2; c.strokeStyle = '#f5f2ea'; c.globalAlpha = .85;
      c.beginPath();
      for (const [a, b] of this.links) { c.moveTo(this.sx(a.x), this.sy(a.y)); c.lineTo(this.sx(b.x), this.sy(b.y)); }
      c.stroke(); c.setLineDash([]); c.globalAlpha = 1;
    }
    const dyn = this.objs.filter(o => (o.kind === 'station' || o.kind === 'player' || o.kind === 'train' || o.kind === 'truck' || o.kind === 'pin') && this.visible(o))
      .sort((a, b) => a.prio - b.prio);
    for (const o of dyn) {
      const x = this.sx(o.x), y = this.sy(o.y);
      if (x < -30 || y < -30 || x > this.w + 30 || y > this.h + 30) continue;
      this.shape(c, o, x, y, o.r);
      if (o.fill != null && this.k > .35) {        // Füllstand als kleiner Balken unter Stationen
        c.fillStyle = '#0c0d0e'; c.fillRect(x - 8, y + o.r + 3, 16, 3);
        c.fillStyle = o.fill > .9 ? '#e5484d' : o.fill < .1 ? '#9a968e' : '#e8e6e1'; c.fillRect(x - 8, y + o.r + 3, 16 * o.fill, 3);
      }
    }
    if (this.flowFocus) for (const o of this.objs) {    // Fokus-Objekte mit Ring markieren
      if (!this.flowFocus.keys.has(o.key) || !this.visible(o) || o.kind === 'factory') continue;
      const x = this.sx(o.x), y = this.sy(o.y);
      if (x < -20 || y < -20 || x > this.w + 20 || y > this.h + 20) continue;
      c.strokeStyle = this.flowFocus.color; c.lineWidth = 2; c.beginPath(); c.arc(x, y, this.rad(o) + 4, 0, Math.PI * 2); c.stroke();
    }
    for (const o of [this.hover, this.sel]) {
      if (!o || !this.visible(o)) continue;
      const x = this.sx(o.x), y = this.sy(o.y), r = this.rad(o) + 7;
      c.strokeStyle = '#f59a23'; c.lineWidth = 2.5;
      c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.stroke();
    }
    if (this.labels) this.drawLabels(c);
  }

  private drawLabels(c: CanvasRenderingContext2D) {
    const placed: number[][] = [];
    const cand = this.objs.filter(o => o.label && this.visible(o) && (!o.minK || this.k >= o.minK) && this.labelOk(o)
        && (!this.flowFocus || this.flowFocus.keys.has(o.key) || o.kind === 'player'))
      .sort((a, b) => (b === this.sel ? 1 : 0) - (a === this.sel ? 1 : 0) || b.prio - a.prio);
    c.font = '600 12px "Barlow Condensed", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'bottom';
    c.lineJoin = 'round';
    let n = 0;
    for (const o of cand) {
      const x = this.sx(o.x), y = this.sy(o.y) - this.rad(o) - 4;
      if (x < -100 || y < 0 || x > this.w + 100 || y > this.h + 20) continue;
      const w = c.measureText(o.label!).width + 6, b = [x - w / 2, y - 14, x + w / 2, y];
      if (placed.some(q => b[0] < q[2] && q[0] < b[2] && b[1] < q[3] && q[1] < b[3])) continue;
      placed.push(b);
      c.strokeStyle = 'rgba(12,13,14,.92)'; c.lineWidth = 3.5; c.strokeText(o.label!, x, y);
      c.fillStyle = o.kind === 'player' ? '#f59a23' : o.kind === 'machine' ? '#b8b4ab' : '#e8e6e1';
      c.fillText(o.label!, x, y);
      if (++n > 260) break;
    }
  }
  private labelOk(o: MapObj) {
    const need: Record<string, number> = { collectible: 3, machine: 2.5, generator: 1.6, node: 2.2, marker: .6, train: .5, truck: 1.2, station: .18, player: 0, pin: .1, factory: 0 };
    return o === this.sel || this.k >= (need[o.kind] ?? 0);
  }
}
