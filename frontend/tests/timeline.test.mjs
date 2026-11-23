import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/timeline.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { isJobActiveAt } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('opening is visible only before its exact expiry boundary', () => {
  const job = { first_seen: 100, deadline_at: 200 };
  assert.equal(isJobActiveAt(job, 99), false);
  assert.equal(isJobActiveAt(job, 100), true);
  assert.equal(isJobActiveAt(job, 199), true);
  assert.equal(isJobActiveAt(job, 200), false);
  assert.equal(isJobActiveAt(job, 250), false);
});

test('reopened jobs are absent in the closed gap, in both scrub directions', () => {
  const job = { expires_at: 500, periods: [
    { opened_at: 100, closed_at: 200 }, { opened_at: 400, closed_at: null },
  ] };
  for (const time of [450, 300, 150, 300, 450]) {
    assert.equal(isJobActiveAt(job, time), time !== 300);
  }
  assert.equal(isJobActiveAt(job, 500), false);
});

test('aggregator expiry and discarded jobs vanish without another poll', () => {
  assert.equal(isJobActiveAt({ first_seen: 1, expires_at: 100 }, 100), false);
  assert.equal(isJobActiveAt({ first_seen: 1, closed_at: 100 }, 100), false);
  assert.equal(isJobActiveAt({ first_seen: 1 }, 100), true);
});
