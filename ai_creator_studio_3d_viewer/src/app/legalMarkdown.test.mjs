import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parseInline, parseLegalMarkdown, legalDocumentBlocks, legalDocumentText } from './legalMarkdown.mjs';

const DOCS = ['terms', 'privacy', 'content_policy'];
const read = (name) => readFileSync(fileURLToPath(new URL(`../legal/${name}.md`, import.meta.url)), 'utf8');
const unescapeMd = (text) => text.replace(/\\([\\`*_{}[\]()#+\-.!|>])/g, '$1');

test('inline: bold, code and backslash escapes; bracket blanks pass through unchanged', () => {
  assert.deepEqual(parseInline('a **b** `[7]` c\\_d \\[결정 필요\\]'), [
    { t: 'text', v: 'a ' }, { t: 'bold', v: 'b' }, { t: 'text', v: ' ' }, { t: 'code', v: '[7]' }, { t: 'text', v: ' c_d [결정 필요]' }]);
});

test('blocks: heading, table (separator dropped), lists, quote, paragraph join', () => {
  const blocks = parseLegalMarkdown('# T\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n- x\n- y\n\n1. p\n2. q\n\n> note\n\nline1\nline2\n');
  assert.deepEqual(blocks.map((b) => b.type), ['heading', 'table', 'list', 'list', 'quote', 'paragraph']);
  assert.equal(blocks[1].header.length, 2);
  assert.equal(blocks[1].rows.length, 1);
  assert.equal(blocks[2].ordered, false);
  assert.equal(blocks[3].ordered, true);
  assert.equal(blocks[3].items.length, 2);
  assert.equal(blocks[5].inline[0].v, 'line1 line2');
});

test('all three documents start with a title and drop the developer note and the author byline', () => {
  for (const name of DOCS) {
    const blocks = legalDocumentBlocks(read(name));
    assert.equal(blocks[0].type, 'heading', name);
    assert.equal(blocks[0].level, 1, name);
    assert.ok(blocks.length > 5, name);
    const text = legalDocumentText(read(name));
    assert.ok(!text.includes('@Justin') && !text.includes('설계 창의 법률 문서 초안'), name);
  }
});

test('no text is lost: every bracketed blank and every heading of the source is on screen, unfilled', () => {
  for (const name of DOCS) {
    const source = read(name);
    const shown = legalDocumentText(source);
    const blanks = unescapeMd(source).match(/\[[^\]\n]*\]/g) || [];
    assert.ok(blanks.length > 0, name);
    // The first quote block (developer note) is intentionally not shown, so skip blanks that only occur in it.
    const firstQuote = source.split('\n').filter((l) => l.startsWith('>'))[0] || '';
    for (const blank of blanks.filter((b) => !firstQuote.includes(b) || unescapeMd(source.replace(firstQuote, '')).includes(b))) {
      assert.ok(shown.includes(blank), `${name}: ${blank} missing`);
    }
    for (const line of source.split('\n').filter((l) => /^#{1,6}\s/.test(l))) {
      assert.ok(shown.includes(unescapeMd(line.replace(/^#+\s+/, '').trim())), `${name}: heading ${line}`);
    }
    assert.ok(!/\*\*/.test(shown), `${name}: raw bold markers leaked`);
  }
});

test('the blanks are never filled in: no email address or phone number appears in any document', () => {
  for (const name of DOCS) {
    const shown = legalDocumentText(read(name));
    assert.ok(!/[\w.+-]+@[\w-]+\.[\w.]+/.test(shown), `${name}: email-like text`);
    assert.ok(!/\b0\d{1,2}-\d{3,4}-\d{4}\b/.test(shown), `${name}: phone-like text`);
  }
});
