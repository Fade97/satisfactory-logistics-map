// Jeder Text, der mit $t('…') oder tr('…') übersetzt wird, braucht einen englischen Eintrag.
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import EN from '../src/lib/i18n/en';
// prefs.ts liest localStorage schon beim Import — für Node einen Ersatz setzen, dann erst laden
const mem = new Map<string, string>();
(globalThis as any).localStorage = { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => mem.set(k, v) };
const { translate } = await import('../src/lib/i18n');

function files(dir: string): string[] {
  return readdirSync(dir).flatMap(f => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? (f === 'i18n' ? [] : files(p)) : /\.(svelte|ts)$/.test(f) && f !== 'i18n.ts' ? [p] : [];
  });
}
const KEY = /(?:\$t|\btr)\(\s*'((?:[^'\\]|\\.)*)'/g;

describe('i18n', () => {
  const keys = new Map<string, string>();
  for (const f of files(join(__dirname, '../src'))) {
    for (const m of readFileSync(f, 'utf8').matchAll(KEY)) keys.set(m[1].replace(/\\'/g, "'"), f);
  }
  it('hat für jeden Schlüssel Englisch', () => {
    const missing = [...keys].filter(([k]) => !(k in EN)).map(([k, f]) => `${f.split('/src/')[1]}: ${k}`);
    expect(missing).toEqual([]);
  });
  it('Platzhalter bleiben erhalten', () => {
    const bad = Object.entries(EN).filter(([k, v]) => {
      const a = (k.match(/\{\w+\}/g) || []).sort().join(), b = (v.match(/\{\w+\}/g) || []).sort().join();
      return a !== b;
    }).map(([k]) => k);
    expect(bad).toEqual([]);
  });
  it('setzt Platzhalter ein', () => {
    expect(translate('de', '{n} Maschinen', { n: 3 })).toBe('3 Maschinen');
  });
});
