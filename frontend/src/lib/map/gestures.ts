// Pointer input on the map canvas: drag to pan, pinch and wheel to zoom, tap, double tap (touch) to zoom in.
// What a tap or hover means (select, measure, draw …) is decided by the page via the handlers.
import { clampZoom, type MapView } from '../mapview';

export interface Pt { x: number; y: number }
export interface GestureHandlers {
  /** Mouse moved without a button pressed */
  hover(p: Pt): void;
  /** Pointer left the canvas */
  leave(): void;
  /** Map is being dragged (beyond the tap tolerance) */
  pan(): void;
  /** Tap/click; return true if handled (measuring, picking, drawing) — otherwise double tap zooms or `select` runs */
  tap(p: Pt): boolean;
  select(p: Pt, touch: boolean): void;
  dblclick(): void;
}

type Gesture =
  | { t: 'pan'; x0: number; y0: number; dx: number; dy: number; moved: number; type?: string }
  | { t: 'pinch'; d0: number; k0: number; wx: number; wy: number };

/** Movement up to this many px still counts as a tap */
const tapTolerance = (type?: string) => (type === 'touch' ? 9 : 4);

/** Attach the listeners; returns a function that removes them again. */
export function attachGestures(cv: HTMLCanvasElement, view: MapView, h: GestureHandlers): () => void {
  const ptrs = new Map<number, Pt>();
  let g: Gesture | null = null, lastTap: { t: number; x: number; y: number } | null = null;
  const loc = (e: PointerEvent | MouseEvent): Pt => { const r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };

  const down = (e: PointerEvent) => {
    const p = loc(e); ptrs.set(e.pointerId, p);
    if (ptrs.size === 1) g = { t: 'pan', x0: p.x, y0: p.y, dx: view.dx, dy: view.dy, moved: 0, type: e.pointerType };
    else if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      g = { t: 'pinch', d0: Math.hypot(a.x - b.x, a.y - b.y), k0: view.k, wx: view.wx((a.x + b.x) / 2), wy: view.wy((a.y + b.y) / 2) };
    }
    cv.setPointerCapture(e.pointerId);
  };
  const move = (e: PointerEvent) => {
    const p = loc(e);
    if (!ptrs.has(e.pointerId)) {                      // hover (mouse)
      if (e.pointerType === 'mouse') h.hover(p);
      return;
    }
    ptrs.set(e.pointerId, p);
    if (g?.t === 'pan') {
      g.moved = Math.max(g.moved, Math.hypot(p.x - g.x0, p.y - g.y0));
      if (g.moved < tapTolerance(g.type)) return;
      h.pan();
      view.dx = g.dx + p.x - g.x0; view.dy = g.dy + p.y - g.y0; view.redraw(); view.onchange();
    } else if (g?.t === 'pinch' && ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      const k = clampZoom(g.k0 * Math.hypot(a.x - b.x, a.y - b.y) / g.d0);
      const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      view.k = k; view.dx = m.x - g.wx * k; view.dy = m.y - g.wy * k; view.redraw(); view.onchange();
    }
  };
  const up = (e: PointerEvent) => {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.delete(e.pointerId);
    if (g?.t === 'pinch') {                            // one finger left: keep panning with it, never a tap
      const p = [...ptrs.values()][0];
      g = ptrs.size === 1 ? { t: 'pan', x0: p.x, y0: p.y, dx: view.dx, dy: view.dy, moved: 99 } : null;
      return;
    }
    if (g?.t === 'pan' && g.moved < tapTolerance(g.type) && e.type === 'pointerup') {
      const p = loc(e), touch = g.type === 'touch';
      if (!h.tap(p)) {
        const now = performance.now();
        if (touch && lastTap && now - lastTap.t < 320 && Math.hypot(p.x - lastTap.x, p.y - lastTap.y) < 30) {
          view.zoomAt(p.x, p.y, 2); lastTap = null;
        } else {
          lastTap = { t: now, ...p };
          h.select(p, touch);
        }
      }
    }
    g = null;
  };
  const leave = () => h.leave();
  const wheel = (e: WheelEvent) => { e.preventDefault(); const p = loc(e); view.zoomAt(p.x, p.y, Math.exp(-e.deltaY * .0016)); };
  const dblclick = () => h.dblclick();

  cv.addEventListener('pointerdown', down);
  cv.addEventListener('pointermove', move);
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  cv.addEventListener('pointerleave', leave);
  cv.addEventListener('wheel', wheel, { passive: false });
  cv.addEventListener('dblclick', dblclick);
  return () => {
    cv.removeEventListener('pointerdown', down);
    cv.removeEventListener('pointermove', move);
    cv.removeEventListener('pointerup', up); cv.removeEventListener('pointercancel', up);
    cv.removeEventListener('pointerleave', leave);
    cv.removeEventListener('wheel', wheel);
    cv.removeEventListener('dblclick', dblclick);
  };
}
