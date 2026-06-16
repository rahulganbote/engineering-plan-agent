import { test, expect } from '@playwright/test'

// Sprint 5 deliverable. Stub kept here so the e2e/ directory + Playwright
// config aren't missing when Sprint 5 starts. The real test will:
//   1. Sign in via Google (use a fixture token in CI)
//   2. Upload a 114KB sample BRD
//   3. Wait for the Critic GREEN badge
//   4. Click "Approve & Export"
//   5. Assert status banner shows "exported"

test.skip('happy path: upload → run → approve → exported', async ({ page }) => {
  await page.goto('/')
  // TODO Sprint 5: implement
  expect(true).toBe(true)
})
