// Svelte actions shared by components.

/** Move the element to <body>, remove it again on destroy. For overlays inside `.panel` (clip-path) or under a
    parent with `transform` — position:fixed alone doesn't escape those. */
export function portal(node: HTMLElement) {
  document.body.appendChild(node);
  return { destroy() { node.remove(); } };
}
