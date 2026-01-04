import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PassFailBadge } from './PassFailBadge'

describe('PassFailBadge', () => {
  describe('when status is null', () => {
    it('renders dash placeholder', () => {
      render(<PassFailBadge status={null} />)
      expect(screen.getByText('—')).toBeInTheDocument()
    })
  })

  describe('when status is pass', () => {
    it('renders PASS text', () => {
      render(<PassFailBadge status="pass" />)
      expect(screen.getByText('PASS')).toBeInTheDocument()
    })

    it('does not render Flagged badge', () => {
      render(<PassFailBadge status="pass" isFlagged={false} />)
      expect(screen.queryByText('Flagged')).not.toBeInTheDocument()
    })
  })

  describe('when status is fail', () => {
    it('renders FAIL text', () => {
      render(<PassFailBadge status="fail" />)
      expect(screen.getByText('FAIL')).toBeInTheDocument()
    })

    it('renders Flagged badge when isFlagged is true', () => {
      render(<PassFailBadge status="fail" isFlagged={true} />)
      expect(screen.getByText('FAIL')).toBeInTheDocument()
      expect(screen.getByText('Flagged')).toBeInTheDocument()
    })

    it('does not render Flagged badge when isFlagged is false', () => {
      render(<PassFailBadge status="fail" isFlagged={false} />)
      expect(screen.getByText('FAIL')).toBeInTheDocument()
      expect(screen.queryByText('Flagged')).not.toBeInTheDocument()
    })
  })

  describe('className prop', () => {
    it('applies custom className', () => {
      const { container } = render(<PassFailBadge status="pass" className="custom-class" />)
      expect(container.firstChild).toHaveClass('custom-class')
    })
  })
})
