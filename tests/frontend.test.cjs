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
    source + '\n;({ state, renderChart, renderLayout, loadRecords })',
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
