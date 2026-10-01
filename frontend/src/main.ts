import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';
import { get } from 'svelte/store';
import { lang } from './lib/i18n';

document.documentElement.lang = get(lang);

export default mount(App, { target: document.getElementById('app')! });

// installable as an app; service worker only in production builds (in the Vite dev server it interferes with reloading)
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
