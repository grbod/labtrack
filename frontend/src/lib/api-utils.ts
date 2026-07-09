/**
 * Extract error message from axios error response with sensible fallbacks.
 */
export function extractApiErrorMessage(
  error: unknown,
  defaultMessage: string,
  statusMessages?: Record<number, string>
): string {
  if (error && typeof error === "object") {
    const axiosError = error as {
      response?: {
        data?: { detail?: unknown }
        status?: number
      }
    }

    // Try to get detail from response body (structured detail objects, e.g. the
    // release-gate's 409 body, are handled by extractGateBlockedDetail instead)
    if (typeof axiosError.response?.data?.detail === "string") {
      return axiosError.response.data.detail
    }

    // Check for status-specific messages
    const status = axiosError.response?.status
    if (status && statusMessages?.[status]) {
      return statusMessages[status]
    }
  }

  return defaultMessage
}

/**
 * Extract the structured 409 body the release-gate returns when an approve is
 * blocked (`{ code, reason, missing_tests, failing_tests }`). Returns null for
 * any other error shape so callers can fall back to extractApiErrorMessage.
 */
export function extractGateBlockedDetail(error: unknown): {
  reason: string
  missing_tests: string[]
  failing_tests: string[]
} | null {
  if (error && typeof error === "object") {
    const axiosError = error as { response?: { data?: { detail?: unknown } } }
    const detail = axiosError.response?.data?.detail
    if (detail && typeof detail === "object" && "reason" in detail) {
      const d = detail as {
        reason?: string
        missing_tests?: string[]
        failing_tests?: string[]
      }
      return {
        reason: d.reason ?? "Release gate not satisfied",
        missing_tests: d.missing_tests ?? [],
        failing_tests: d.failing_tests ?? [],
      }
    }
  }
  return null
}
