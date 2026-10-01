// Every text translated with $t('…') or tr('…') needs a German entry.
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import DE from '../src/lib/i18n/de';
import { translate } from '../src/lib/i18n';

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
    for (const m of readFileSync(f, 'utf8').matchAll(KEY)) keys.set(m[1].replace(/\\'/g, "'").replace(/\\n/g, '\n'), f);
  }
  it('has German for every key', () => {
    const missing = [...keys].filter(([k]) => !(k in DE)).map(([k, f]) => `${f.split('/src/')[1]}: ${k}`);
    expect(missing).toEqual([]);
  });
  it('keeps placeholders', () => {
    const bad = Object.entries(DE).filter(([k, v]) => {
      const a = (k.match(/\{\w+\}/g) || []).sort().join(), b = (v.match(/\{\w+\}/g) || []).sort().join();
      return a !== b;
    }).map(([k]) => k);
    expect(bad).toEqual([]);
  });
  it('fills placeholders', () => {
    expect(translate('en', '{n} machines', { n: 3 })).toBe('3 machines');
    expect(translate('de', 'Map')).toBe('Karte');
  });
});
