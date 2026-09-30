import { describe, it, expect } from 'vitest';
import { serverText } from '../src/lib/i18n/server-de';

describe('Backend-Texte auf Deutsch', () => {
  it('übersetzt Ereignisse mit Platzhaltern', () => {
    expect(serverText('Ada is online')).toBe('Ada ist online');
    expect(serverText('Iron Plate Factory 2: 5 of 8 machines missing input')).toBe('Iron Plate-Fabrik 2: 5 von 8 Maschinen fehlt Material');
    expect(serverText('1× Assembler, 2× Miner Mk.2 built (Ada)')).toBe('1× Assembler, 2× Miner Mk.2 gebaut (Ada)');
  });
  it('übersetzt Gründe und Namen', () => {
    expect(serverText('Output full: Steel Beam')).toBe('Ausgang voll: Steel Beam');
    expect(serverText('Iron Ore Mining')).toBe('Iron Ore-Abbau');
    expect(serverText('Extracting Iron Ore')).toBe('Abbau Iron Ore');
  });
  it('lässt Unbekanntes stehen', () => {
    expect(serverText('Meine eigene Fabrik')).toBe('Meine eigene Fabrik');
  });
});
