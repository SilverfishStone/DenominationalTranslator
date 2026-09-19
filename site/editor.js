// Suggest-edits mode: rewrite any explanation for an audience, then export the changes as a lang file
// (JSON) that a maintainer can drop straight into lang/. Drafts are kept in this browser's localStorage.
//
//   #/edit                    pick a starting view (audience)
//   #/edit/<audience>         scroll through every topic for that audience
//   #/edit/<audience>/<key>   same, opened at one entry

import { renderMarkdown } from './markdown.js';

const draftsKey = (aud) => `ingoodfaith.edits.${aud}`;
const NAME_KEY = 'ingoodfaith.editor.name';

const read = (key, fallback) => { try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; } };
const write = (key, value) => { try { localStorage.setItem(key, value); } catch { /* storage unavailable */ } };
const loadDrafts = (aud) => { try { return JSON.parse(read(draftsKey(aud), '{}')) ?? {}; } catch { return {}; } };
const saveDrafts = (aud, drafts) => write(draftsKey(aud), JSON.stringify(drafts));

const make = (tag, props = {}, ...children) => {
  const el = Object.assign(document.createElement(tag), props);
  el.append(...children);
  return el;
};

export function viewEditPicker(env) {
  const { app, state, esc } = env;
  document.title = 'Suggest edits · In Good Faith';
  const rows = [{ id: 'common', name: 'General explanations (no tradition)' },
    ...[...state.index.sects].sort((a, b) => a.name.localeCompare(b.name))];
  app.innerHTML = `
    <p class="crumbs"><a href="#/">← Back to reading</a></p>
    <h1>Suggest edits</h1>
    <p class="lede">Pick the tradition whose readers you're writing for. You'll see every explanation written for them and can rewrite any of it. Your changes stay in this browser until you export them.</p>
    <ul class="list">${rows.map((r) => {
      const n = Object.keys(loadDrafts(r.id)).length;
      return `<li><a href="#/edit/${esc(r.id)}"><span class="t">${esc(r.name)}</span>${n ? `<span class="tag warn">${n} unsent edit${n === 1 ? '' : 's'}</span>` : ''}</a></li>`;
    }).join('')}</ul>`;
}

export function viewEditor(env, bundle, focusKey) {
  const { app, sectName, titleFor, subjectName, mdContext, esc } = env;
  const aud = bundle.audience;
  const audName = sectName(aud);
  document.title = `Edit · ${audName} · In Good Faith`;

  const drafts = loadDrafts(aud);
  const items = [
    ...bundle.entries.map((e) => ({ key: e.key, source: e.source, subject: e.subject, text: e.text, level: e.level })),
    ...bundle.missing.map((key) => { const [source, subject] = key.split('.'); return { key, source, subject, text: '', level: 'missing' }; }),
  ];
  const sources = [...new Set(items.map((i) => i.source))].sort((a, b) => sectName(a).localeCompare(sectName(b)));
  const filter = { q: '', src: 'all', only: false };

  app.innerHTML = `
    <p class="crumbs"><a href="#/a/${esc(aud)}">← Back to reading</a> · <a href="#/edit">Change view</a></p>
    <h1>Edit explanations for ${aud === 'common' ? 'general' : esc(audName)} readers</h1>
    <p class="lede">Rewrite anything below. Changes save in this browser as you type. When you're done, use <strong>Export</strong> to get a file you can send to the maintainers.</p>
    <details class="help"><summary>Formatting tips</summary>
      <ul>
        <li>Plain text works. Leave a blank line between paragraphs.</li>
        <li><code>**bold**</code> and <code>*italic*</code>; start a line with <code>- </code> for a bullet list.</li>
        <li><code>[link text](https://example.org)</code> makes a link. <code>[official site](site:catholic)</code> links to a tradition's official site when one is listed.</li>
        <li><code>[[theosis]]</code> or <code>[[theosis|deification]]</code> gives a word a pop-up definition from the <a href="#/dictionary">Dictionary</a>. Unfamiliar words are also explained automatically.</li>
      </ul>
    </details>
    <div class="editor-bar">
      <input id="eq" type="search" placeholder="Filter by word…" autocomplete="off" aria-label="Filter entries">
      <select id="esrc" aria-label="Show one tradition's entries">
        <option value="all">All traditions</option>
        ${sources.map((s) => `<option value="${esc(s)}">${esc(sectName(s))}</option>`).join('')}
      </select>
      <label class="check"><input type="checkbox" id="eonly"> Edited only</label>
      <span id="ecount" class="count"></span>
      <button type="button" id="eexport" class="primary">Export…</button>
    </div>
    <section id="epanel" class="panel" hidden>
      <h2>Export your edits</h2>
      <p class="hint">This is a ready-to-use file. Send it to the maintainers, or save it in <code>lang/</code> to try it on the site.</p>
      <label class="field">Your name (optional; credited in the file)
        <input id="ename" type="text" autocomplete="name"></label>
      <textarea id="ejson" readonly rows="12" aria-label="Exported JSON"></textarea>
      <div class="row">
        <button type="button" id="edl" class="primary">Download file</button>
        <button type="button" id="ecopy">Copy</button>
        <button type="button" id="eclear" class="danger">Discard all edits</button>
        <span id="emsg" class="hint" role="status"></span>
      </div>
    </section>
    <div id="elist"></div>`;

  const $ = (sel) => app.querySelector(sel);
  const nameInput = $('#ename');
  nameInput.value = read(NAME_KEY, '');

  const buildPack = () => {
    const name = nameInput.value.trim();
    const entries = {};
    for (const key of Object.keys(drafts).sort()) entries[key] = drafts[key].replace(/\r\n?/g, '\n').trim();
    return {
      _meta: { author: name ? `unverified: suggested by ${name}` : 'unverified: community suggestion', reviewed_by: [], priority: 10 },
      ...entries,
    };
  };
  const packText = () => `${JSON.stringify(buildPack(), null, 2)}\n`;

  const refreshSummary = () => {
    const n = Object.keys(drafts).length;
    $('#ecount').textContent = `${n} edited`;
    for (const id of ['#eexport', '#edl', '#ecopy']) $(id).disabled = n === 0;
    $('#ejson').value = n ? packText() : '(nothing edited yet)';
  };

  const autosize = (ta) => { ta.style.height = 'auto'; ta.style.height = `${ta.scrollHeight + 2}px`; };

  function card(it) {
    const title = titleFor(it.source, it.subject);
    const art = make('article', { className: 'edit-card', id: `e-${it.key}` });
    const badge = make('span', { className: 'tag warn' });
    art.append(make('header', {}, make('strong', { textContent: title }), make('span', { className: 's', textContent: subjectName(it.subject) }), badge));

    const ta = make('textarea', {
      value: drafts[it.key] ?? it.text,
      spellcheck: true,
      placeholder: it.level === 'missing' ? 'Nothing has been written for this audience yet. Write an explanation here.' : '',
    });
    ta.setAttribute('aria-label', `Explanation of ${title}`);
    const preview = make('div', { className: 'preview entry-body', hidden: true });
    const previewBtn = make('button', { type: 'button', textContent: 'Preview' });
    const resetBtn = make('button', { type: 'button', textContent: 'Reset to current version' });
    art.append(ta, make('div', { className: 'row' }, previewBtn, resetBtn), preview);

    const label = { own: '', inherited: 'inherited', common: 'general', missing: 'no entry yet' }[it.level];
    const refresh = () => {
      const edited = it.key in drafts;
      art.classList.toggle('edited', edited);
      badge.textContent = edited ? 'edited' : label;
      badge.hidden = !badge.textContent;
      resetBtn.hidden = !edited;
    };
    const showPreview = () => preview.replaceChildren(renderMarkdown(ta.value, mdContext(aud)));
    const commit = () => {
      const value = ta.value.trim();
      if (value && value !== it.text.trim()) drafts[it.key] = ta.value; else delete drafts[it.key];
      saveDrafts(aud, drafts);
      refresh();
      refreshSummary();
      autosize(ta);
      if (!preview.hidden) showPreview();
    };
    ta.addEventListener('input', commit);
    resetBtn.addEventListener('click', () => { ta.value = it.text; commit(); });
    previewBtn.addEventListener('click', () => {
      preview.hidden = !preview.hidden;
      previewBtn.textContent = preview.hidden ? 'Preview' : 'Hide preview';
      if (!preview.hidden) showPreview();
    });
    refresh();
    return art;
  }

  function paint() {
    const words = filter.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const list = $('#elist');
    list.replaceChildren();
    const visible = items.filter((it) => {
      if (filter.src !== 'all' && it.source !== filter.src) return false;
      if (filter.only && !(it.key in drafts)) return false;
      if (!words.length) return true;
      const hay = `${titleFor(it.source, it.subject)} ${subjectName(it.subject)} ${sectName(it.source)} ${drafts[it.key] ?? it.text}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    });
    if (!visible.length) { list.append(make('p', { className: 'empty', textContent: 'Nothing matches.' })); return; }

    const groups = new Map();
    for (const it of visible) (groups.get(it.source) ?? groups.set(it.source, []).get(it.source)).push(it);
    for (const src of [...groups.keys()].sort((a, b) => sectName(a).localeCompare(sectName(b)))) {
      const rows = groups.get(src).sort((a, b) => titleFor(a.source, a.subject).localeCompare(titleFor(b.source, b.subject)));
      const body = make('div');
      const group = make('details', { className: 'edit-group' }, make('summary', { textContent: `About ${sectName(src)} beliefs (${rows.length})` }), body);
      // Cards are built when a group is first opened, so a 600-entry audience stays light.
      const fill = () => {
        if (body.childElementCount) return;
        rows.forEach((it) => body.append(card(it)));
        setTimeout(() => body.querySelectorAll('textarea').forEach(autosize), 0);   // after the group is attached
      };
      group.open = Boolean(words.length || filter.only || filter.src !== 'all' || (focusKey && rows.some((it) => it.key === focusKey)));
      if (group.open) fill();
      group.addEventListener('toggle', () => { if (group.open) fill(); });
      list.append(group);
    }
  }

  $('#eq').addEventListener('input', (ev) => { filter.q = ev.target.value; paint(); });
  $('#esrc').addEventListener('change', (ev) => { filter.src = ev.target.value; paint(); });
  $('#eonly').addEventListener('change', (ev) => { filter.only = ev.target.checked; paint(); });
  $('#eexport').addEventListener('click', () => { const p = $('#epanel'); p.hidden = !p.hidden; if (!p.hidden) p.scrollIntoView({ block: 'nearest' }); });
  nameInput.addEventListener('input', () => { write(NAME_KEY, nameInput.value); refreshSummary(); });

  const say = (msg) => { $('#emsg').textContent = msg; };
  $('#edl').addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([packText()], { type: 'application/json' }));
    const a = make('a', { href: url, download: `suggested-edits.${aud}.json` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    say('Downloaded.');
  });
  $('#ecopy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(packText()); say('Copied to the clipboard.'); }
    catch { $('#ejson').select(); say('Press Ctrl+C to copy the selected text.'); }
  });
  $('#eclear').addEventListener('click', () => {
    const n = Object.keys(drafts).length;
    if (!n || !confirm(`Discard all ${n} edit${n === 1 ? '' : 's'} for ${audName}? This can't be undone.`)) return;
    for (const key of Object.keys(drafts)) delete drafts[key];
    saveDrafts(aud, drafts);
    refreshSummary();
    paint();
    say('Edits discarded.');
  });

  refreshSummary();
  paint();
  if (focusKey) {
    setTimeout(() => {
      const el = document.getElementById(`e-${focusKey}`);
      if (el) { el.scrollIntoView({ block: 'center' }); el.querySelector('textarea').focus({ preventScroll: true }); }
    }, 50);
  }
}
