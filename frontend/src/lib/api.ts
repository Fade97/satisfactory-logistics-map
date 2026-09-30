// Datenzugriff: pollt die API mit ETag, hält den Stand in Svelte-Stores.
import { writable, type Writable } from 'svelte/store';
import type { Live, Stations, Factory, Geo, Node, Status, Progress, GameEvent, Pin } from './types';

const etags: Record<string, string> = {};
let cached = false;                        // letzte Antworten kamen aus dem Service-Worker-Cache

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
export const collectibles: Writable<any | null> = writable(null);
export const storage: Writable<any[] | null> = writable(null);
export const sink: Writable<any | null> = writable(null);
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
      online.set(!cached);                     // Antwort aus dem Offline-Cache des Service Workers = nicht verbunden
    } catch { online.set(false); }
  };
  run();
  return setInterval(run, every);
}

let lastEvent = 0;
async function pollEvents() {
  try {
    const r = await fetch('/api/events?limit=200');
    const d: GameEvent[] = await r.json();
    if (d.length && d[0].id !== lastEvent) { lastEvent = d[0].id; events.set(d); }
  } catch { /* offline, nächster Versuch */ }
}

export async function loadPins() {
  try { pins.set(await (await fetch('/api/pins')).json()); } catch { /* */ }
}
export async function loadTrails() {
  try { trails.set(await (await fetch('/api/trails')).json()); } catch { /* */ }
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
  const r = await fetch(`/api/series?${q}&since=${Math.floor(since)}`);
  return r.json() as Promise<{ res: string; data: Record<string, [number, number][]> }>;
}

// ---------------------------------------------------------------- Schreiben (Passwort)
const PW_KEY = 'fgmap.pw', AUTHOR_KEY = 'fgmap.author';
export const password = writable<string>(localStorage.getItem(PW_KEY) || '');
export const author = writable<string>(localStorage.getItem(AUTHOR_KEY) || '');
password.subscribe(v => v ? localStorage.setItem(PW_KEY, v) : localStorage.removeItem(PW_KEY));
author.subscribe(v => localStorage.setItem(AUTHOR_KEY, v));

let pw = '';
password.subscribe(v => (pw = v));

export async function post(path: string, body: unknown): Promise<any> {
  const r = await fetch('/api/' + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Map-Password': pw }, body: JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({}));
  if (r.status === 403) password.set('');
  if (!r.ok) throw new Error(d.error || 'Fehler ' + r.status);
  return d;
}
export const checkPassword = (p: string) =>
  fetch('/api/auth', { method: 'POST', headers: { 'X-Map-Password': p } }).then(r => r.ok);

addEventListener('offline', () => online.set(false));
addEventListener('online', () => online.set(true));
