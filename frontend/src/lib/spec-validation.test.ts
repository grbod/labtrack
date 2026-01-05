import { describe, it, expect } from 'vitest'
import {
  matchesResult,
  getInputTypeForSpec,
  calculatePassFail,
  POSITIVE_NEGATIVE_OPTIONS,
  isNegativeSpec,
  isPositiveSpec,
  getAutocompleteOptions,
  NEGATIVE_ACCEPTED_VALUES,
  POSITIVE_ACCEPTED_VALUES,
} from './spec-validation'

describe('spec-validation', () => {
  describe('matchesResult', () => {
    describe('Positive/Negative tests', () => {
      it('returns true for Negative spec with "negative" result', () => {
        expect(matchesResult('Negative', 'Negative', 'Positive/Negative')).toBe(true)
        expect(matchesResult('negative', 'Negative', 'Positive/Negative')).toBe(true)
      })

      it('returns true for Negative spec with "nd" result', () => {
        expect(matchesResult('ND', 'Negative', 'Positive/Negative')).toBe(true)
        expect(matchesResult('nd', 'Negative', 'Positive/Negative')).toBe(true)
      })

      it('returns true for Negative spec with "not detected" result', () => {
        expect(matchesResult('Not Detected', 'Negative', 'Positive/Negative')).toBe(true)
        expect(matchesResult('not detected', 'Negative', 'Positive/Negative')).toBe(true)
      })

      it('returns true for Positive spec with "positive" result', () => {
        expect(matchesResult('Positive', 'Positive', 'Positive/Negative')).toBe(true)
        expect(matchesResult('positive', 'Positive', 'Positive/Negative')).toBe(true)
      })

      it('returns false for Negative spec with "positive" result', () => {
        expect(matchesResult('Positive', 'Negative', 'Positive/Negative')).toBe(false)
      })

      it('returns false for Positive spec with "negative" result', () => {
        expect(matchesResult('Negative', 'Positive', 'Positive/Negative')).toBe(false)
      })

      it('falls through to exact match when spec is not neg/pos (misconfigured testUnit)', () => {
        // When testUnit is "Positive/Negative" but spec is a value like "5" or "White",
        // the validation should fall through to exact match instead of returning false
        expect(matchesResult('5', '5', 'Positive/Negative')).toBe(true)
        expect(matchesResult('White', 'White', 'Positive/Negative')).toBe(true)
        expect(matchesResult('Off-White', 'off-white', 'Positive/Negative')).toBe(true)
        expect(matchesResult('10', '5', 'Positive/Negative')).toBe(false) // Different values should fail
      })
    })

    describe('Less than specifications', () => {
      it('returns true when result is below spec', () => {
        expect(matchesResult('5', '< 10', null)).toBe(true)
        expect(matchesResult('0', '< 10', null)).toBe(true)
        expect(matchesResult('9.9', '< 10', null)).toBe(true)
      })

      it('returns false when result equals or exceeds spec', () => {
        expect(matchesResult('10', '< 10', null)).toBe(false)
        expect(matchesResult('15', '< 10', null)).toBe(false)
      })

      it('returns true when both result and spec are less than', () => {
        expect(matchesResult('< 5', '< 10', null)).toBe(true)
        expect(matchesResult('<0.1', '<1', null)).toBe(true)
      })
    })

    describe('Greater than specifications', () => {
      it('returns true when result exceeds spec', () => {
        expect(matchesResult('15', '> 10', null)).toBe(true)
        expect(matchesResult('10.1', '> 10', null)).toBe(true)
      })

      it('returns false when result equals or is below spec', () => {
        expect(matchesResult('10', '> 10', null)).toBe(false)
        expect(matchesResult('5', '> 10', null)).toBe(false)
      })

      it('returns true when both result and spec are greater than', () => {
        expect(matchesResult('> 15', '> 10', null)).toBe(true)
      })
    })

    describe('Range specifications', () => {
      it('returns true when result is within range', () => {
        expect(matchesResult('5', '5-10', null)).toBe(true)
        expect(matchesResult('7', '5-10', null)).toBe(true)
        expect(matchesResult('10', '5-10', null)).toBe(true)
      })

      it('returns false when result is outside range', () => {
        expect(matchesResult('4', '5-10', null)).toBe(false)
        expect(matchesResult('11', '5-10', null)).toBe(false)
      })

      it('handles decimal ranges', () => {
        expect(matchesResult('0.5', '0.1-1.0', null)).toBe(true)
        expect(matchesResult('0.05', '0.1-1.0', null)).toBe(false)
      })
    })

    describe('Exact match specifications', () => {
      it('returns true for exact match', () => {
        expect(matchesResult('Pass', 'Pass', null)).toBe(true)
        expect(matchesResult('pass', 'Pass', null)).toBe(true)
      })

      it('returns false for non-match', () => {
        expect(matchesResult('Fail', 'Pass', null)).toBe(false)
      })
    })

    describe('Edge cases', () => {
      it('returns false for null or empty result', () => {
        expect(matchesResult(null, '< 10', null)).toBe(false)
        expect(matchesResult('', '< 10', null)).toBe(false)
        expect(matchesResult('   ', '< 10', null)).toBe(false)
      })

      it('handles whitespace in values', () => {
        expect(matchesResult('  5  ', '< 10', null)).toBe(true)
        expect(matchesResult(' Negative ', 'Negative', 'Positive/Negative')).toBe(true)
      })

      it('returns false for invalid numeric spec', () => {
        expect(matchesResult('5', '< abc', null)).toBe(false)
      })
    })
  })

  describe('getInputTypeForSpec', () => {
    it('returns dropdown for Positive/Negative unit', () => {
      expect(getInputTypeForSpec('Negative', 'Positive/Negative')).toBe('dropdown')
      expect(getInputTypeForSpec('Positive', 'Positive/Negative')).toBe('dropdown')
    })

    it('returns number for less than specs', () => {
      expect(getInputTypeForSpec('< 10', null)).toBe('number')
      expect(getInputTypeForSpec('<100', null)).toBe('number')
    })

    it('returns number for greater than specs', () => {
      expect(getInputTypeForSpec('> 10', null)).toBe('number')
      expect(getInputTypeForSpec('>0.5', null)).toBe('number')
    })

    it('returns number for range specs', () => {
      expect(getInputTypeForSpec('5-10', null)).toBe('number')
      expect(getInputTypeForSpec('0.1-1.0', null)).toBe('number')
    })

    it('returns text for other specs', () => {
      expect(getInputTypeForSpec('Pass', null)).toBe('text')
      expect(getInputTypeForSpec('Conforms', null)).toBe('text')
    })

    it('handles specs starting with negative numbers', () => {
      expect(getInputTypeForSpec('-10', null)).toBe('text')
    })
  })

  describe('calculatePassFail', () => {
    it('returns pass for valid results', () => {
      expect(calculatePassFail('5', '< 10', null)).toBe('pass')
      expect(calculatePassFail('Negative', 'Negative', 'Positive/Negative')).toBe('pass')
      expect(calculatePassFail('7', '5-10', null)).toBe('pass')
    })

    it('returns fail for invalid results', () => {
      expect(calculatePassFail('15', '< 10', null)).toBe('fail')
      expect(calculatePassFail('Positive', 'Negative', 'Positive/Negative')).toBe('fail')
      expect(calculatePassFail('4', '5-10', null)).toBe('fail')
    })

    it('returns null for empty results', () => {
      expect(calculatePassFail(null, '< 10', null)).toBe(null)
      expect(calculatePassFail('', '< 10', null)).toBe(null)
    })

    it('returns null when no specification', () => {
      expect(calculatePassFail('5', null, null)).toBe(null)
    })
  })

  describe('POSITIVE_NEGATIVE_OPTIONS', () => {
    it('has correct options', () => {
      expect(POSITIVE_NEGATIVE_OPTIONS).toHaveLength(3)
      expect(POSITIVE_NEGATIVE_OPTIONS.map(o => o.value)).toEqual(['Negative', 'Positive', 'ND'])
    })
  })

  describe('isNegativeSpec', () => {
    it('returns true for specs starting with "Negative"', () => {
      expect(isNegativeSpec('Negative')).toBe(true)
      expect(isNegativeSpec('Negative in 10g')).toBe(true)
      expect(isNegativeSpec('Negative per 10g')).toBe(true)
      expect(isNegativeSpec('negative')).toBe(true)
      expect(isNegativeSpec('  Negative  ')).toBe(true)
    })

    it('returns false for non-negative specs', () => {
      expect(isNegativeSpec('Positive')).toBe(false)
      expect(isNegativeSpec('< 10')).toBe(false)
      expect(isNegativeSpec('Pass')).toBe(false)
    })
  })

  describe('isPositiveSpec', () => {
    it('returns true for specs starting with "Positive"', () => {
      expect(isPositiveSpec('Positive')).toBe(true)
      expect(isPositiveSpec('Positive in 10g')).toBe(true)
      expect(isPositiveSpec('positive')).toBe(true)
      expect(isPositiveSpec('  Positive  ')).toBe(true)
    })

    it('returns false for non-positive specs', () => {
      expect(isPositiveSpec('Negative')).toBe(false)
      expect(isPositiveSpec('< 10')).toBe(false)
      expect(isPositiveSpec('Pass')).toBe(false)
    })
  })

  describe('matchesResult for specs starting with Negative', () => {
    it('returns true for "Negative in 10g" spec with accepted negative values', () => {
      expect(matchesResult('Negative', 'Negative in 10g', null)).toBe(true)
      expect(matchesResult('negative', 'Negative in 10g', null)).toBe(true)
      expect(matchesResult('ND', 'Negative in 10g', null)).toBe(true)
      expect(matchesResult('Not Detected', 'Negative in 10g', null)).toBe(true)
      expect(matchesResult('BDL', 'Negative in 10g', null)).toBe(true)
    })

    it('returns true for below detection limit values', () => {
      expect(matchesResult('<10', 'Negative in 10g', null)).toBe(true)
      expect(matchesResult('< 5', 'Negative in 10g', null)).toBe(true)
      expect(matchesResult('<0.1', 'Negative in 10g', null)).toBe(true)
    })

    it('returns false for positive values', () => {
      expect(matchesResult('Positive', 'Negative in 10g', null)).toBe(false)
      expect(matchesResult('Detected', 'Negative in 10g', null)).toBe(false)
      expect(matchesResult('100', 'Negative in 10g', null)).toBe(false)
    })
  })

  describe('matchesResult for specs starting with Positive', () => {
    it('returns true for accepted positive values', () => {
      expect(matchesResult('Positive', 'Positive in 10g', null)).toBe(true)
      expect(matchesResult('positive', 'Positive in 10g', null)).toBe(true)
      expect(matchesResult('Detected', 'Positive in 10g', null)).toBe(true)
      expect(matchesResult('Present', 'Positive in 10g', null)).toBe(true)
      expect(matchesResult('+', 'Positive in 10g', null)).toBe(true)
    })

    it('returns false for negative values', () => {
      expect(matchesResult('Negative', 'Positive in 10g', null)).toBe(false)
      expect(matchesResult('ND', 'Positive in 10g', null)).toBe(false)
      expect(matchesResult('Not Detected', 'Positive in 10g', null)).toBe(false)
    })
  })

  describe('getInputTypeForSpec with negative/positive specs', () => {
    it('returns autocomplete for specs starting with Negative', () => {
      expect(getInputTypeForSpec('Negative in 10g', null)).toBe('autocomplete')
      expect(getInputTypeForSpec('Negative per 25g', null)).toBe('autocomplete')
    })

    it('returns autocomplete for specs starting with Positive', () => {
      expect(getInputTypeForSpec('Positive in 10g', null)).toBe('autocomplete')
    })

    it('returns dropdown for Positive/Negative unit (legacy)', () => {
      expect(getInputTypeForSpec('Negative', 'Positive/Negative')).toBe('dropdown')
    })
  })

  describe('getAutocompleteOptions', () => {
    it('returns negative options for negative specs', () => {
      const options = getAutocompleteOptions('Negative in 10g')
      expect(options.length).toBeGreaterThan(0)
      expect(options.filter(o => o.passes)).toHaveLength(4) // Negative, ND, Not Detected, BDL
      expect(options.filter(o => !o.passes)).toHaveLength(2) // Positive, Detected
    })

    it('returns positive options for positive specs', () => {
      const options = getAutocompleteOptions('Positive in 10g')
      expect(options.length).toBeGreaterThan(0)
      expect(options.filter(o => o.passes)).toHaveLength(4) // Positive, Detected, Present, +
      expect(options.filter(o => !o.passes)).toHaveLength(2) // Negative, ND
    })

    it('returns empty array for non-neg/pos specs', () => {
      expect(getAutocompleteOptions('< 10')).toHaveLength(0)
      expect(getAutocompleteOptions('Pass')).toHaveLength(0)
    })
  })

  describe('NEGATIVE_ACCEPTED_VALUES', () => {
    it('contains expected values', () => {
      expect(NEGATIVE_ACCEPTED_VALUES).toContain('negative')
      expect(NEGATIVE_ACCEPTED_VALUES).toContain('nd')
      expect(NEGATIVE_ACCEPTED_VALUES).toContain('not detected')
      expect(NEGATIVE_ACCEPTED_VALUES).toContain('bdl')
    })
  })

  describe('POSITIVE_ACCEPTED_VALUES', () => {
    it('contains expected values', () => {
      expect(POSITIVE_ACCEPTED_VALUES).toContain('positive')
      expect(POSITIVE_ACCEPTED_VALUES).toContain('detected')
      expect(POSITIVE_ACCEPTED_VALUES).toContain('present')
      expect(POSITIVE_ACCEPTED_VALUES).toContain('+')
    })
  })
})
