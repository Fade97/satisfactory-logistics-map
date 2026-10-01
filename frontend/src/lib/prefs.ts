// Personal settings per browser (no login): who am I, start page, map follows me, last position.
import { writable } from 'svelte/store';
import { KEYS, loadJson, saveJson } from './storage';

// ui = interface language (English by default), lang = language of item names
export interface Prefs { me: string; start: string; followMe: boolean; lastView: { x: number; y: number; z: number } | null; lang: 'en' | 'de'; ui: 'en' | 'de' }
const init: Prefs = { me: '', start: 'overview', followMe: false, lastView: null, lang: 'en', ui: 'en', ...loadJson<Partial<Prefs>>(KEYS.prefs, {}) };
export const prefs = writable<Prefs>(init);
prefs.subscribe(v => saveJson(KEYS.prefs, v));

/** Remember the last map position — throttled, this is called on every pan. */
let timer = 0;
export function rememberView(x: number, y: number, z: number) {
  clearTimeout(timer);
  timer = window.setTimeout(() => prefs.update(p => ({ ...p, lastView: { x: Math.round(x), y: Math.round(y), z: +z.toFixed(3) } })), 800);
}
