/**
 * Spec validation utilities for test results.
 * Ported from backend/app/models/product_test_spec.py matches_result() method.
 */

/**
 * Accepted values for specs starting with "Negative" (case-insensitive)
 */
export const NEGATIVE_ACCEPTED_VALUES = ['negative', 'nd', 'not detected', 'bdl']

/**
 * Accepted values for specs starting with "Positive" (case-insensitive)
 */
export const POSITIVE_ACCEPTED_VALUES = ['positive', 'detected', 'present', '+']

/**
 * Check if a spec starts with "Negative" (case-insensitive)
 * e.g., "Negative", "Negative in 10g", "Negative per 10g"
 */
export function isNegativeSpec(specification: string): boolean {
  return specification.trim().toLowerCase().startsWith('negative')
}

/**
 * Check if a spec starts with "Positive" (case-insensitive)
 * e.g., "Positive", "Positive in 10g"
 */
export function isPositiveSpec(specification: string): boolean {
  return specification.trim().toLowerCase().startsWith('positive')
}

/**
 * Check if a test result value matches a specification.
 *
 * @param resultValue - The actual test result value
 * @param specification - The acceptance criteria (e.g., "< 10", "Negative")
 * @param testUnit - The test unit (e.g., "Positive/Negative", "CFU/g")
 * @returns true if passes, false if fails
 */
export function matchesResult(
  resultValue: string | null,
  specification: string,
  testUnit: string | null
): boolean {
  if (!resultValue || !resultValue.trim()) {
    return false
  }

  const spec = specification.trim().toLowerCase()
  const value = resultValue.trim().toLowerCase()

  // Handle Positive/Negative results (legacy unit-based check)
  // Only apply P/N logic if the spec is actually "negative" or "positive"
  if (testUnit === "Positive/Negative") {
    if (spec === "negative" && NEGATIVE_ACCEPTED_VALUES.includes(value)) {
      return true
    }
    if (spec === "positive" && POSITIVE_ACCEPTED_VALUES.includes(value)) {
      return true
    }
    // If spec is neither "negative" nor "positive", fall through to other checks
    // This handles cases where testUnit is misconfigured
    if (spec === "negative" || spec === "positive") {
      return false
    }
  }

  // Handle specs starting with "Negative" (e.g., "Negative in 10g")
  if (isNegativeSpec(specification)) {
    // Accept: Negative, ND, Not Detected, BDL, or any <X value
    if (NEGATIVE_ACCEPTED_VALUES.includes(value)) {
      return true
    }
    // Also accept "<X" values (below detection limit)
    if (value.startsWith('<')) {
      return true
    }
    return false
  }

  // Handle specs starting with "Positive" (e.g., "Positive in 10g")
  if (isPositiveSpec(specification)) {
    // Accept: Positive, Detected, Present, +
    return POSITIVE_ACCEPTED_VALUES.includes(value)
  }

  // Handle "< X" specifications
  if (spec.startsWith("<")) {
    const specLimit = parseFloat(spec.slice(1).trim())
    if (isNaN(specLimit)) return false
    if (value.startsWith("<")) {
      // Both are "less than" values - pass
      return true
    }
    const resultVal = parseFloat(value)
    return !isNaN(resultVal) && resultVal < specLimit
  }

  // Handle "> X" specifications
  if (spec.startsWith(">")) {
    const specLimit = parseFloat(spec.slice(1).trim())
    if (isNaN(specLimit)) return false
    if (value.startsWith(">")) {
      // Both are "greater than" values - pass
      return true
    }
    const resultVal = parseFloat(value)
    return !isNaN(resultVal) && resultVal > specLimit
  }

  // Handle range specifications (e.g., "5-10")
  if (spec.includes("-") && !spec.startsWith("-")) {
    const parts = spec.split("-")
    if (parts.length === 2) {
      const minVal = parseFloat(parts[0].trim())
      const maxVal = parseFloat(parts[1].trim())
      const resultVal = parseFloat(value)
      if (!isNaN(minVal) && !isNaN(maxVal) && !isNaN(resultVal)) {
        return resultVal >= minVal && resultVal <= maxVal
      }
    }
  }

  // Handle exact match
  return spec === value
}

/**
 * Determine the appropriate input type based on specification and unit.
 *
 * @param specification - The acceptance criteria
 * @param testUnit - The test unit
 * @returns 'dropdown' for P/N unit tests, 'autocomplete' for neg/pos specs, 'number' for numeric specs, 'text' otherwise
 */
export function getInputTypeForSpec(
  specification: string,
  testUnit: string | null
): 'dropdown' | 'autocomplete' | 'number' | 'text' {
  // Positive/Negative tests with explicit unit get a dropdown
  if (testUnit === "Positive/Negative") {
    return 'dropdown'
  }

  // Specs starting with Negative/Positive get autocomplete
  if (isNegativeSpec(specification) || isPositiveSpec(specification)) {
    return 'autocomplete'
  }

  const spec = specification.trim().toLowerCase()

  // Numeric comparisons get number input
  if (spec.startsWith("<") || spec.startsWith(">")) {
    return 'number'
  }

  // Range specifications get number input
  if (spec.includes("-") && !spec.startsWith("-")) {
    const parts = spec.split("-")
    if (parts.length === 2) {
      const minVal = parseFloat(parts[0].trim())
      const maxVal = parseFloat(parts[1].trim())
      if (!isNaN(minVal) && !isNaN(maxVal)) {
        return 'number'
      }
    }
  }

  return 'text'
}

/**
 * Dropdown options for Positive/Negative tests (legacy unit-based).
 */
export const POSITIVE_NEGATIVE_OPTIONS = [
  { value: 'Negative', label: 'Negative' },
  { value: 'Positive', label: 'Positive' },
  { value: 'ND', label: 'ND (Not Detected)' },
] as const

/**
 * Get autocomplete options for a negative/positive spec with pass/fail hints.
 */
export function getAutocompleteOptions(specification: string): Array<{
  value: string
  label: string
  passes: boolean
}> {
  if (isNegativeSpec(specification)) {
    return [
      { value: 'Negative', label: 'Negative', passes: true },
      { value: 'ND', label: 'ND (Not Detected)', passes: true },
      { value: 'Not Detected', label: 'Not Detected', passes: true },
      { value: 'BDL', label: 'BDL (Below Detection Limit)', passes: true },
      { value: 'Positive', label: 'Positive', passes: false },
      { value: 'Detected', label: 'Detected', passes: false },
    ]
  }

  if (isPositiveSpec(specification)) {
    return [
      { value: 'Positive', label: 'Positive', passes: true },
      { value: 'Detected', label: 'Detected', passes: true },
      { value: 'Present', label: 'Present', passes: true },
      { value: '+', label: '+ (Positive)', passes: true },
      { value: 'Negative', label: 'Negative', passes: false },
      { value: 'ND', label: 'ND (Not Detected)', passes: false },
    ]
  }

  return []
}

/**
 * Calculate pass/fail status for a test result.
 *
 * @param resultValue - The actual test result value
 * @param specification - The acceptance criteria
 * @param testUnit - The test unit
 * @returns 'pass', 'fail', or null if no result
 */
export function calculatePassFail(
  resultValue: string | null,
  specification: string | null,
  testUnit: string | null
): 'pass' | 'fail' | null {
  if (!resultValue || !resultValue.trim()) {
    return null
  }

  if (!specification) {
    // No spec to validate against
    return null
  }

  return matchesResult(resultValue, specification, testUnit) ? 'pass' : 'fail'
}
