import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  I18nContext,
  LOCALE_STORAGE_KEY,
  getInitialLocale,
  translate,
  translateRich,
  type I18nContextValue,
  type LocaleId,
} from './index'

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleId>(getInitialLocale)

  // Keep <html lang> in sync (screen readers, fonts, hyphenation)
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  // Only persist explicit choices, so the browser language keeps being
  // honored until the user picks one
  const setLocale = useCallback((next: LocaleId) => {
    setLocaleState(next)
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, next)
    } catch {
      // localStorage not available
    }
  }, [])

  const value = useMemo<I18nContextValue>(() => ({
    locale,
    setLocale,
    t: (key, values) => translate(locale, key, values),
    tRich: (key, values) => translateRich(locale, key, values),
  }), [locale, setLocale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
