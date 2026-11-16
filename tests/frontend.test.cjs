const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');

function app(fetch = () => new Promise(() => {})) {
  const elements = new Map();
  const document = {
    activeElement: null,
    querySelectorAll: () => [],
    createElementNS: (_, tag) => element(tag),
    createElement: (tag) => element(tag),
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element(id));
      return elements.get(id);
    },
  };

  function element(tag) {
    return {
      tag,
      attributes: {},
      children: [],
      handlers: {},
      value: '',
      setAttribute(name, value) { this.attributes[name] = String(value); },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      addEventListener(event, fn) { this.handlers[event] = fn; },
      focus() { document.activeElement = this; },
    };
  }

  const script = vm.runInNewContext(
    source + '\n;({ state, renderChart, renderLayout, loadRecords, selectAsset })',
    { document, URLSearchParams, fetch: (url, opts) => url === '/api/summary' || url === '/api/assets'
        ? new Promise(() => {})
        : fetch(url, opts) },
  );
  return { ...script, element: (id) => document.getElementById(id), document };
}

test('shows isolated observations without joining across missing readings', () => {
  const view = app();
  const items = [0, null, 1, 2, null, 3].map(value => ({ value, timestamp: '2026-11-12T12:30:00+08:00' }));
  view.renderChart({ asset_id: 'D-01', items });
  const [chart] = view.element('chart').children;
  const dots = chart.children.filter(child => child.tag === 'circle');
  assert.deepEqual(dots.map(dot => dot.attributes.cx), ['40', '398']);
  const line = chart.children.find(child => child.tag === 'path');
  assert.equal((line.attributes.d.match(/L/g) || []).length, 1);
});

test('keyboard selection retains focus on the replacement asset', () => {
  const view = app();
  view.state.assets = [{ id: 'D-01', name: 'Module 1', x: 1, y: 2, quality: 'valid' }];
  view.renderLayout();
  const [first] = view.element('layout').children;
  const oldButton = first.children.find(child => child.tag === 'g');
  oldButton.focus();
  oldButton.handlers.keydown({ key: 'Enter', preventDefault() {} });
  const [newLayout] = view.element('layout').children;
  const newButton = newLayout.children.find(child => child.tag === 'g');
  assert.notEqual(oldButton, newButton);
  assert.equal(view.document.activeElement, newButton);
});

test('clears the previous rows when a new filter fails to load', async () => {
  let rejectRequest;
  const view = app(() => new Promise((_, reject) => { rejectRequest = reject; }));
  const rows = view.element('rows');
  rows.replaceChildren({ tag: 'tr' });
  view.element('record-count').textContent = '5 条';
  const pending = view.loadRecords();
  assert.equal(rows.children.length, 0);
  assert.equal(view.element('record-count').textContent, '读取中');
  rejectRequest(new Error('Network failed'));
  await pending;
  assert.equal(rows.children.length, 0);
  assert.equal(view.element('record-count').textContent, '读取失败');
});

test('clears a resolved record error while keeping an unrelated detail error', async () => {
  let recordFailure = true;
  const view = app((url) => {
    if (url.includes('/api/records?')) {
      return recordFailure
        ? Promise.reject(new Error('Record load failed'))
        : Promise.resolve({ ok: true, json: async () => ({ total: 0, items: [] }) });
    }
    return Promise.reject(new Error('Detail load failed'));
  });
  await view.selectAsset('D-01');
  await view.loadRecords();
  const banner = view.element('error');
  assert.match(banner.textContent, /Detail load failed/);
  assert.match(banner.textContent, /Record load failed/);
  recordFailure = false;
  await view.loadRecords();
  assert.equal(banner.textContent, 'Detail load failed');
  assert.equal(banner.hidden, false);
});

test('hides the record error banner after a successful retry', async () => {
  let fail = true;
  const view = app(() => fail
    ? Promise.reject(new Error('Record load failed'))
    : Promise.resolve({ ok: true, json: async () => ({ total: 0, items: [] }) }));
  await view.loadRecords();
  assert.equal(view.element('error').hidden, false);
  fail = false;
  await view.loadRecords();
  assert.equal(view.element('error').hidden, true);
  assert.equal(view.element('error').textContent, '');
});

test('a pending selection clears the previous asset note and status styling', () => {
  const view = app();
  view.element('value-note').textContent = 'Previous status';
  view.element('quality-badge').className = 'quality-badge stale';
  view.selectAsset('P-03');
  assert.equal(view.element('value-note').textContent, '');
  assert.equal(view.element('quality-badge').className, 'quality-badge');
});

test('plots irregular readings at their elapsed-time positions', () => {
  const view = app();
  const items = ['00:00', '00:05', '00:20'].map((time, value) => ({
    value, timestamp: `2026-11-12T${time}:00+08:00`,
  }));
  view.renderChart({ asset_id: 'D-01', items });
  const [chart] = view.element('chart').children;
  const line = chart.children.find(child => child.tag === 'path');
  assert.match(line.attributes.d, /^M40\.0,.* L129\.5,.* L398\.0,/);
});
