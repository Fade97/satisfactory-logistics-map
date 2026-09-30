// Englische Texte, nach Bereichen getrennt. Schlüssel = deutscher Text aus dem Quelltext.
import app from './app';
import map from './map';
import pages from './pages';
import parts from './parts';
import server from './server';

const EN: Record<string, string> = { ...app, ...map, ...pages, ...parts, ...server };
export default EN;
