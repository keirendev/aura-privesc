import { createContext, useCallback, useContext, useEffect, useState } from 'react'

interface ThemeContextValue {
  isDark: boolean
  toggle: () => void
}

export const ThemeContext = createContext<ThemeContextValue>({
  isDark: true,
  toggle: () => {},
})

export function useThemeProvider() {
  const [isDark, setIsDark] = useState(() => {
    const stored = localStorage.getItem('theme')
    return stored ? stored === 'dark' : true
  })

  useEffect(() => {
    localStorage.setItem('theme', isDark ? 'dark' : 'light')
  }, [isDark])

  const toggle = useCallback(() => setIsDark(d => !d), [])

  return { isDark, toggle }
}

export function useTheme() {
  return useContext(ThemeContext)
}
