import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { type OpeningStatus, useOpeningStatus } from '@/lib/hooks/use-opening-status'

function OpeningStatusProbe({ renders }: { renders: Array<OpeningStatus | null> }) {
  const status = useOpeningStatus()
  renders.push(status)

  return <p data-testid="opening-status">{status === null ? 'pending' : String(status.isOpen)}</p>
}

describe('useOpeningStatus', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns null on first render and real status after mount', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-06-08T02:00:00.000Z').getTime())
    const renders: Array<OpeningStatus | null> = []

    render(<OpeningStatusProbe renders={renders} />)

    expect(renders[0]).toBeNull()
    await waitFor(() => expect(screen.getByTestId('opening-status')).toHaveTextContent('true'))
    expect(renders.at(-1)).toEqual({ isOpen: true })
  })
})
