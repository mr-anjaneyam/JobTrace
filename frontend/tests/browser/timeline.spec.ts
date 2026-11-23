import { test, expect, type Page } from '@playwright/test';
import type { ApiJob } from '../../src/lib/api';

const NOW = Date.UTC(2026, 10, 19, 12) / 1000;
const DAY = 86400;

async function workspace(page: Page) {
  await page.clock.install({ time: new Date((NOW - 60) * 1000) });
  await page.clock.pauseAt(new Date(NOW * 1000));
  const state = { fail: false, requests: 0, closed: new Set<string>() };
  const jobs: ApiJob[] = [
    { id: 'steady', company: 'Acme', title: 'Engineer', source: 'greenhouse', location: 'Remote',
      url: 'https://example.com/job', domain: '', score: 8, reason: '', first_seen: NOW - 20 * DAY },
    { id: 'expires', company: 'Acme', title: 'Expiring engineer', source: 'greenhouse', location: 'Remote',
      url: 'https://example.com/job', domain: '', score: 7, reason: '', first_seen: NOW - 2 * DAY, deadline_at: NOW + 5 },
    { id: 'past', company: 'Acme', title: 'Closed engineer', source: 'greenhouse', location: 'Remote',
      url: 'https://example.com/job', domain: '', score: 6, reason: '', first_seen: NOW - 10 * DAY, closed_at: NOW - DAY },
    { id: 'survivor', company: 'Acme', title: 'Continuing engineer', source: 'greenhouse', location: 'Remote',
      url: 'https://example.com/job', domain: '', score: 9, reason: '', first_seen: NOW - 20 * DAY },
  ];
  await page.route('https://**/*', (route) => route.abort());
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/onboarding/status') {
      return route.fulfill({ json: { completed: true, name: '', scan: { state: 'idle' } } });
    }
    if (path.endsWith('/verify')) return route.fulfill({ json: { ok: true, active: true, verified: true } });
    if (path === '/api/state') {
      state.requests++;
      if (state.fail) return route.fulfill({ status: 503, json: { detail: 'Busy' } });
      const now = await page.evaluate(() => Date.now() / 1000);
      const history = jobs.map((j) => {
        const closed = state.closed.has(j.id) ? NOW : j.closed_at ?? (j.deadline_at && j.deadline_at <= now ? j.deadline_at : null);
        return { ...j, closed_at: closed, expires_at: closed ?? j.deadline_at,
          periods: [{ opened_at: j.first_seen, closed_at: closed }] };
      });
      return route.fulfill({ json: {
        jobs: history.filter((j) => j.closed_at == null), scanning: false, scoring: false, companies: [],
        stats: { checked: 2, total: 2, closed: 1, would_apply: 2, avg: 7, threshold: 6 },
        timeline: { start: now - 30 * DAY, end: now, jobs: history, truncated: false },
      } });
    }
    return route.fulfill({ status: 404, json: { detail: 'Unexpected test request' } });
  });
  await page.goto('/');
  await expect(page.locator('.gmap-pin[data-state="open"]')).toHaveCount(3);
  return state;
}

async function seek(page: Page, time: number) {
  await page.getByRole('slider', { name: 'Opening history time' }).evaluate((node, value) => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
    set.call(node, String(value));
    node.dispatchEvent(new Event('input', { bubbles: true }));
    node.dispatchEvent(new Event('change', { bubbles: true }));
  }, time);
}

test('known expiry removes pins between polls', async ({ page }) => {
  const state = await workspace(page);
  const requests = state.requests;
  await page.clock.fastForward(6500);
  await expect(page.locator('[data-job-id="expires"][data-state="open"]')).toHaveCount(0);
  expect(state.requests).toBe(requests);
  await expect(page.locator('[data-job-id="steady"][data-state="open"]')).toHaveCount(1);
});

test('polling removes closed selections without changing surviving coordinates or zoom', async ({ page }) => {
  const state = await workspace(page);
  await page.getByRole('button', { name: 'Zoom in (+)', exact: true }).click();
  await page.clock.runFor(500);
  await page.locator('[data-job-id="steady"]').focus();
  await page.locator('[data-job-id="steady"]').press('Enter');
  await expect(page.locator('.gmap-place-card')).toBeVisible();
  await page.clock.runFor(700);
  const transform = await page.locator('.gmap-transform-content').getAttribute('style');
  const position = await page.locator('[data-job-id="survivor"]').getAttribute('style');
  state.closed.add('steady');
  await page.clock.fastForward(15000);
  await expect(page.locator('[data-job-id="steady"][data-state="open"]')).toHaveCount(0);
  await expect(page.locator('.gmap-place-card[data-state="open"]')).toHaveCount(0);
  expect(await page.locator('.gmap-transform-content').getAttribute('style')).toBe(transform);
  expect(await page.locator('[data-job-id="survivor"]').getAttribute('style')).toBe(position);
});

test('historical scrubbing restores closed jobs and paused playback does not drift', async ({ page }) => {
  await workspace(page);
  await seek(page, NOW - 3 * DAY);
  await expect(page.locator('[data-job-id="past"][data-state="open"]')).toHaveCount(1);
  await expect(page.locator('[data-job-id="expires"][data-state="open"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Play timeline', exact: true }).click();
  await page.clock.runFor(300);
  await page.getByRole('button', { name: 'Pause timeline', exact: true }).click();
  const slider = page.getByRole('slider', { name: 'Opening history time' });
  const paused = await slider.inputValue();
  await page.clock.fastForward(1500);
  expect(await slider.inputValue()).toBe(paused);
  await slider.press('End');
  await expect(page.getByRole('button', { name: 'Live', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('[data-job-id="past"][data-state="open"]')).toHaveCount(0);
});

test('failed polls keep cached jobs and show a recoverable error', async ({ page }) => {
  const state = await workspace(page);
  state.fail = true;
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByRole('alert')).toContainText('Live updates paused');
  await expect(page.locator('[data-job-id="steady"][data-state="open"]')).toHaveCount(1);
  state.fail = false;
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('timeline and zoom controls remain reachable across viewport sizes', async ({ page }) => {
  await workspace(page);
  for (const [width, height] of [[1440, 900], [1024, 768], [768, 1024], [390, 844], [320, 640], [844, 390]]) {
    await page.setViewportSize({ width, height });
    await page.clock.runFor(500);
    const hidden = await page.locator('.job-timeline button,.job-timeline input,.gmap-ctrl-btn').evaluateAll((nodes) =>
      nodes.filter((node) => {
        const r = node.getBoundingClientRect();
        const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return r.left < 0 || r.right > innerWidth || r.top < 0 || r.bottom > innerHeight || !node.contains(hit);
      }).map((node) => node.getAttribute('aria-label') || node.textContent),
    );
    expect(hidden, `${width}x${height}`).toEqual([]);
    const overlap = await page.evaluate(() => {
      const bar = document.querySelector('.job-timeline')!.getBoundingClientRect();
      const others = ['.gmap-ctrl-cluster', '.gmap-explore-trigger-wrap', '.gmap-status-cluster'];
      return {
        slim: bar.height <= 60 && bar.bottom === innerHeight,
        covered: others.filter((selector) => {
          const r = document.querySelector(selector)!.getBoundingClientRect();
          return r.bottom > bar.top && r.top < bar.bottom;
        }),
      };
    });
    expect(overlap, `${width}x${height}`).toEqual({ slim: true, covered: [] });
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.getByRole('button', { name: 'Play timeline', exact: true })).toBeDisabled();
  await page.getByRole('slider', { name: 'Opening history time' }).press('ArrowLeft');
  await expect(page.getByRole('button', { name: 'Live', exact: true })).toHaveAttribute('aria-pressed', 'false');
});

test('dots keep the original look: no extra graph chrome is added', async ({ page }) => {
  await workspace(page);
  await expect(page.locator('.pin-body .company-mark')).toHaveCount(3);
  await expect(page.locator('.pin-score-badge')).toHaveCount(3);
  await expect(page.locator('.gmap-corner-watermark')).toHaveCount(4);
  await expect(page.locator('.graph-key, .graph-density-cell, .opportunity-graph')).toHaveCount(0);
});
