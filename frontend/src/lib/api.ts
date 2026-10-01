// Data access: polls the API with ETags, keeps the state in Svelte stores.
import { writable, type Writable } from 'svelte/store';
import type { Live, Stations, Factory, Geo, Node, Status, Progress, GameEvent, Pin, Collectibles, StorageBox, Sink, DetailLayer } from './types';
import { tr } from './i18n';
import { KEYS } from './storage';

/** fetch + JSON; throws on HTTP errors (message = the server's `error` field if any), so error bodies never end up as data. */
export async function fetchJson<T = any>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    const e = await r.json().catch(() => null);
    throw new Error(e?.error || tr('Error') + ' ' + r.status);
  }
  return r.json();
}

const etags: Record<string, string> = {};
let cached = false;                        // last responses came from the service worker cache

async function getJson<T>(name: string): Promise<T | null> {
  const h: Record<string, string> = {};
  if (etags[name]) h['If-None-Match'] = etags[name];
  const r = await fetch('/api/' + name, { headers: h });
  if (r.status === 304) return null;
  if (!r.ok) throw new Error(name + ': ' + r.status);
  if (r.headers.get('X-From-Cache')) cached = true; else if (name === 'status') cached = false;
  const t = r.headers.get('ETag');
  if (t) etags[name] = t;
  return r.json();
}

export const live: Writable<Live | null> = writable(null);
export const stations: Writable<Stations | null> = writable(null);
export const factory: Writable<Factory | null> = writable(null);
export const geo: Writable<Geo | null> = writable(null);
export const nodes: Writable<Node[] | null> = writable(null);
export const powerlines: Writable<number[][] | null> = writable(null);
export const flow: Writable<Record<string, number[][][]> | null> = writable(null);
export const collectibles: Writable<Collectibles | null> = writable(null);
export const storage: Writable<StorageBox[] | null> = writable(null);
export const sink: Writable<Sink | null> = writable(null);
export const status: Writable<Status | null> = writable(null);
export const progress: Writable<Progress | null> = writable(null);
export const events: Writable<GameEvent[]> = writable([]);
export const pins: Writable<Pin[]> = writable([]);
export const trails: Writable<Record<string, number[][]>> = writable({});
export const online: Writable<boolean> = writable(true);

function poll<T>(name: string, store: Writable<T | null>, every: number) {
  const run = async () => {
    try {
      const d = await getJson<T>(name);
      if (d !== null) store.set(d);
      online.set(!cached);                     // response from the service worker's offline cache = not connected
    } catch { online.set(false); }
  };
  run();
  return setInterval(run, every);
}

let lastEvent = 0;
async function pollEvents() {
  try {
    const d = await fetchJson<GameEvent[]>('/api/events?limit=200');
    if (d.length && d[0].id !== lastEvent) { lastEvent = d[0].id; events.set(d); }
  } catch { /* offline, next attempt */ }
}

export async function loadPins() {
  try { pins.set(await fetchJson<Pin[]>('/api/pins')); } catch { /* offline, keep the last state */ }
}
export async function loadTrails() {
  try { trails.set(await fetchJson<Record<string, number[][]>>('/api/trails')); } catch { /* offline, keep the last state */ }
}

export function start() {
  poll('live', live, 5000);
  poll('status', status, 5000);
  poll('stations', stations, 60000);
  poll('factory', factory, 30000);
  poll('geo', geo, 300000);
  poll('nodes', nodes, 300000);
  poll('powerlines', powerlines, 300000);
  poll('flow', flow, 300000);
  poll('collectibles', collectibles, 300000);
  poll('storage', storage, 120000);
  poll('sink', sink, 60000);
  poll('progress', progress, 300000);
  pollEvents(); setInterval(pollEvents, 10000);
  loadPins(); setInterval(loadPins, 60000);
  loadTrails(); setInterval(loadTrails, 30000);
}

export async function series(keys: string[], since: number) {
  const q = keys.map(k => 'k=' + encodeURIComponent(k)).join('&');
  return fetchJson<{ res: string; data: Record<string, [number, number][]> }>(`/api/series?${q}&since=${Math.floor(since)}`);
}

/** Detail layer (binary package, ~180 KB gzip): header [n tiles, n walls] (Int32), tiles x/y/z (Int16 ×3),
    tile meta (Uint8, padded to 2 bytes), walls ax/ay/bx/by/z (Int16 ×5); null if not available. */
export async function loadDetail(): Promise<DetailLayer | null> {
  const r = await fetch('/api/detail');
  if (!r.ok) return null;
  const buf = await r.arrayBuffer();
  const h = new Int32Array(buf, 0, 2), nt = h[0], nw = h[1];
  const tiles = new Int16Array(buf, 8, 3 * nt), tmeta = new Uint8Array(buf, 8 + 6 * nt, nt);
  const wOff = 8 + 6 * nt + nt + ((nt % 2) ? 1 : 0);
  return { tiles, tmeta, walls: new Int16Array(buf, wOff, 5 * nw) };
}

// ---------------------------------------------------------------- Writing (password)
export const password = writable<string>(localStorage.getItem(KEYS.password) || '');
export const author = writable<string>(localStorage.getItem(KEYS.author) || '');
password.subscribe(v => v ? localStorage.setItem(KEYS.password, v) : localStorage.removeItem(KEYS.password));
author.subscribe(v => localStorage.setItem(KEYS.author, v));

let pw = '';
password.subscribe(v => (pw = v));

export async function post(path: string, body: unknown): Promise<any> {
  const r = await fetch('/api/' + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Map-Password': pw }, body: JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({}));
  if (r.status === 403) password.set('');
  if (!r.ok) throw new Error(d.error || tr('Error') + ' ' + r.status);
  return d;
}
export const checkPassword = (p: string) =>
  fetch('/api/auth', { method: 'POST', headers: { 'X-Map-Password': p } }).then(r => r.ok);

addEventListener('offline', () => online.set(false));
addEventListener('online', () => online.set(true));
