// Persönliche Einstellungen je Browser (kein Login): wer bin ich, Startseite, Karte folgt mir, letzte Position.
import { writable } from 'svelte/store';

// ui = Sprache der Oberfläche (Englisch Standard), lang = Sprache der Warennamen
export interface Prefs { me: string; start: string; followMe: boolean; lastView: { x: number; y: number; z: number } | null; lang: 'en' | 'de'; ui: 'en' | 'de' }
const KEY = 'fgmap.prefs';
const init: Prefs = { me: '', start: 'overview', followMe: false, lastView: null, lang: 'en', ui: 'en', ...JSON.parse(localStorage.getItem(KEY) || '{}') };
export const prefs = writable<Prefs>(init);
prefs.subscribe(v => localStorage.setItem(KEY, JSON.stringify(v)));

/** Letzte Kartenposition merken — gedrosselt, das wird bei jedem Verschieben aufgerufen. */
let t = 0;
export function rememberView(x: number, y: number, z: number) {
  clearTimeout(t);
  t = window.setTimeout(() => prefs.update(p => ({ ...p, lastView: { x: Math.round(x), y: Math.round(y), z: +z.toFixed(3) } })), 800);
}
