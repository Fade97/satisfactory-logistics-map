<script lang="ts">
  // Create/edit a note or rename a factory — both require the shared password.
  import { untrack } from 'svelte';
  import { password, author, post, checkPassword } from './api';
  import { C } from './fmt';
  import { t, tr, lx, lxr } from './i18n';

  let { pin, onclose }: { pin: any; onclose: (saved: boolean) => void } = $props();
  const CATS: [string, string, string][] = [
    ['planned', tr('Planned'), C.accent], ['problem', tr('Problem'), C.bad], ['resource', tr('Resource'), C.ok],
    ['meetup', tr('Meeting point'), C.unload], ['note', tr('Note'), C.neutral],
  ];
  // The form fields start from the pin the editor was opened with (later prop changes don't reset the input)
  const initial = untrack(() => pin);
  const isFactory = !!initial.factory;
  let text = $state(isFactory ? initial.factory.name : initial.text || '');
  let fstatus = $state(isFactory ? initial.factory.status || 'active' : 'active');
  const FST: [string, string, string][] = [
    ['active', tr('Active'), tr('Warns about missing input')], ['building', tr('Under construction'), tr('No warnings')],
    ['buffer', tr('Buffer/stock'), tr('Standstill is intended')], ['decommissioned', tr('Decommissioned'), tr('No warnings')],
  ];
  let cat = $state(initial.cat || 'planned');
  let pw = $state($password);
  let name = $state($author);
  let err = $state(''), busy = $state(false);

  async function save() {
    err = ''; busy = true;
    try {
      if (!$password || pw !== $password) {
        if (!(await checkPassword(pw))) throw new Error(tr('Wrong password. Ask the map operator for the current one.'));
        password.set(pw);
      }
      author.set(name.trim());
      if (isFactory) await post('factory-name', { key: pin.factory.key, name: text.trim() === pin.factory.auto ? '' : text.trim(), status: fstatus, author: name.trim() });
      else await post('pins', { ...pin, text: text.trim(), cat, color: CATS.find(c => c[0] === cat)![2], author: name.trim() || 'anonymous' });
      onclose(true);
    } catch (e: any) { err = lxr(e.message); } finally { busy = false; }
  }
  async function del() {
    if (!confirm(tr('Delete note?'))) return;
    busy = true;
    try { await post('pins/' + pin.id + '/delete', {}); onclose(true); } catch (e: any) { err = lxr(e.message); } finally { busy = false; }
  }
</script>

<div class="modal" role="dialog" aria-modal="true" aria-label={isFactory ? $t('Rename factory') : $t('Note')}>
  <button class="bg" aria-label={$t('Close')} onclick={() => onclose(false)}></button>
  <form class="panel box" onsubmit={e => { e.preventDefault(); save(); }}>
    <h2>{isFactory ? $t('Edit factory') : pin.id ? $t('Edit note') : $t('New note')}</h2>
    {#if isFactory}
      <label>{$t('Name')}<input class="field" bind:value={text} maxlength="60" /></label>
      <p class="muted small">{$t('Automatic name: {auto}. Leave empty to restore it.', { auto: $lx(pin.factory.auto) })}</p>
      <div class="cats">
        {#each FST as [k, l, h]}<button type="button" class:on={fstatus === k} onclick={() => (fstatus = k)} title={h}>{l}</button>{/each}
      </div>
      <p class="muted small">{FST.find(x => x[0] === fstatus)?.[2]}</p>
    {:else}
      <div class="cats">
        {#each CATS as [k, l, c]}<button type="button" class:on={cat === k} onclick={() => (cat = k)}><span class="dot" style="background:{c}"></span>{l}</button>{/each}
      </div>
      <label>{$t('Text')}<textarea class="field" bind:value={text} rows="4" maxlength="500" placeholder={$t('What should go here?')}></textarea></label>
    {/if}
    <div class="two">
      <label>{$t('Your name')}<input class="field" bind:value={name} maxlength="40" autocomplete="nickname" /></label>
      <label>{$t('Password')}<input class="field" type="password" bind:value={pw} autocomplete="current-password" /></label>
    </div>
    {#if err}<p class="err">{err}</p>{/if}
    <div class="act">
      {#if pin.id}<button type="button" class="btn" onclick={del} disabled={busy}>{$t('Delete')}</button>{/if}
      <span style="flex:1"></span>
      <button type="button" class="btn" onclick={() => onclose(false)}>{$t('Cancel')}</button>
      <button class="btn primary" disabled={busy || (!isFactory && !text.trim()) || !pw}>{$t('Save')}</button>
    </div>
  </form>
</div>

<style>
  .modal { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; padding: 12px; }
  .bg { position: absolute; inset: 0; background: #000a; border: none; }
  .box { position: relative; width: min(460px, 100%); padding: 18px; display: flex; flex-direction: column; gap: 12px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--text2); }
  .two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .cats { display: flex; flex-wrap: wrap; gap: 4px; }
  .cats button { background: var(--steel); border: 1px solid var(--seam); padding: 4px 10px; font-size: 13px; display: inline-flex; gap: 6px; align-items: center; }
  .cats button.on { border-color: var(--ficsit); }
  .act { display: flex; gap: 8px; }
  .err { color: var(--bad); margin: 0; font-size: 13px; }
  .small { font-size: 12px; margin: -6px 0 0; }
  textarea { resize: vertical; }
</style>
