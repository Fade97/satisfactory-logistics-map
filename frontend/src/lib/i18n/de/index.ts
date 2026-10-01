// German UI texts, split by area. Key = English source text, value = German.
import app from './app';
import map from './map';
import pages from './pages';
import parts from './parts';

const DE: Record<string, string> = { ...app, ...map, ...pages, ...parts };
export default DE;
