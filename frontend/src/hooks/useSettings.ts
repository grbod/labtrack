import { useCallback, useEffect, useState } from "react"

// Per-user settings stored in localStorage
export interface UserSettings {
  pageSize: number
}

// Global system settings (stored in localStorage for now, backend API later)
export interface SystemSettings {
  staleWarningDays: number
  staleCriticalDays: number
  recentlyCompletedDays: number
  labInfo: {
    companyName: string
    address: string
    phone: string
    email: string
    logoUrl: string | null
  }
}

const USER_SETTINGS_KEY = "userSettings"
const SYSTEM_SETTINGS_KEY = "systemSettings"

const DEFAULT_USER_SETTINGS: UserSettings = {
  pageSize: 25,
}

const DEFAULT_SYSTEM_SETTINGS: SystemSettings = {
  staleWarningDays: 7,
  staleCriticalDays: 12,
  recentlyCompletedDays: 7,
  labInfo: {
    companyName: "",
    address: "",
    phone: "",
    email: "",
    logoUrl: null,
  },
}

/**
 * Hook for managing per-user settings stored in localStorage.
 * Settings are scoped to the current user via their username.
 */
export function useUserSettings(username: string | undefined) {
  const storageKey = username ? `${USER_SETTINGS_KEY}_${username}` : null

  const [settings, setSettingsState] = useState<UserSettings>(() => {
    if (!storageKey) return DEFAULT_USER_SETTINGS
    try {
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        return { ...DEFAULT_USER_SETTINGS, ...JSON.parse(stored) }
      }
    } catch {
      // Invalid JSON, use defaults
    }
    return DEFAULT_USER_SETTINGS
  })

  // Re-sync from localStorage when username changes
  useEffect(() => {
    if (!storageKey) {
      setSettingsState(DEFAULT_USER_SETTINGS)
      return
    }
    try {
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        setSettingsState({ ...DEFAULT_USER_SETTINGS, ...JSON.parse(stored) })
      } else {
        setSettingsState(DEFAULT_USER_SETTINGS)
      }
    } catch {
      setSettingsState(DEFAULT_USER_SETTINGS)
    }
  }, [storageKey])

  const updateSettings = useCallback(
    (updates: Partial<UserSettings>) => {
      if (!storageKey) return

      setSettingsState((prev) => {
        const newSettings = { ...prev, ...updates }
        try {
          localStorage.setItem(storageKey, JSON.stringify(newSettings))
        } catch {
          // Storage full or unavailable
        }
        return newSettings
      })
    },
    [storageKey]
  )

  return { settings, updateSettings }
}

/**
 * Hook for managing global system settings.
 * Currently stored in localStorage; will be migrated to backend API.
 */
export function useSystemSettings() {
  const [settings, setSettingsState] = useState<SystemSettings>(() => {
    try {
      const stored = localStorage.getItem(SYSTEM_SETTINGS_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return {
          ...DEFAULT_SYSTEM_SETTINGS,
          ...parsed,
          labInfo: {
            ...DEFAULT_SYSTEM_SETTINGS.labInfo,
            ...(parsed.labInfo || {}),
          },
        }
      }
    } catch {
      // Invalid JSON, use defaults
    }
    return DEFAULT_SYSTEM_SETTINGS
  })

  const updateSettings = useCallback((updates: Partial<SystemSettings>) => {
    setSettingsState((prev) => {
      const newSettings = {
        ...prev,
        ...updates,
        labInfo: {
          ...prev.labInfo,
          ...(updates.labInfo || {}),
        },
      }
      try {
        localStorage.setItem(SYSTEM_SETTINGS_KEY, JSON.stringify(newSettings))
      } catch {
        // Storage full or unavailable
      }
      return newSettings
    })
  }, [])

  return { settings, updateSettings }
}

/**
 * Combined hook providing access to both user and system settings.
 * Determines if current user can edit system settings based on role.
 */
export function useSettings(username: string | undefined, role: string | undefined) {
  const userSettings = useUserSettings(username)
  const systemSettings = useSystemSettings()

  const normalizedRole = role?.toUpperCase()
  const canEditSystemSettings = normalizedRole === "ADMIN" || normalizedRole === "QC_MANAGER"

  return {
    user: userSettings,
    system: systemSettings,
    canEditSystemSettings,
  }
}

// Page size options for dropdown
export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const
