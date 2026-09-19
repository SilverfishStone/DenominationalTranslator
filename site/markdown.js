// A small, safe Markdown renderer for entry text. It builds DOM nodes with textContent and
// never uses innerHTML, so contributor text cannot inject markup.
//
//   Blocks:  paragraphs · "- " bullets · "1. " numbered lists · "> " quotes
//   Inline:  **bold** · *italic* · `code` · [text](https://...) · [text](site:<sect_id>)
//            [[term]] and [[term|shown text]]   (glossary pop-ups)
//
// Optionally also links glossary words automatically (first occurrence per entry).

const INLINE = /\[\[([A-Za-z0-9_]+)(?:\|([^\]]+))?\]\]|\[([^\]]+)\]\(([^)\s]+)\)|\*\*(.+?)\*\*|\*(?!\s)([^*\n]+?)\*|`([^`\n]+)`/g;
const EXTERNAL = /^(https?:\/\/|mailto:)/i;

const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// glossary: { id: { id, term, aliases?, auto? } }  ->  { regex, lookup } for auto-linking.
export function buildGlossaryIndex(glossary) {
  const lookup = new Map();
  for (const t of Object.values(glossary)) {
    if (t.auto === false) continue;
    for (const name of [t.term, ...(t.aliases ?? [])]) lookup.set(name.toLowerCase(), t.id);
  }
  if (!lookup.size) return { regex: null, lookup };
  const alternation = [...lookup.keys()].sort((a, b) => b.length - a.length).map(escapeRegExp).join('|');
  return { regex: new RegExp(`(?<![\\p{L}\\p{N}_])(?:${alternation})(?![\\p{L}\\p{N}_])`, 'giu'), lookup };
}

// ctx: { glossary, sects: Map, autoRegex, autoLookup, skip: Set of term ids not to auto-link }
export function renderMarkdown(source, ctx = {}) {
  const text = String(source ?? '').replace(/\r\n?/g, '\n');
  // Terms marked by hand are never also auto-linked earlier in the same entry.
  const seen = new Set([...text.matchAll(/\[\[([A-Za-z0-9_]+)/g)].map((m) => m[1]));

  const termButton = (id, shown) => {
    const term = ctx.glossary?.[id];
    if (!term) return document.createTextNode(shown ?? id);
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'term';
    b.dataset.term = id;
    b.textContent = shown ?? term.term;
    return b;
  };

  const plain = (chunk, parent) => {
    if (!chunk) return;
    const re = ctx.autoRegex;
    if (!re) { parent.append(chunk); return; }
    let last = 0;
    for (const m of chunk.matchAll(re)) {
      const id = ctx.autoLookup.get(m[0].toLowerCase());
      if (!id || seen.has(id) || ctx.skip?.has(id)) continue;
      seen.add(id);
      parent.append(chunk.slice(last, m.index), termButton(id, m[0]));
      last = m.index + m[0].length;
    }
    parent.append(chunk.slice(last));
  };

  const link = (label, url, parent) => {
    let href = null;
    let external = true;
    if (url.startsWith('site:')) href = ctx.sects?.get(url.slice(5))?.site ?? null;
    else if (EXTERNAL.test(url)) href = url;
    else if (url.startsWith('#/')) { href = url; external = false; }
    if (!href) { parent.append(label); return; }        // unsafe or unknown target: show the words only
    const a = document.createElement('a');
    a.href = href;
    a.textContent = label;
    if (external) { a.target = '_blank'; a.rel = 'noopener noreferrer'; a.className = 'ext'; }
    parent.append(a);
  };

  const wrap = (tag, inner, parent) => {
    const el = document.createElement(tag);
    inline(inner, el);
    parent.append(el);
  };

  function inline(chunk, parent) {
    let last = 0;
    for (const m of chunk.matchAll(INLINE)) {
      plain(chunk.slice(last, m.index), parent);
      last = m.index + m[0].length;
      const [, termId, shown, label, url, bold, italic, code] = m;
      if (termId) parent.append(termButton(termId, shown));
      else if (label !== undefined) link(label, url, parent);
      else if (bold !== undefined) wrap('strong', bold, parent);
      else if (italic !== undefined) wrap('em', italic, parent);
      else { const c = document.createElement('code'); c.textContent = code; parent.append(c); }
    }
    plain(chunk.slice(last), parent);
  }

  const isBullet = (l) => /^\s*[-*]\s+\S/.test(l);
  const isNumber = (l) => /^\s*\d+[.)]\s+\S/.test(l);
  const isQuote = (l) => /^\s*>/.test(l);
  const startsBlock = (l) => isBullet(l) || isNumber(l) || isQuote(l);

  const frag = document.createDocumentFragment();
  const lines = text.split('\n');
  const lines_ = (buf, parent) => buf.forEach((line, n) => { if (n) parent.append(document.createElement('br')); inline(line.trim(), parent); });

  let i = 0;
  while (i < lines.length) {
    if (!lines[i].trim()) { i++; continue; }
    if (isBullet(lines[i]) || isNumber(lines[i])) {
      const ordered = isNumber(lines[i]);
      const test = ordered ? isNumber : isBullet;
      const list = document.createElement(ordered ? 'ol' : 'ul');
      while (i < lines.length && test(lines[i])) {
        const li = document.createElement('li');
        inline(lines[i].replace(/^\s*(?:[-*]|\d+[.)])\s+/, ''), li);
        list.append(li);
        i++;
      }
      frag.append(list);
    } else if (isQuote(lines[i])) {
      const buf = [];
      while (i < lines.length && isQuote(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ''));
      const quote = document.createElement('blockquote');
      const p = document.createElement('p');
      lines_(buf, p);
      quote.append(p);
      frag.append(quote);
    } else {
      const buf = [lines[i++]];
      while (i < lines.length && lines[i].trim() && !startsBlock(lines[i])) buf.push(lines[i++]);
      const p = document.createElement('p');
      lines_(buf, p);
      frag.append(p);
    }
  }
  return frag;
}
