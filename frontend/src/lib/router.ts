// Hash-Router: #/map?x=..&y=..&z=..&sel=kind:key · #/production · #/power · #/logistics · #/history · #/planner · #/kiosk
// Alte deutsche Adressen (#/karte, ?ware=, ?folge= …) werden auf die englischen umgeschrieben.
import { writable } from 'svelte/store';

export interface Route { page: string; q: URLSearchParams }
export const PAGE_ALIAS: Record<string, string> = {
  lage: 'overview', karte: 'map', produktion: 'production', strom: 'power', logistik: 'logistics', verlauf: 'history', rechner: 'planner',
};
const PARAM_ALIAS: Record<string, string> = { ware: 'item', folge: 'follow' };
function parse(): Route {
  const h = location.hash.replace(/^#\/?/, '');
  const [p, qs] = h.split('?');
  const q = new URLSearchParams(qs || '');
  for (const [de, en] of Object.entries(PARAM_ALIAS)) if (q.has(de) && !q.has(en)) { q.set(en, q.get(de)!); q.delete(de); }
  if (q.get('pick') === 'bauplatz') q.set('pick', 'site');
  return { page: PAGE_ALIAS[p] || p || 'overview', q };
}
export const route = writable<Route>(parse());
addEventListener('hashchange', () => route.set(parse()));

export function go(page: string, q: Record<string, string | number> = {}) {
  const s = new URLSearchParams(Object.entries(q).map(([k, v]) => [k, String(v)])).toString();
  location.hash = '#/' + page + (s ? '?' + s : '');
}
/** Karte auf ein Objekt oder einen Ort springen lassen */
export const toMap = (sel: string, x?: number, y?: number) =>
  go('map', { sel, ...(x !== undefined ? { x: Math.round(x), y: Math.round(y!), z: 1.5 } : {}) });

/** Adresszeile ohne neuen Verlaufseintrag aktualisieren (Kartenposition). */
export function replaceQuery(page: string, q: Record<string, string>) {
  const s = new URLSearchParams(q).toString();
  history.replaceState(null, '', '#/' + page + (s ? '?' + s : ''));
}
