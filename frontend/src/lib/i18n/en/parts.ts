// Englische Texte: gemeinsame Begriffe (Zustände, Status) — auch als dynamische Schlüssel genutzt: $t(m.state)
const en: Record<string, string> = {
  'läuft': 'running', 'teilweise': 'partial', 'steht': 'stopped', 'pausiert': 'paused', 'aus': 'off',
  'aktiv': 'active', 'im Aufbau': 'under construction', 'Puffer': 'buffer', 'stillgelegt': 'decommissioned',
  'Beladen': 'Load', 'Entladen': 'Unload', 'gemischt': 'mixed', 'ohne Plattform': 'no platform',
  'rein': 'pure', 'normal': 'normal', 'unrein': 'impure',
  // fmt.ts
  ' Mio': 'M', ' Tsd': 'k', 'gerade eben': 'just now', 'vor {n} min': '{n} min ago', 'vor {n} h': '{n} h ago',
  'vor {n} Tagen': '{n} days ago', '{n} Tage': '{n} days',
  // flowlayout.ts
  '{rate}/min Rohstoff': '{rate}/min raw', '{rate}/min aus Überschuss': '{rate}/min from surplus', '{rate}/min Ziel': '{rate}/min target',
};
export default en;
