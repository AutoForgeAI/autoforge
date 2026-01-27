# Custom Updates - AutoCoder

This document tracks all customizations made to AutoCoder that deviate from the upstream repository. Reference this file before any updates to preserve these changes.

---

## Table of Contents

1. [UI Theme Customization](#1-ui-theme-customization)
2. [Playwright Browser Configuration](#2-playwright-browser-configuration)
3. [Update Checklist](#update-checklist)

---

## 1. UI Theme Customization

### Overview

The UI has been customized from the default **neobrutalism** style to a clean **Twitter/Supabase-style** design.

**Design Changes:**
- No shadows
- Thin borders (1px)
- Rounded corners (1.3rem base)
- Blue accent color (Twitter blue)
- Clean typography (Open Sans)

### Modified Files

#### `ui/src/styles/custom-theme.css`

**Purpose:** Main theme override file that replaces neo design with clean Twitter style.

**Key Changes:**
- All `--shadow-neo-*` variables set to `none`
- All status colors (`pending`, `progress`, `done`) use Twitter blue
- Rounded corners: `--radius-neo-lg: 1.3rem`
- Font: Open Sans
- Removed all transform effects on hover
- Dark mode with proper contrast

**CSS Variables (Light Mode):**
```css
--color-neo-accent: oklch(0.6723 0.1606 244.9955);  /* Twitter blue */
--color-neo-pending: oklch(0.6723 0.1606 244.9955);
--color-neo-progress: oklch(0.6723 0.1606 244.9955);
--color-neo-done: oklch(0.6723 0.1606 244.9955);
```

**CSS Variables (Dark Mode):**
```css
--color-neo-bg: oklch(0.08 0 0);
--color-neo-card: oklch(0.16 0.005 250);
--color-neo-border: oklch(0.30 0 0);
```

**How to preserve:** This file should NOT be overwritten. It loads after `globals.css` and overrides it.

---

#### `ui/src/components/KanbanColumn.tsx`

**Purpose:** Modified to support themeable kanban columns without inline styles.

**Changes:**

1. **colorMap changed from inline colors to CSS classes:**
```tsx
// BEFORE (original):
const colorMap = {
  pending: 'var(--color-neo-pending)',
  progress: 'var(--color-neo-progress)',
  done: 'var(--color-neo-done)',
}

// AFTER (customized):
const colorMap = {
  pending: 'kanban-header-pending',
  progress: 'kanban-header-progress',
  done: 'kanban-header-done',
}
```

2. **Column div uses CSS class instead of inline style:**
```tsx
// BEFORE:
<div className="neo-card overflow-hidden" style={{ borderColor: colorMap[color] }}>

// AFTER:
<div className={`neo-card overflow-hidden kanban-column ${colorMap[color]}`}>
```

3. **Header div simplified (removed duplicate color class):**
```tsx
// BEFORE:
<div className={`... ${colorMap[color]}`} style={{ backgroundColor: colorMap[color] }}>

// AFTER:
<div className="kanban-header px-4 py-3 border-b border-[var(--color-neo-border)]">
```

4. **Title text color:**
```tsx
// BEFORE:
text-[var(--color-neo-text-on-bright)]

// AFTER:
text-[var(--color-neo-text)]
```

---

## 2. Playwright Browser Configuration

### Overview

Changed default Playwright settings for better performance:
- **Default browser:** Firefox (lower CPU usage)
- **Default mode:** Headless (saves resources)

### Modified Files

#### `client.py`

**Changes:**

```python
# BEFORE:
DEFAULT_PLAYWRIGHT_HEADLESS = False

# AFTER:
DEFAULT_PLAYWRIGHT_HEADLESS = True
DEFAULT_PLAYWRIGHT_BROWSER = "firefox"
```

**New function added:**
```python
def get_playwright_browser() -> str:
    """
    Get the browser to use for Playwright.
    Options: chrome, firefox, webkit, msedge
    Firefox is recommended for lower CPU usage.
    """
    return os.getenv("PLAYWRIGHT_BROWSER", DEFAULT_PLAYWRIGHT_BROWSER).lower()
```

**Playwright args updated:**
```python
playwright_args = [
    "@playwright/mcp@latest",
    "--viewport-size", "1280x720",
    "--browser", browser,  # NEW: configurable browser
]
```

---

#### `.env.example`

**Updated documentation:**
```bash
# PLAYWRIGHT_BROWSER: Which browser to use for testing
# - firefox: Lower CPU usage, recommended (default)
# - chrome: Google Chrome
# - webkit: Safari engine
# - msedge: Microsoft Edge
# PLAYWRIGHT_BROWSER=firefox

# PLAYWRIGHT_HEADLESS: Run browser without visible window
# - true: Browser runs in background, saves CPU (default)
# - false: Browser opens a visible window (useful for debugging)
# PLAYWRIGHT_HEADLESS=true
```

---

## 3. Update Checklist

When updating AutoCoder from upstream, verify these items:

### UI Changes
- [ ] `ui/src/styles/custom-theme.css` is preserved
- [ ] `ui/src/components/KanbanColumn.tsx` changes are preserved
- [ ] Run `npm run build` in `ui/` directory
- [ ] Test both light and dark modes

### Backend Changes
- [ ] `client.py` - Playwright browser/headless defaults preserved
- [ ] `.env.example` - Documentation updates preserved

### General
- [ ] Verify Playwright uses Firefox by default
- [ ] Check that browser runs headless by default

---

## Reverting to Defaults

### UI Only
```bash
rm ui/src/styles/custom-theme.css
git checkout ui/src/components/KanbanColumn.tsx
cd ui && npm run build
```

### Backend Only
```bash
git checkout client.py .env.example
```

---

## Files Summary

| File | Type | Change Description |
|------|------|-------------------|
| `ui/src/styles/custom-theme.css` | UI | Twitter-style theme |
| `ui/src/components/KanbanColumn.tsx` | UI | Themeable kanban columns |
| `ui/src/main.tsx` | UI | Imports custom theme |
| `client.py` | Backend | Firefox + headless defaults |
| `.env.example` | Config | Updated documentation |

---

## Last Updated

**Date:** January 2026
**PR:** #93 - Twitter-style UI theme with custom theme override system
