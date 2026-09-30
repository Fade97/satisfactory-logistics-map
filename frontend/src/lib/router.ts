// Hash-Router: #/karte?x=..&y=..&z=..&sel=kind:key · #/produktion · #/strom · #/logistik · #/verlauf · #/kiosk
import { writable } from 'svelte/store';

export interface Route { page: string; q: URLSearchParams }
function parse(): Route {
  const h = location.hash.replace(/^#\/?/, '');
  const [p, qs] = h.split('?');
  return { page: p || 'lage', q: new URLSearchParams(qs || '') };
}
export const route = writable<Route>(parse());
addEventListener('hashchange', () => route.set(parse()));

export function go(page: string, q: Record<string, string | number> = {}) {
  const s = new URLSearchParams(Object.entries(q).map(([k, v]) => [k, String(v)])).toString();
  location.hash = '#/' + page + (s ? '?' + s : '');
}
/** Karte auf ein Objekt oder einen Ort springen lassen */
export const toMap = (sel: string, x?: number, y?: number) =>
  go('karte', { sel, ...(x !== undefined ? { x: Math.round(x), y: Math.round(y!), z: 1.5 } : {}) });

/** Adresszeile ohne neuen Verlaufseintrag aktualisieren (Kartenposition). */
export function replaceQuery(page: string, q: Record<string, string>) {
  const s = new URLSearchParams(q).toString();
  history.replaceState(null, '', '#/' + page + (s ? '?' + s : ''));
}
