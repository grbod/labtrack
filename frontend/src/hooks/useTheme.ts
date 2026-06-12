import { useCallback, useSyncExternalStore } from "react"

const STORAGE_KEY = "labtrack-theme"
type Theme = "light" | "dark"

let listeners: Array<() => void> = []

function getTheme(): Theme {
  return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light"
}

export function applyStoredTheme() {
  document.documentElement.classList.toggle("dark", getTheme() === "dark")
}

function setTheme(theme: Theme) {
  localStorage.setItem(STORAGE_KEY, theme)
  document.documentElement.classList.toggle("dark", theme === "dark")
  listeners.forEach((l) => l())
}

export function useTheme() {
  const theme = useSyncExternalStore(
    (cb) => {
      listeners.push(cb)
      return () => {
        listeners = listeners.filter((l) => l !== cb)
      }
    },
    getTheme,
    () => "light" as Theme
  )
  const toggleTheme = useCallback(
    () => setTheme(getTheme() === "dark" ? "light" : "dark"),
    []
  )
  return { theme, toggleTheme }
}
