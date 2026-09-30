// Anzeigenamen für Waren und Gebäude: englisch (wie im Spiel des Servers) oder deutsch, umschaltbar.
// Intern bleiben überall die englischen Namen — nur die Anzeige wechselt. Übersetzungen: AyKarambo/Ficsit.Schematics (MIT).
import { derived } from 'svelte/store';
import DE from './names_de.json';
import { prefs } from './prefs';

const de = DE as Record<string, string>;
/** Store mit Übersetzungsfunktion: `$tn('Iron Ore')` → „Eisenerz“, wenn Deutsch gewählt ist. */
export const tn = derived(prefs, p => (name: string | null | undefined) => {
  if (!name) return '';
  // Extraktor-Rezepte kommen als „Extracting Iron Ore“; das Präfix folgt der Sprache der Oberfläche
  const m = name.match(/^(?:Extracting|Abbau) (.+)$/);
  if (m) return (p.ui === 'de' ? 'Abbau ' : 'Extracting ') + (p.lang === 'de' ? (de[m[1]] ?? m[1]) : m[1]);
  return p.lang === 'de' ? translate(name) : name;
});

/** Auch zusammengesetzte Namen: „Alternate: Steel Rod“, „3,2× Assembler“. */
function translate(name: string): string {
  if (de[name]) return de[name];
  let m = name.match(/^Alternate: (.+)$/);
  if (m) return 'Alternativ: ' + (de[m[1]] ?? m[1]);
  m = name.match(/^(.*?)([\d.,]+× )(.+)$/);
  if (m && de[m[3]]) return m[1] + m[2] + de[m[3]];
  return name;
}
/** Beide Namen für die Suche (unscharf über englisch und deutsch). */
export const both = (name: string) => (de[name] ? name + ' ' + de[name] : name);
export const deName = (name: string) => de[name];
