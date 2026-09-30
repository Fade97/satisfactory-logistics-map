import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';
import { get } from 'svelte/store';
import { lang } from './lib/i18n';

document.documentElement.lang = get(lang);

export default mount(App, { target: document.getElementById('app')! });

// Installierbar als App; Service Worker nur im Produktionsbuild (im Vite-Dev-Server stört er das Neuladen)
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
