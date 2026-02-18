/**
 * Date formatting utilities for consistent date display across the application.
 */

/**
 * Format date as short readable string (e.g., "Jan 15, 2024")
 */
export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

/**
 * Calculate relative time string from a date.
 * Returns human-readable relative time like "Today", "2 days ago", "1 week ago".
 *
 * @param dateString - ISO date string to calculate relative time from
 * @returns Relative time string (e.g., "Today", "2 days ago", "1 month ago")
 */
export function getRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return "Today"
  if (diffDays === 1) return "1 day ago"
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 14) return "1 week ago"
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  if (diffDays < 60) return "1 month ago"
  return `${Math.floor(diffDays / 30)} months ago`
}

/**
 * Format date as short date + compact relative time.
 * Returns combined format like "Jan 31 (2d ago)" for compact display.
 *
 * @param dateString - ISO date string to format
 * @returns Formatted string with short date and relative time (e.g., "Jan 31 (today)")
 */
export function formatDateWithRelative(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  // Short date: "Jan 31"
  const shortDate = date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })

  // Compact relative time
  let relative: string
  if (diffDays === 0) relative = "today"
  else if (diffDays === 1) relative = "1d ago"
  else if (diffDays < 7) relative = `${diffDays}d ago`
  else if (diffDays < 30) relative = `${Math.floor(diffDays / 7)}w ago`
  else relative = `${Math.floor(diffDays / 30)}mo ago`

  return `${shortDate} (${relative})`
}
