import { test, expect, type Page, type Route } from '@playwright/test'

/**
 * E2E tests for role-based UI gating (proxy-header auth).
 *
 * The backend is fully stubbed with page.route(), so these tests don't need
 * a running server or any registered projects.
 *
 * Run tests:
 *   cd ui && npm run test:e2e -- viewer-role.spec.ts
 */

const PROJECT = 'app-a'

const pendingFeature = {
  id: 1,
  priority: 1,
  category: 'core',
  name: 'Login page',
  description: 'Users can log in',
  steps: ['Open /login', 'Submit the form'],
  passes: false,
  in_progress: false,
  dependencies: [],
  blocked: false,
  blocking_dependencies: [],
  needs_human_input: false,
}

function json(route: Route, body: unknown) {
  return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

async function stubBackend(page: Page, role: 'viewer' | 'developer') {
  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path === '/api/auth/me') {
      return json(route, {
        enabled: true,
        user: 'alice',
        groups: [],
        is_admin: false,
        default_role: 'none',
        projects: { [PROJECT]: role },
      })
    }
    if (path === '/api/projects') {
      return json(route, [{
        name: PROJECT,
        path: '/tmp/app-a',
        has_spec: true,
        stats: { passing: 0, in_progress: 0, total: 1, percentage: 0 },
        default_concurrency: 1,
        auto_improve_enabled: false,
        auto_improve_interval_minutes: 60,
      }])
    }
    if (path === `/api/projects/${PROJECT}/features`) {
      return json(route, { pending: [pendingFeature], in_progress: [], done: [], needs_human_input: [] })
    }
    if (path === `/api/projects/${PROJECT}/features/graph`) {
      return json(route, { nodes: [], edges: [] })
    }
    if (path === `/api/projects/${PROJECT}/agent/status`) {
      return json(route, { status: 'stopped', pid: null, started_at: null, yolo_mode: false })
    }
    if (path === '/api/setup/status') {
      return json(route, { claude_cli: true, credentials: true, node: true, npm: true })
    }
    if (path === '/api/health') {
      return json(route, { status: 'healthy' })
    }
    // Anything else: empty object keeps the UI quiet
    return json(route, {})
  })

  await page.addInitScript((project) => {
    localStorage.setItem('autoforge-selected-project', project)
    localStorage.setItem('autoforge-active-view', 'kanban')
  }, PROJECT)
}

test.describe('Role-based UI gating', () => {
  test.setTimeout(30000)

  test('viewer does not see feature write controls', async ({ page }) => {
    await stubBackend(page, 'viewer')
    await page.goto('/')

    const card = page.getByText('Login page').first()
    await expect(card).toBeVisible({ timeout: 10000 })

    // Kanban + (add feature) and ✨ (expand) buttons are not rendered
    await expect(page.locator('button[title="Add new feature (N)"]')).toHaveCount(0)
    await expect(page.locator('button[title="Expand project with AI (E)"]')).toHaveCount(0)

    // N shortcut does not open the add-feature form
    await page.locator('body').click({ position: { x: 1, y: 1 } })
    await page.keyboard.press('n')
    await expect(page.getByRole('dialog')).toHaveCount(0)

    // Feature modal opens read-only: no Edit / Skip / Delete
    await card.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText('Test Steps')).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Edit' })).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: 'Skip' })).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: 'Delete feature' })).toHaveCount(0)
  })

  test('developer sees feature write controls', async ({ page }) => {
    await stubBackend(page, 'developer')
    await page.goto('/')

    const card = page.getByText('Login page').first()
    await expect(card).toBeVisible({ timeout: 10000 })

    await expect(page.locator('button[title="Add new feature (N)"]')).toBeVisible()
    await expect(page.locator('button[title="Expand project with AI (E)"]')).toBeVisible()

    await card.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByRole('button', { name: 'Edit' })).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Skip' })).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Delete feature' })).toBeVisible()
  })
})
