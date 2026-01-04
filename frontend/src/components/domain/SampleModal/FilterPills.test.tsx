import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FilterPills } from './FilterPills'

describe('FilterPills', () => {
  const defaultCounts = {
    all: 10,
    pending: 5,
    passed: 3,
    failed: 2,
  }

  it('renders all filter options', () => {
    const onChange = vi.fn()
    render(<FilterPills filter="all" counts={defaultCounts} onChange={onChange} />)

    expect(screen.getByText(/All/)).toBeInTheDocument()
    expect(screen.getByText(/Pending/)).toBeInTheDocument()
    expect(screen.getByText(/Passed/)).toBeInTheDocument()
    expect(screen.getByText(/Failed/)).toBeInTheDocument()
  })

  it('displays counts for each filter', () => {
    const onChange = vi.fn()
    render(<FilterPills filter="all" counts={defaultCounts} onChange={onChange} />)

    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('highlights the active filter', () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <FilterPills filter="all" counts={defaultCounts} onChange={onChange} />
    )

    // Get the "All" button and check its classes
    const allButton = screen.getByRole('button', { name: /All/ })
    expect(allButton).toHaveClass('bg-slate-900')

    // Change to pending filter
    rerender(<FilterPills filter="pending" counts={defaultCounts} onChange={onChange} />)
    const pendingButton = screen.getByRole('button', { name: /Pending/ })
    expect(pendingButton).toHaveClass('bg-slate-900')
  })

  it('calls onChange when filter is clicked', () => {
    const onChange = vi.fn()
    render(<FilterPills filter="all" counts={defaultCounts} onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: /Pending/ }))
    expect(onChange).toHaveBeenCalledWith('pending')

    fireEvent.click(screen.getByRole('button', { name: /Passed/ }))
    expect(onChange).toHaveBeenCalledWith('passed')

    fireEvent.click(screen.getByRole('button', { name: /Failed/ }))
    expect(onChange).toHaveBeenCalledWith('failed')
  })

  it('applies custom className', () => {
    const onChange = vi.fn()
    const { container } = render(
      <FilterPills filter="all" counts={defaultCounts} onChange={onChange} className="custom-class" />
    )

    expect(container.firstChild).toHaveClass('custom-class')
  })

  it('handles zero counts', () => {
    const onChange = vi.fn()
    const zeroCounts = { all: 0, pending: 0, passed: 0, failed: 0 }
    render(<FilterPills filter="all" counts={zeroCounts} onChange={onChange} />)

    const zeroElements = screen.getAllByText('0')
    expect(zeroElements).toHaveLength(4)
  })
})
