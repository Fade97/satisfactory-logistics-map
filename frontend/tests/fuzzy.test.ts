import { describe, expect, test } from 'vitest';
import { fuzzy, matches } from '../src/lib/fuzzy';

const ITEMS = ['Steel Beam', 'Steel Pipe', 'Steel Ingot', 'Iron Ore', 'Iron Plate', 'Iron Ingot', 'Iron Rod', 'Reinforced Iron Plate',
  'Copper Ore', 'Copper Ingot', 'Copper Sheet', 'Wire', 'Quickwire', 'Caterium Ore', 'Heavy Modular Frame', 'Plastic',
  'Supercomputer', 'Aluminum Ingot', 'Concrete'];
const top = (q: string) => fuzzy(q, ITEMS, x => x, 3)[0];

describe('fuzzy item search', () => {
  test.each([
    ['stel beam', 'Steel Beam'], ['steelbeam', 'Steel Beam'], ['quickwier', 'Quickwire'], ['catrium', 'Caterium Ore'],
    ['reinforsed', 'Reinforced Iron Plate'], ['hmf', 'Heavy Modular Frame'], ['plastk', 'Plastic'],
  ])('typo/abbreviation "%s" → %s', (q, want) => expect(top(q)).toBe(want));

  test.each([
    ['Stahlträger', 'Steel Beam'], ['stahltrager', 'Steel Beam'], ['Stahltraeger', 'Steel Beam'], ['Kupferblech', 'Copper Sheet'],
    ['Eisenerz', 'Iron Ore'], ['Eisenbarren', 'Iron Ingot'], ['Stahlrohr', 'Steel Pipe'], ['Aluminiumbarren', 'Aluminum Ingot'],
    ['Verstärkte Eisenplatte', 'Reinforced Iron Plate'], ['Schwerer modularer Rahmen', 'Heavy Modular Frame'], ['Kupferdraht', 'Wire'],
  ])('German "%s" → %s', (q, want) => expect(top(q)).toBe(want));

  test('no match', () => expect(fuzzy('xyz', ITEMS, x => x)).toEqual([]));
  test('empty query returns everything', () => expect(fuzzy('', ITEMS, x => x, 100)).toHaveLength(ITEMS.length));
  test('matches for filters', () => {
    expect(matches('kupfr', 'Copper Sheet')).toBe(true);
    expect(matches('kupfer', 'Steel Beam')).toBe(false);
  });
});
