import { describe, expect, test } from 'vitest';
import { layout, W, H } from '../src/lib/flowlayout';

const fmt = (n: number) => String(Math.round(n * 10) / 10);
// Iron Plate: ore → ingot → plate, plus a surplus
const res = {
  raw: [{ item: 'Iron Ore', rate: 90 }],
  surplus_used: [{ item: 'Iron Ingot', rate: 10, available: 20 }],
  steps: [
    { recipe: 'Iron Ingot', building: 'Smelter', machines: 3, out: [{ item: 'Iron Ingot', rate: 90 }], inp: [{ item: 'Iron Ore', rate: 90 }] },
    { recipe: 'Iron Plate', building: 'Constructor', machines: 5, out: [{ item: 'Iron Plate', rate: 66.7 }], inp: [{ item: 'Iron Ingot', rate: 100 }] },
  ],
  targets: [{ item: 'Iron Plate', rate: 66.7 }],
};

describe('chain diagram layout', () => {
  const g = layout(res, fmt);
  test('target step becomes the target box (no duplicate box)', () => {
    expect(g.nodes.filter(n => n.kind === 'target')).toHaveLength(1);
    expect(g.nodes.find(n => n.kind === 'target')!.label).toBe('Iron Plate');
    expect(g.nodes).toHaveLength(4);
  });
  test('layers run left to right', () => {
    for (const e of g.edges) expect(e.b.layer).toBeGreaterThan(e.a.layer);
  });
  test('rates per edge: ingot split between smelter and surplus', () => {
    const ins = g.edges.filter(e => e.b.label === 'Iron Plate');
    expect(ins.reduce((a, e) => a + e.rate, 0)).toBeCloseTo(100, 5);
  });
  test('no overlapping boxes', () => {
    for (const a of g.nodes) for (const b of g.nodes) if (a !== b)
      expect(a.x + W <= b.x || b.x + W <= a.x || a.y + H <= b.y || b.y + H <= a.y).toBe(true);
  });
  test('ports lie within the boxes', () => {
    for (const e of g.edges) {
      expect(e.y1).toBeGreaterThanOrEqual(e.a.y); expect(e.y1).toBeLessThanOrEqual(e.a.y + H);
      expect(e.y2).toBeGreaterThanOrEqual(e.b.y); expect(e.y2).toBeLessThanOrEqual(e.b.y + H);
    }
  });
});
