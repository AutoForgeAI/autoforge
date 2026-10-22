/**
 * Lightweight internationalization (i18n) for the AutoForge UI.
 *
 * - Message catalogs live in `./locales/` (English is the source of truth).
 * - Wrap the app in <I18nProvider> and call `useI18n()` in components.
 * - `t('some.key', { name: 'x' })` returns a translated string with `{name}`
 *   placeholders filled in. `tRich` does the same but accepts React nodes as
 *   values (e.g. <code> elements) and returns renderable children.
 * - Missing translations fall back to English, then to the key itself.
 *
 * To add a language, see ui/src/i18n/README.md.
 */
import { createContext, useContext, Fragment, createElement, type ReactNode } from 'react'
import { en, type Messages, type TranslationKey } from './locales/en'
import { zhCN } from './locales/zh-CN'

export type { TranslationKey } from './locales/en'

export interface LocaleOption {
  id: string
  /** Name of the language in that language (e.g. "简体中文") */
  nativeName: string
  messages: Partial<Messages>
}

export const LOCALES = [
  { id: 'en', nativeName: 'English', messages: en },
  { id: 'zh-CN', nativeName: '简体中文', messages: zhCN },
] as const satisfies readonly LocaleOption[]

export type LocaleId = (typeof LOCALES)[number]['id']

export const DEFAULT_LOCALE: LocaleId = 'en'
export const LOCALE_STORAGE_KEY = 'autoforge-locale'

export type TranslationValues = Record<string, string | number>
export type RichTranslationValues = Record<string, ReactNode>

export function isLocaleId(value: unknown): value is LocaleId {
  return LOCALES.some(l => l.id === value)
}

/**
 * Pick the best supported locale for a list of BCP 47 language tags
 * (e.g. navigator.languages), falling back to English. Only Simplified
 * Chinese tags (zh, zh-CN, zh-SG, zh-Hans*) map to zh-CN; Traditional
 * Chinese (zh-TW, zh-HK) does not.
 */
export function matchLocale(languages: readonly string[]): LocaleId {
  for (const raw of languages) {
    const tag = raw.toLowerCase()
    const exact = LOCALES.find(l => l.id.toLowerCase() === tag)
    if (exact) return exact.id
    if (tag === 'zh' || tag.startsWith('zh-hans') || tag === 'zh-sg') return 'zh-CN'
    const base = tag.split('-')[0]
    const byBase = LOCALES.find(l => l.id.toLowerCase() === base)
    if (byBase) return byBase.id
  }
  return DEFAULT_LOCALE
}

export function getInitialLocale(): LocaleId {
  try {
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY)
    if (isLocaleId(stored)) return stored
  } catch {
    // localStorage not available
  }
  if (typeof navigator !== 'undefined') {
    return matchLocale(navigator.languages?.length ? navigator.languages : [navigator.language])
  }
  return DEFAULT_LOCALE
}

function lookup(locale: LocaleId, key: TranslationKey): string {
  const messages: Partial<Messages> = LOCALES.find(l => l.id === locale)?.messages ?? en
  return messages[key] ?? en[key] ?? key
}

const PLACEHOLDER = /\{(\w+)\}/g

export function translate(locale: LocaleId, key: TranslationKey, values?: TranslationValues): string {
  const message = lookup(locale, key)
  if (!values) return message
  return message.replace(PLACEHOLDER, (match, name: string) =>
    name in values ? String(values[name]) : match,
  )
}

export function translateRich(locale: LocaleId, key: TranslationKey, values: RichTranslationValues): ReactNode {
  const message = lookup(locale, key)
  // split() with a capture group yields [text, name, text, name, ..., text]
  const parts = message.split(PLACEHOLDER)
  return parts.map((part, i) => {
    if (i % 2 === 0) return part
    const node = part in values ? values[part] : `{${part}}`
    return createElement(Fragment, { key: i }, node)
  })
}

export interface I18nContextValue {
  locale: LocaleId
  setLocale: (locale: LocaleId) => void
  t: (key: TranslationKey, values?: TranslationValues) => string
  tRich: (key: TranslationKey, values: RichTranslationValues) => ReactNode
}

export const I18nContext = createContext<I18nContextValue>({
  locale: DEFAULT_LOCALE,
  setLocale: () => {},
  t: (key, values) => translate(DEFAULT_LOCALE, key, values),
  tRich: (key, values) => translateRich(DEFAULT_LOCALE, key, values),
})

export function useI18n(): I18nContextValue {
  return useContext(I18nContext)
}
