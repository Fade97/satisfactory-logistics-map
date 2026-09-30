// Englische Texte: gemeinsame Begriffe (Zustände, Status) — auch als dynamische Schlüssel genutzt: $t(m.state)
const en: Record<string, string> = {
  'läuft': 'running', 'teilweise': 'partial', 'steht': 'stopped', 'pausiert': 'paused', 'aus': 'off',
  'aktiv': 'active', 'im Aufbau': 'under construction', 'Puffer': 'buffer', 'stillgelegt': 'decommissioned',
  'Beladen': 'Load', 'Entladen': 'Unload', 'gemischt': 'mixed', 'ohne Plattform': 'no platform',
  'rein': 'pure', 'normal': 'normal', 'unrein': 'impure',
};
export default en;
