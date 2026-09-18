// DenomBridge front end: static, no dependencies, hash routing (works on GitHub Pages).
//   #/                    pick your tradition
//   #/a/<audience>        browse/search everything explained for that audience
//   #/a/<audience>/<key>  one entry, e.g. #/a/ortho/evangelical.new_birth

const app = document.getElementById('app');
const state = { index: null, sects: new Map(), bundles: new Map(), audience: null, source: 'all', query: '' };

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const store = {
  get() { try { return localStorage.getItem('denombridge.audience'); } catch { return null; } },
  set(v) { try { localStorage.setItem('denombridge.audience', v); } catch { /* storage unavailable */ } },
};

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

async function loadIndex() {
  if (state.index) return;
  state.index = await getJson('data/index.json');
  state.sects = new Map(state.index.sects.map((s) => [s.id, s]));
}

async function loadBundle(id) {
  if (!state.bundles.has(id)) state.bundles.set(id, await getJson(`data/${id}.json`));
  return state.bundles.get(id);
}

const isAudience = (id) => id === 'common' || state.sects.has(id);
const sectName = (id) => (id === 'common' ? 'General' : state.sects.get(id)?.name ?? id);
const subjectOf = (e) => state.index.subjects[e.subject];
// A sect's own terms, or its nearest ancestor's when it has none (e.g. baptist -> evangelical).
function termsFor(subject, sectId) {
  for (let id = sectId; id; id = state.sects.get(id)?.parent) {
    const terms = subject?.terms?.[id];
    if (terms?.length) return terms;
  }
  return [];
}
// The first term is how that sect names the idea (e.g. "born again").
const entryTitle = (e) => termsFor(subjectOf(e), e.source)[0] ?? subjectOf(e)?.name ?? e.subject;

function tags(e) {
  const out = [];
  if (e.level === 'inherited') out.push(`<span class="tag">via ${esc(sectName(e.from))}</span>`);
  if (e.level === 'common') out.push('<span class="tag">general</span>');
  if (/^unverified/i.test(e.author ?? '')) out.push('<span class="tag warn">unverified</span>');
  if (e.placeholder) out.push('<span class="tag warn">placeholder</span>');
  return out.join('');
}

// --- views ---------------------------------------------------------------------

function viewHome() {
  document.title = 'DenomBridge';
  const { sects, audiences } = state.index;
  const branch = (parent) => {
    const kids = sects.filter((s) => (s.parent ?? null) === parent);
    return kids.length ? `<ul class="tree">${kids.map(card).join('')}</ul>` : '';
  };
  const card = (s) => `<li><a class="card" href="#/a/${esc(s.id)}">
      <strong>${esc(s.name)}</strong>${s.blurb ? `<span>${esc(s.blurb)}</span>` : ''}
      <small>${audiences[s.id].count} explanations</small></a>${branch(s.id)}</li>`;

  const last = store.get();
  const resume = last && isAudience(last)
    ? `<p class="resume">Last time you chose <a href="#/a/${esc(last)}">${esc(sectName(last))}</a>.</p>` : '';

  app.innerHTML = `
    <h1>Which tradition are you coming from?</h1>
    <p class="lede">Pick your own tradition. You'll then see other traditions' beliefs explained in terms you'll recognise.</p>
    ${resume}
    ${branch(null)}
    <p class="general"><a href="#/a/common">Not sure, or none of these? Read the general explanations →</a></p>`;
}

function viewAudience(bundle) {
  const aud = bundle.audience;
  if (state.audience !== aud) Object.assign(state, { audience: aud, source: 'all', query: '' });
  store.set(aud);
  document.title = `${sectName(aud)} · DenomBridge`;

  const sources = [...new Set(bundle.entries.map((e) => e.source))].sort((a, b) => sectName(a).localeCompare(sectName(b)));
  const heading = aud === 'common' ? 'General explanations' : `Explained for ${esc(sectName(aud))} readers`;
  app.innerHTML = `
    <p class="crumbs"><a href="#/">← Change tradition</a></p>
    <h1>${heading}</h1>
    <p class="lede">Choose a belief from another tradition, or search for a term you've heard.</p>
    <input id="q" type="search" placeholder="Search a term, e.g. “born again”" value="${esc(state.query)}" autocomplete="off">
    <div class="chips" id="chips"></div>
    <div id="results"></div>
    ${bundle.missing.length ? `<p class="hint">${bundle.missing.length} topic(s) have no explanation for you yet.</p>` : ''}`;

  const score = (e, tokens) => {
    const s = subjectOf(e);
    const terms = [entryTitle(e), s?.name ?? '', ...Object.values(s?.terms ?? {}).flat()].join(' ').toLowerCase();
    const body = `${sectName(e.source)} ${e.text}`.toLowerCase();
    let total = 0;
    for (const t of tokens) {
      if (terms.includes(t)) total += 3;
      else if (body.includes(t)) total += 1;
      else return 0;
    }
    return total;
  };

  const paint = () => {
    const tokens = state.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    app.querySelector('#chips').innerHTML = ['all', ...sources].map((id) =>
      `<button type="button" data-source="${esc(id)}" aria-pressed="${state.source === id}">${id === 'all' ? 'All' : esc(sectName(id))}</button>`).join('');

    const rows = bundle.entries
      .filter((e) => state.source === 'all' || e.source === state.source)
      .map((e) => ({ e, score: score(e, tokens) }))
      .filter((r) => !tokens.length || r.score > 0)
      .sort((a, b) => b.score - a.score || entryTitle(a.e).localeCompare(entryTitle(b.e)));

    const groups = {};
    for (const r of rows) (groups[r.e.source] ||= []).push(r.e);
    const order = Object.keys(groups).sort((a, b) => (a === aud) - (b === aud) || sectName(a).localeCompare(sectName(b)));

    app.querySelector('#results').innerHTML = order.length ? order.map((src) => `
      <section>
        <h2>${src === aud ? 'Your own tradition' : `About ${esc(sectName(src))} beliefs`}</h2>
        <ul class="list">${groups[src].map((e) => `
          <li><a href="#/a/${esc(aud)}/${esc(e.key)}">
            <span class="t">${esc(entryTitle(e))}</span>
            <span class="s">${esc(subjectOf(e)?.name ?? e.subject)}</span>${tags(e)}</a></li>`).join('')}
        </ul>
      </section>`).join('') : '<p class="empty">Nothing matches. Try a different word.</p>';
  };

  const q = app.querySelector('#q');
  q.addEventListener('input', () => { state.query = q.value; paint(); });
  app.querySelector('#chips').addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-source]');
    if (btn) { state.source = btn.dataset.source; paint(); }
  });
  paint();
}

function viewEntry(bundle, key) {
  const e = bundle.entries.find((x) => x.key === key);
  if (!e) return viewNotFound();
  const aud = bundle.audience;
  const name = sectName(aud);
  document.title = `${entryTitle(e)} · ${name} · DenomBridge`;

  const notice = {
    own: `Written for ${esc(name)} readers.`,
    inherited: `Nothing has been written specifically for ${esc(name)} readers yet, so this is the version written for ${esc(sectName(e.from))} readers.`,
    common: aud === 'common'
      ? 'A general explanation, not tailored to any tradition.'
      : `Nothing has been written specifically for ${esc(name)} readers yet, so this is a general explanation.`,
  }[e.level];

  const paragraphs = e.text.split(/\n{2,}/).map((p) => `<p>${esc(p).replace(/\n/g, '<br>')}</p>`).join('');
  const related = bundle.entries.filter((x) => x.subject === e.subject && x.key !== e.key);
  const reviewed = e.reviewed_by.length ? esc(e.reviewed_by.map(sectName).join(', ')) : 'Not yet reviewed by an adherent';

  app.innerHTML = `
    <p class="crumbs"><a href="#/a/${esc(aud)}">← ${esc(aud === 'common' ? 'General explanations' : name)}</a></p>
    <p class="kicker">${esc(sectName(e.source))} · ${esc(subjectOf(e)?.name ?? e.subject)}</p>
    <h1>${esc(entryTitle(e))} ${tags(e)}</h1>
    <p class="notice ${e.level}">${notice}</p>
    <article>${paragraphs}</article>
    <dl class="meta">
      ${e.author ? `<dt>Author</dt><dd>${esc(e.author)}</dd>` : ''}
      <dt>Reviewed by</dt><dd>${reviewed}</dd>
    </dl>
    ${related.length ? `<section><h2>Same topic, other traditions</h2><ul class="list">${related.map((r) => `
      <li><a href="#/a/${esc(aud)}/${esc(r.key)}"><span class="t">${esc(entryTitle(r))}</span><span class="s">${esc(sectName(r.source))}</span>${tags(r)}</a></li>`).join('')}</ul></section>` : ''}`;
}

function viewNotFound() {
  document.title = 'Not found · DenomBridge';
  app.innerHTML = '<h1>Not found</h1><p><a href="#/">Back to the start</a></p>';
}

// --- router --------------------------------------------------------------------

async function route() {
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent);
  try {
    await loadIndex();
    if (parts[0] === 'a' && parts[1]) {
      if (!isAudience(parts[1])) return viewNotFound();
      const bundle = await loadBundle(parts[1]);
      if (parts[2]) viewEntry(bundle, parts[2]); else viewAudience(bundle);
    } else {
      viewHome();
    }
  } catch (err) {
    app.innerHTML = `<p class="error">Couldn't load data (${esc(err.message)}). Serve this folder over HTTP rather than opening the file directly: <code>python scripts/serve.py</code></p>`;
  }
}

let lastPath = null;
window.addEventListener('hashchange', () => { route().then(() => { if (location.hash !== lastPath) window.scrollTo(0, 0); lastPath = location.hash; }); });
route();
