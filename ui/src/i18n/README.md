# UI translations (i18n)

The AutoForge UI uses a small, dependency-free i18n layer.

- `locales/en.ts` — English catalog and **source of truth** for keys
- `locales/<id>.ts` — one file per additional language
- `index.ts` — `LOCALES` registry, `useI18n()` hook, lookup/interpolation
- `I18nProvider.tsx` — React provider (wired up in `src/main.tsx`)

The active language is picked in **Settings → Appearance → Language**. Until
a user picks one, the browser language is used (falling back to English).
The choice is stored in `localStorage` under `autoforge-locale`.

## Using translations in a component

```tsx
import { useI18n } from '@/i18n'

function Example({ count }: { count: number }) {
  const { t, tRich } = useI18n()
  return (
    <>
      <h1>{t('settings.title')}</h1>
      {/* `{name}` placeholders */}
      <p>{t('some.key', { count })}</p>
      {/* placeholders that need React elements */}
      <p>{tRich('settings.claudeAuthWarning', { loginCommand: <code>claude login</code>, envVar: <code>ANTHROPIC_API_KEY</code> })}</p>
    </>
  )
}
```

Keys are type-checked: `t('typo.key')` fails `npm run build`.

## Adding a new string

1. Add the key and English text to `locales/en.ts` (group by UI area, e.g. `kanban.*`).
2. Add the translation to every other locale file — they are typed as
   `Messages`, so the build fails if a key is missing.
3. Replace the hard-coded text in the component with `t('your.key')`.

Do not translate user/agent content (feature names, logs, chat messages),
product names, model IDs, or shell commands.

## Adding a new language

1. Copy `locales/zh-CN.ts` to `locales/<id>.ts` (use a BCP 47 tag such as `ja`
   or `pt-BR`), rename the export, and translate every value.
2. Register it in `LOCALES` in `index.ts` with its native name, e.g.
   `{ id: 'ja', nativeName: '日本語', messages: ja }`.
3. If browser tags need special matching (like `zh-Hans` → `zh-CN`), extend
   `matchLocale()`.
4. Run `npm run lint && npm run build`.

## Coverage

Currently translated: sidebar navigation and the Settings view. The rest of
the UI is still English-only; contributions that move more components onto
`t()` are welcome — the steps above apply unchanged.
