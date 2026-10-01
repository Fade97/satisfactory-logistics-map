// Display names for items and buildings: English (as in the server's game) or German, switchable.
// Internally English names are used everywhere — only the display changes. Translations: AyKarambo/Ficsit.Schematics (MIT).
import { derived } from 'svelte/store';
import DE from './names_de.json';
import { prefs } from './prefs';

const de = DE as Record<string, string>;
/** Store with a translation function: `$tn('Iron Ore')` → "Eisenerz" when German is selected. */
export const tn = derived(prefs, p => (name: string | null | undefined) => {
  if (!name) return '';
  // Extractor recipes arrive as "Extracting Iron Ore"; the prefix follows the interface language
  const m = name.match(/^(?:Extracting|Abbau) (.+)$/);
  if (m) return (p.ui === 'de' ? 'Abbau ' : 'Extracting ') + (p.lang === 'de' ? (de[m[1]] ?? m[1]) : m[1]);
  return p.lang === 'de' ? translate(name) : name;
});

/** Also compound names: "Alternate: Steel Rod", "3,2× Assembler". */
function translate(name: string): string {
  if (de[name]) return de[name];
  let m = name.match(/^Alternate: (.+)$/);
  if (m) return 'Alternativ: ' + (de[m[1]] ?? m[1]);
  m = name.match(/^(.*?)([\d.,]+× )(.+)$/);
  if (m && de[m[3]]) return m[1] + m[2] + de[m[3]];
  return name;
}
/** Both names for search (fuzzy over English and German). */
export const both = (name: string) => (de[name] ? name + ' ' + de[name] : name);
export const deName = (name: string) => de[name];
