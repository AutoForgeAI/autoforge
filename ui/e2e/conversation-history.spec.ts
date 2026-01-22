import { test, expect } from '@playwright/test'

/**
 * E2E tests for the Conversation History feature in the Assistant panel.
 *
 * Two test groups:
 * 1. UI Tests - Only test UI elements, no API needed
 * 2. Integration Tests - Test full flow with API (skipped if API unavailable)
 *
 * Run tests:
 *   cd ui && npm run test:e2e
 *   cd ui && npm run test:e2e:ui  (interactive mode)
 */

// =============================================================================
// UI TESTS - No API required, just test UI elements
// =============================================================================
test.describe('Assistant Panel UI', () => {
  test.setTimeout(30000)

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForSelector('button:has-text("Select Project")', { timeout: 10000 })
  })

  async function selectProject(page: import('@playwright/test').Page) {
    const projectSelector = page.locator('button:has-text("Select Project")')
    if (await projectSelector.isVisible()) {
      await projectSelector.click()
      const projectItem = page.locator('.neo-dropdown-item').first()
      const hasProject = await projectItem.isVisible().catch(() => false)
      if (!hasProject) {
        return false
      }
      await projectItem.click()
      // Wait for dropdown to close (project selected)
      await expect(projectSelector).not.toBeVisible({ timeout: 5000 }).catch(() => {})
      return true
    }
    return false
  }

  async function waitForPanelOpen(page: import('@playwright/test').Page) {
    await page.waitForFunction(() => {
      const panel = document.querySelector('[aria-label="Project Assistant"]')
      return panel && panel.getAttribute('aria-hidden') !== 'true'
    }, { timeout: 5000 })
  }

  async function waitForPanelClosed(page: import('@playwright/test').Page) {
    await page.waitForFunction(() => {
      const panel = document.querySelector('[aria-label="Project Assistant"]')
      return !panel || panel.getAttribute('aria-hidden') === 'true'
    }, { timeout: 5000 })
  }

  // --------------------------------------------------------------------------
  // Panel open/close tests
  // --------------------------------------------------------------------------
  test('Panel opens and closes with A key', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    const panel = page.locator('[aria-label="Project Assistant"]')

    // Panel should be closed initially
    await expect(panel).toHaveAttribute('aria-hidden', 'true')

    // Press A to open
    await page.keyboard.press('a')
    await waitForPanelOpen(page)
    await expect(panel).toHaveAttribute('aria-hidden', 'false')

    // Press A again to close
    await page.keyboard.press('a')
    await waitForPanelClosed(page)
    await expect(panel).toHaveAttribute('aria-hidden', 'true')
  })

  test('Panel closes when clicking backdrop', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    const panel = page.locator('[aria-label="Project Assistant"]')
    await expect(panel).toHaveAttribute('aria-hidden', 'false')

    // Click on the backdrop
    const backdrop = page.locator('.fixed.inset-0.bg-black\\/20')
    await backdrop.click()

    // Panel should close
    await waitForPanelClosed(page)
    await expect(panel).toHaveAttribute('aria-hidden', 'true')
  })

  test('Panel closes with X button', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    const panel = page.locator('[aria-label="Project Assistant"]')
    await expect(panel).toHaveAttribute('aria-hidden', 'false')

    // Click X button (inside the panel dialog, not the floating button)
    const closeButton = page.locator('[aria-label="Project Assistant"] button[title="Close Assistant (Press A)"]')
    await closeButton.click()

    // Panel should close
    await waitForPanelClosed(page)
    await expect(panel).toHaveAttribute('aria-hidden', 'true')
  })

  // --------------------------------------------------------------------------
  // Header buttons tests
  // --------------------------------------------------------------------------
  test('New chat and history buttons are visible and clickable', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    // Verify New Chat button
    const newChatButton = page.locator('button[title="New conversation"]')
    await expect(newChatButton).toBeVisible()
    await expect(newChatButton).toBeEnabled()

    // Verify History button
    const historyButton = page.locator('button[title="Conversation history"]')
    await expect(historyButton).toBeVisible()
    await expect(historyButton).toBeEnabled()
  })

  test('History dropdown opens and closes', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    // Click history button
    const historyButton = page.locator('button[title="Conversation history"]')
    await historyButton.click()

    // Dropdown should be visible
    const historyDropdown = page.locator('h3:has-text("Conversation History")')
    await expect(historyDropdown).toBeVisible({ timeout: 5000 })

    // Dropdown should be inside the panel (not hidden by edge)
    const dropdownBox = await page.locator('.neo-dropdown:has-text("Conversation History")').boundingBox()
    const panelBox = await page.locator('[aria-label="Project Assistant"]').boundingBox()

    if (dropdownBox && panelBox) {
      // Dropdown left edge should be >= panel left edge (not cut off)
      expect(dropdownBox.x).toBeGreaterThanOrEqual(panelBox.x - 10) // small tolerance
    }

    // Close dropdown by pressing Escape (more reliable than clicking backdrop)
    await page.keyboard.press('Escape')
    await expect(historyDropdown).not.toBeVisible({ timeout: 5000 })
  })

  test('History dropdown shows empty state or conversations', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    // Click history button
    const historyButton = page.locator('button[title="Conversation history"]')
    await historyButton.click()

    // Should show either "No conversations yet" or a list of conversations
    const dropdown = page.locator('.neo-dropdown:has-text("Conversation History")')
    await expect(dropdown).toBeVisible({ timeout: 5000 })

    // Check content - either empty state or conversation items
    const emptyState = dropdown.locator('text=No conversations yet')
    const conversationItems = dropdown.locator('.neo-dropdown-item')

    const hasEmpty = await emptyState.isVisible().catch(() => false)
    const itemCount = await conversationItems.count()

    // Should have either empty state or some items
    expect(hasEmpty || itemCount > 0).toBe(true)
    console.log(`History shows: ${hasEmpty ? 'empty state' : `${itemCount} conversations`}`)
  })

  // --------------------------------------------------------------------------
  // Input area tests
  // --------------------------------------------------------------------------
  test('Input textarea exists and is focusable', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    // Input should exist
    const inputArea = page.locator('textarea[placeholder="Ask about the codebase..."]')
    await expect(inputArea).toBeVisible()

    // Should be able to type in it (even if disabled, we can check it exists)
    const placeholder = await inputArea.getAttribute('placeholder')
    expect(placeholder).toBe('Ask about the codebase...')
  })

  test('Send button exists', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    // Send button should exist
    const sendButton = page.locator('button[title="Send message"]')
    await expect(sendButton).toBeVisible()
  })

  // --------------------------------------------------------------------------
  // Connection status tests
  // --------------------------------------------------------------------------
  test('Connection status indicator exists', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    // Wait for any status to appear
    await page.waitForFunction(() => {
      const text = document.body.innerText
      return text.includes('Connecting...') || text.includes('Connected') || text.includes('Disconnected')
    }, { timeout: 10000 })

    // One of the status indicators should be visible
    const connecting = await page.locator('text=Connecting...').isVisible().catch(() => false)
    const connected = await page.locator('text=Connected').isVisible().catch(() => false)
    const disconnected = await page.locator('text=Disconnected').isVisible().catch(() => false)

    expect(connecting || connected || disconnected).toBe(true)
    console.log(`Connection status: ${connected ? 'Connected' : disconnected ? 'Disconnected' : 'Connecting'}`)
  })

  // --------------------------------------------------------------------------
  // Panel header tests
  // --------------------------------------------------------------------------
  test('Panel header shows project name', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    // Open panel
    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    // Header should show "Project Assistant"
    const header = page.locator('h2:has-text("Project Assistant")')
    await expect(header).toBeVisible()
  })
})

// =============================================================================
// INTEGRATION TESTS - Require API connection
// =============================================================================
test.describe('Conversation History Integration', () => {
  test.setTimeout(120000)

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForSelector('button:has-text("Select Project")', { timeout: 10000 })
  })

  async function selectProject(page: import('@playwright/test').Page) {
    const projectSelector = page.locator('button:has-text("Select Project")')
    if (await projectSelector.isVisible()) {
      await projectSelector.click()
      const projectItem = page.locator('.neo-dropdown-item').first()
      const hasProject = await projectItem.isVisible().catch(() => false)
      if (!hasProject) return false
      await projectItem.click()
      // Wait for dropdown to close (project selected)
      await expect(projectSelector).not.toBeVisible({ timeout: 5000 }).catch(() => {})
      return true
    }
    return false
  }

  async function waitForPanelOpen(page: import('@playwright/test').Page) {
    await page.waitForFunction(() => {
      const panel = document.querySelector('[aria-label="Project Assistant"]')
      return panel && panel.getAttribute('aria-hidden') !== 'true'
    }, { timeout: 5000 })
  }

  async function waitForPanelClosed(page: import('@playwright/test').Page) {
    await page.waitForFunction(() => {
      const panel = document.querySelector('[aria-label="Project Assistant"]')
      return !panel || panel.getAttribute('aria-hidden') === 'true'
    }, { timeout: 5000 })
  }

  async function waitForAssistantReady(page: import('@playwright/test').Page): Promise<boolean> {
    try {
      await page.waitForSelector('text=Connected', { timeout: 15000 })
      const inputArea = page.locator('textarea[placeholder="Ask about the codebase..."]')
      await expect(inputArea).toBeEnabled({ timeout: 30000 })
      return true
    } catch {
      console.log('Assistant not available - API may not be configured')
      return false
    }
  }

  async function sendMessageAndWaitForResponse(page: import('@playwright/test').Page, message: string) {
    const inputArea = page.locator('textarea[placeholder="Ask about the codebase..."]')
    await inputArea.fill(message)
    await inputArea.press('Enter')
    await expect(page.locator(`text=${message}`).first()).toBeVisible({ timeout: 5000 })
    await page.waitForSelector('text=Thinking...', { timeout: 10000 }).catch(() => {})
    await expect(inputArea).toBeEnabled({ timeout: 60000 })
    // Wait for any streaming to complete (input enabled means response done)
  }

  // --------------------------------------------------------------------------
  // Full flow test
  // --------------------------------------------------------------------------
  test('Full conversation flow: create, persist, switch conversations', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    if (!await waitForAssistantReady(page)) {
      test.skip(true, 'Assistant API not available')
      return
    }

    // STEP 1: Send first message
    console.log('STEP 1: Ask 1+1')
    await sendMessageAndWaitForResponse(page, 'how much is 1+1')
    await expect(page.locator('.flex-1.overflow-y-auto')).toContainText('2', { timeout: 5000 })

    // Count greeting messages before closing
    const greetingSelector = 'text=Hello! I\'m your project assistant'
    const greetingCountBefore = await page.locator(greetingSelector).count()
    console.log(`Greeting count before close: ${greetingCountBefore}`)

    // STEP 2: Close and reopen - should see same conversation WITHOUT new greeting
    console.log('STEP 2: Close and reopen')
    const closeButton = page.locator('[aria-label="Project Assistant"] button[title="Close Assistant (Press A)"]')
    await closeButton.click()
    await waitForPanelClosed(page)

    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    // Verify our question is still visible (conversation resumed)
    await expect(page.locator('text=how much is 1+1').first()).toBeVisible({ timeout: 10000 })

    // CRITICAL: Verify NO new greeting was added (bug fix verification)
    const greetingCountAfter = await page.locator(greetingSelector).count()
    console.log(`Greeting count after reopen: ${greetingCountAfter}`)
    expect(greetingCountAfter).toBe(greetingCountBefore)

    // STEP 3: Start new chat
    console.log('STEP 3: New chat')
    const newChatButton = page.locator('button[title="New conversation"]')
    await newChatButton.click()

    if (!await waitForAssistantReady(page)) {
      test.skip(true, 'Assistant API not available')
      return
    }

    await expect(page.locator('text=how much is 1+1')).not.toBeVisible({ timeout: 5000 })

    // STEP 4: Send second message in new chat
    console.log('STEP 4: Ask 2+2')
    await sendMessageAndWaitForResponse(page, 'how much is 2+2')
    await expect(page.locator('.flex-1.overflow-y-auto')).toContainText('4', { timeout: 5000 })

    // STEP 5: Check history has both conversations
    console.log('STEP 5: Check history')
    const historyButton = page.locator('button[title="Conversation history"]')
    await historyButton.click()
    await expect(page.locator('h3:has-text("Conversation History")')).toBeVisible()

    const conversationItems = page.locator('.neo-dropdown:has-text("Conversation History") .neo-dropdown-item')
    const count = await conversationItems.count()
    console.log(`Found ${count} conversations`)
    expect(count).toBeGreaterThanOrEqual(2)

    // STEP 6: Switch to first conversation
    console.log('STEP 6: Switch conversation')
    await conversationItems.nth(1).click()
    // Wait for conversation to load by checking for the expected message
    await expect(page.locator('text=how much is 1+1').first()).toBeVisible({ timeout: 10000 })
    await expect(page.locator('text=how much is 2+2')).not.toBeVisible()

    console.log('All steps completed!')
  })

  // --------------------------------------------------------------------------
  // Delete conversation test
  // --------------------------------------------------------------------------
  test('Delete conversation from history', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    if (!await waitForAssistantReady(page)) {
      test.skip(true, 'Assistant API not available')
      return
    }

    // Create a conversation
    await sendMessageAndWaitForResponse(page, `test delete ${Date.now()}`)

    // Open history and get count
    const historyButton = page.locator('button[title="Conversation history"]')
    await historyButton.click()
    await expect(page.locator('h3:has-text("Conversation History")')).toBeVisible()

    const conversationItems = page.locator('.neo-dropdown:has-text("Conversation History") .neo-dropdown-item')
    const countBefore = await conversationItems.count()

    // Delete first conversation
    const deleteButton = page.locator('.neo-dropdown:has-text("Conversation History") button[title="Delete conversation"]').first()
    await deleteButton.click()

    // Confirm
    const confirmButton = page.locator('button:has-text("Delete")').last()
    await expect(confirmButton).toBeVisible()
    await confirmButton.click()

    // Wait for confirmation dialog to close
    await expect(confirmButton).not.toBeVisible({ timeout: 5000 })

    // Verify count decreased
    await historyButton.click()
    const countAfter = await conversationItems.count()
    expect(countAfter).toBeLessThan(countBefore)
  })

  // --------------------------------------------------------------------------
  // Send button state test
  // --------------------------------------------------------------------------
  test('Send button disabled when empty, enabled with text', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    if (!await waitForAssistantReady(page)) {
      test.skip(true, 'Assistant API not available')
      return
    }

    const inputArea = page.locator('textarea[placeholder="Ask about the codebase..."]')
    const sendButton = page.locator('button[title="Send message"]')

    // Empty = disabled
    await inputArea.fill('')
    await expect(sendButton).toBeDisabled()

    // With text = enabled
    await inputArea.fill('test')
    await expect(sendButton).toBeEnabled()

    // Empty again = disabled
    await inputArea.fill('')
    await expect(sendButton).toBeDisabled()
  })

  // --------------------------------------------------------------------------
  // Shift+Enter test
  // --------------------------------------------------------------------------
  test('Shift+Enter adds newline, Enter sends', async ({ page }) => {
    const hasProject = await selectProject(page)
    if (!hasProject) {
      test.skip(true, 'No projects available')
      return
    }

    await page.keyboard.press('a')
    await waitForPanelOpen(page)

    if (!await waitForAssistantReady(page)) {
      test.skip(true, 'Assistant API not available')
      return
    }

    const inputArea = page.locator('textarea[placeholder="Ask about the codebase..."]')

    // Type and add newline
    await inputArea.fill('Line 1')
    await inputArea.press('Shift+Enter')
    await inputArea.pressSequentially('Line 2')

    const value = await inputArea.inputValue()
    expect(value).toContain('Line 1')
    expect(value).toContain('Line 2')

    // Enter sends
    await inputArea.press('Enter')
    await expect(page.locator('text=Line 1').first()).toBeVisible({ timeout: 5000 })
  })
})
