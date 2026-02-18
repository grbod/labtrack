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
        data?: { detail?: string }
        status?: number
      }
    }

    // Try to get detail from response body
    if (axiosError.response?.data?.detail) {
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
