import { describe, expect, test, vi } from 'vitest';
import { measureStats, fmtArea } from '../src/lib/map/measure';
import { computeFlow, flowItemList } from '../src/lib/map/flow';
import { tipTitle, tipText } from '../src/lib/map/tooltip';
import { minPoints } from '../src/lib/map/draw';
import { stationKey, stationVisible, factoryColor } from '../src/lib/scene';
import { C, fmtDist, factoryStatusColor, purityRank, purityLabel } from '../src/lib/fmt';
import { loadJson } from '../src/lib/storage';
import type { MapObj } from '../src/lib/mapview';
import type { Factory, Stations } from '../src/lib/types';

describe('measuring', () => {
  test('needs two points', () => {
    expect(measureStats(null)).toBeNull();
    expect(measureStats([[0, 0]])).toBeNull();
  });
  test('line: length, straight distance, material, no area', () => {
    const s = measureStats([[0, 0], [30, 40], [30, 100]])!;
    expect(s.len).toBe(110);
    expect(s.direct).toBeCloseTo(Math.hypot(30, 100));
    expect(s.rails).toBe(10);                 // ceil(110 / 12)
    expect(s.belts).toBe(2);                  // ceil(110 / 56)
    expect(measureStats([[0, 0], [100, 0]])!.area).toBe(0);
  });
  test('area of a square, closed automatically', () => {
    const s = measureStats([[0, 0], [80, 0], [80, 80], [0, 80]])!;
    expect(s.area).toBe(6400);
    expect(s.foundations).toBe(100);          // 8 × 8 m each
    expect(s.len).toBe(240);                  // open polyline, last edge not counted
  });
  test('formatting', () => {
    expect(fmtDist(740.4)).toBe('740 m');
    expect(fmtDist(1250)).toBe('1.25 km');
    expect(fmtArea(2.5e6)).toBe('2.50 km²');
    expect(fmtArea(640)).toBe('640 m²');
  });
});

const fac = {
  machines: [
    { id: 'm1', out: [{ item: 'Iron Plate', rate: 20 }], inp: [{ item: 'Iron Ingot', rate: 30 }] },
    { id: 'm2', out: [{ item: 'Screw', rate: 40 }], inp: [{ item: 'Iron Plate', rate: 10 }] },
  ],
  generators: [{ id: 'g1', fuel: 'Coal' }],
  factories: [{ key: 'f1', out: [{ item: 'Iron Plate', rate: 10 }], inp: [] }, { key: 'f2', out: [], inp: [{ item: 'Coal', rate: 1 }] }],
  balance: [{ item: 'Screw' }, { item: 'Coal' }],
} as unknown as Factory;
const st = {
  trucks: [{ id: 'Persistent_Level:PersistentLevel.Truck_1', items: [{ item: 'Iron Plate', amount: 5 }] }],
  trains: [{ id: 'Level.Train_2', items: [{ item: 'Coal', amount: 5 }] }],
} as unknown as Stations;

describe('item flow', () => {
  test('off without an item', () => expect(computeFlow('', fac, st, [], {})).toBeNull());
  test('producers, consumers, stations, factories', () => {
    const f = computeFlow('Iron Plate', fac, st, [], { 'Iron Plate': [[[0, 0], [1, 1]]] })!;
    expect([f.prod, f.cons, f.np, f.nc, f.ns]).toEqual([20, 10, 1, 1, 1]);
    expect([...f.keys].sort()).toEqual(['factory:f1', 'machine:m1', 'machine:m2', 'station:Truck_1']);
    expect(f.paths).toHaveLength(1);
  });
  test('generators burning the item count as consumers', () => {
    const f = computeFlow('Coal', fac, st, [{ id: 'n1', item: 'Coal' }] as any, null)!;
    expect(f.nc).toBe(1);
    expect(f.keys).toEqual(new Set(['generator:g1', 'station:Train_2', 'node:n1', 'factory:f2']));
    expect(f.paths).toEqual([]);
  });
  test('item list: belts plus balance, unique and sorted', () => {
    expect(flowItemList({ Wire: [], Coal: [] }, fac, 'en')).toEqual(['Coal', 'Screw', 'Wire']);
  });
});

const obj = (kind: string, data: any, label?: string) => ({ kind, data, label }) as MapObj;
const tn = (s: string | null | undefined) => (s ? '«' + s + '»' : '');

describe('map tooltip', () => {
  test('title: item names for machines, nodes, generators, else the label', () => {
    expect(tipTitle(obj('machine', { recipe: 'Iron Plate', name: 'Constructor' }), tn)).toBe('«Iron Plate»');
    expect(tipTitle(obj('machine', { recipe: null, name: 'Miner' }), tn)).toBe('«Miner»');
    expect(tipTitle(obj('node', { item: 'Coal' }), tn)).toBe('«Coal»');
    expect(tipTitle(obj('generator', { name: 'Coal Generator' }), tn)).toBe('«Coal Generator»');
    expect(tipTitle(obj('station', {}, 'North'), tn)).toBe('North');
    expect(tipTitle(obj('pin', {}), tn)).toBe('');
  });
  test('text per kind', () => {
    expect(tipText(obj('station', { kind: 'train', mode: 'load', items: [{ item: 'Coal' }, { item: 'Wire' }] }), tn))
      .toBe('Train station · Load · «Coal», «Wire»');
    expect(tipText(obj('machine', { name: 'Smelter', state: 'stopped', pct: 0, why: 'Missing: Iron Ore' }), tn))
      .toBe('«Smelter» · stopped 0 % · Missing: Iron Ore');
    expect(tipText(obj('node', { used: true, rate: 120 }), tn)).toBe('occupied · 120/min');
    expect(tipText(obj('player', { online: null }), tn)).toBe('as of the save');
    expect(tipText(obj('truck', { cargo: { item: 'Coal' }, speed: 41.6 }), tn)).toBe('«Coal» · 42 km/h');
    expect(tipText(obj('train', { speed: null }), tn)).toBe('Position from the save');
    expect(tipText(obj('factory', { n: 12, states: { stopped: 3 } }), tn)).toBe('12 machines · 3 stopped');
    expect(tipText(obj('generator', { producing: true, cap: 75 }), tn)).toBe('producing 75 MW');
    expect(tipText(obj('collectible', { pos: [1, 2, 30] }), tn)).toBe('not collected yet · height 30 m');
    expect(tipText(obj('other', {}), tn)).toBe('');
  });
});

describe('shared helpers', () => {
  test('station key and filter chips', () => {
    expect(stationKey({ id: 'Persistent_Level:PersistentLevel.Station_7' })).toBe('station:Station_7');
    const all = { truck: true, train: true, load: true, unload: true };
    expect(stationVisible({ kind: 'truck', mode: 'load' }, all)).toBe(true);
    expect(stationVisible({ kind: 'truck', mode: 'load' }, { ...all, truck: false })).toBe(false);
    expect(stationVisible({ kind: 'train', mode: 'unload' }, { ...all, unload: false })).toBe(false);
    expect(stationVisible({ kind: 'train', mode: 'mixed' }, { ...all, load: false })).toBe(true);
    expect(stationVisible({ kind: 'train', mode: 'none' }, { ...all, load: false, unload: false })).toBe(false);
  });
  test('factory status colour: live clusters and time travel shares agree', () => {
    expect(factoryColor({ n: 10, starved: 4, states: {} })).toBe(C.bad);
    expect(factoryColor({ n: 10, starved: 1, states: { running: 9 } })).toBe(C.warn);
    expect(factoryColor({ n: 10, starved: 0, states: { running: 2, partial: 1 } })).toBe(C.ok);
    expect(factoryColor({ n: 10, starved: 0, states: { stopped: 10 } })).toBe(C.full);
    expect(factoryStatusColor(31 / 100, 0)).toBe(C.bad);
    expect(factoryStatusColor(30 / 100, 0)).toBe(C.warn);
    expect(factoryStatusColor(0, 21 / 100)).toBe(C.ok);
  });
  test('purity rank and label', () => {
    expect(['impure', null, 'pure', 'normal'].sort((a, b) => purityRank(b) - purityRank(a))).toEqual(['pure', 'normal', 'impure', null]);
    expect(purityLabel('pure')).toBe('pure');
    expect(purityLabel(null)).toBe('?');
    expect(purityLabel('weird', 'unknown')).toBe('unknown');
  });
  test('note shapes need 1/2/3 points', () => expect(['point', 'line', 'area'].map(s => minPoints(s as any))).toEqual([1, 2, 3]));
  test('storage falls back without localStorage or on broken JSON', () => {
    expect(loadJson('fgmap.layers', { a: 1 })).toEqual({ a: 1 });
    const stored: Record<string, string> = { bad: '{oops', nul: 'null', ok: '[1,2]' };
    vi.stubGlobal('localStorage', { getItem: (k: string) => stored[k] ?? null });
    try {
      expect(loadJson('bad', 'fb')).toBe('fb');
      expect(loadJson('nul', 'fb')).toBe('fb');
      expect(loadJson('missing', 'fb')).toBe('fb');
      expect(loadJson('ok', [])).toEqual([1, 2]);
    } finally { vi.unstubAllGlobals(); }
  });
});
