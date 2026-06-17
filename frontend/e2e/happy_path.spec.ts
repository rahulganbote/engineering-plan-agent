import { test, expect } from '@playwright/test'

/**
 * Sprint 5 deliverable. Happy-path E2E:
 *   1. Land on /
 *   2. See the React shell render (header + nav)
 *   3. The auth gate either shows "Sign in" OR (with mock auth) shows the workspace
 *   4. Smoke the API base health
 *
 * This is intentionally LIGHT — it doesn't run a real BRD through OpenAI because
 * that would cost money on every CI run + need real OpenAI credentials. The full
 * pipeline E2E should run as a manual nightly job, not on every PR.
 *
 * For richer flows, write more files in this directory (Playwright auto-discovers
 * *.spec.ts), or extend this test with Playwright's `test.describe` blocks.
 */

test.describe('EM Copilot — happy path', () => {
  test('app shell loads and renders the BRD → Engineering Plan title', async ({ page }) => {
    await page.goto('/');

    // The header text from AgentWorkspace is the canonical landmark
    await expect(
      page.getByText(/BRD\s*[→-]\s*Engineering Plan/i)
    ).toBeVisible({ timeout: 10_000 });
  });

  test('auth gate or signed-in workspace is visible', async ({ page }) => {
    await page.goto('/');

    // Either the sign-in CTA OR a signed-in user chip should be present.
    // Both paths are valid app shells — this test asserts "one of them rendered."
    const signInVisible = await page.getByText(/sign in/i).isVisible().catch(() => false);
    const signedInVisible = await page.getByText(/signed in/i).isVisible().catch(() => false);
    expect(signInVisible || signedInVisible).toBe(true);
  });

  test('upload area shows the 25MB limit', async ({ page }) => {
    await page.goto('/');
    // The dropzone helper text mentions the file size cap
    await expect(page.getByText(/25\s*MB/i)).toBeVisible({ timeout: 5_000 });
  });

  test('backend health endpoint responds (via /health proxy)', async ({ request }) => {
    // The Vite dev proxy forwards /health → FastAPI :8000
    const resp = await request.get('/health');
    expect(resp.ok()).toBe(true);
  });
});
