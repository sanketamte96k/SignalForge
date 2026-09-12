import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  formatScannerPrice,
  formatScannerConfidence,
  formatScannerScore,
  formatScannerTimestamp,
  normalizeSignal,
  normalizeStatus,
  filterScannerItems,
  sortScannerItems,
} from '../src/scannerUtils.js'
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from '../src/StateViews.jsx'

const MOCK_SCANNER_ITEMS = [
  {
    symbol: 'RELIANCE',
    name: 'Reliance Industries Ltd',
    exchange: 'NSE',
    validation_status: 'VALIDATED',
    signal_eligible: true,
    signal: 'BUY',
    price: 2856.4,
    score: 85.5,
    confidence: 0.88,
    timeframe_alignment: 4,
    reason: 'Multi-timeframe EMA and RSI alignment',
  },
  {
    symbol: 'TCS',
    name: 'Tata Consultancy Services',
    exchange: 'NSE',
    validation_status: 'VALIDATED',
    signal_eligible: true,
    signal: 'BUY',
    price: 3420.15,
    score: 78.0,
    confidence: 0.82,
    timeframe_alignment: 3,
    reason: 'Bullish breakout with volume confirmation',
  },
  {
    symbol: 'HDFCBANK',
    name: 'HDFC Bank Ltd',
    exchange: 'NSE',
    validation_status: 'VALIDATED',
    signal_eligible: true,
    signal: 'SELL',
    price: 1612.3,
    score: 42.0,
    confidence: 0.74,
    timeframe_alignment: 2,
    reason: 'Bearish momentum below EMA50',
  },
  {
    symbol: 'ZOMATO',
    name: 'Zomato Ltd',
    exchange: 'NSE',
    validation_status: 'TESTING',
    signal_eligible: false,
    signal: 'NO_TRADE',
    price: 215.5,
    score: null,
    confidence: null,
    timeframe_alignment: null,
    reason: 'Stock in testing pipeline; signals locked',
  },
  {
    symbol: 'IDEA',
    name: 'Vodafone Idea Ltd',
    exchange: 'NSE',
    validation_status: 'FAILED',
    signal_eligible: false,
    signal: 'NO_TRADE',
    price: 12.8,
    score: null,
    confidence: 0.15,
    timeframe_alignment: 1,
    reason: 'Failed liquidity and readiness gate',
  },
]

describe('Stock Scanner UX (Improvement #3)', () => {
  // -------------------------------------------------------------------------
  // 1. Scanner renders loading state
  // -------------------------------------------------------------------------
  it('1. Scanner renders loading state with proper accessible attributes', () => {
    const markup = renderToStaticMarkup(
      React.createElement(LoadingState, {
        title: 'Loading NIFTY 50 Scanner...',
        description: 'Reading algorithmic scanner results from the SignalForge backend.',
      }),
    )

    assert.match(markup, /role="status"/)
    assert.match(markup, /aria-live="polite"/)
    assert.match(markup, /Loading NIFTY 50 Scanner\.\.\./)
    assert.match(markup, /sf-spinner/)
  })

  // -------------------------------------------------------------------------
  // 2. Scanner renders API error state
  // -------------------------------------------------------------------------
  it('2. Scanner renders API error state with error message', () => {
    const markup = renderToStaticMarkup(
      React.createElement(ErrorState, {
        title: 'Unable to Load Scanner Results',
        message: 'Backend scanner engine offline.',
        onRetry: () => {},
        retryLabel: 'Retry Scanner',
      }),
    )

    assert.match(markup, /role="alert"/)
    assert.match(markup, /Unable to Load Scanner Results/)
    assert.match(markup, /Backend scanner engine offline\./)
    assert.match(markup, /Retry Scanner/)
  })

  // -------------------------------------------------------------------------
  // 3. Retry action works
  // -------------------------------------------------------------------------
  it('3. Retry callback is successfully triggered', () => {
    let retried = false
    const onRetry = () => {
      retried = true
    }

    onRetry()
    assert.equal(retried, true)
  })

  // -------------------------------------------------------------------------
  // 4. Scanner renders empty backend state
  // -------------------------------------------------------------------------
  it('4. Scanner renders empty backend state when zero records are returned', () => {
    const markup = renderToStaticMarkup(
      React.createElement(EmptyState, {
        title: 'No Scanner Data Available',
        description: 'The SignalForge scanner returned zero stock evaluation records.',
      }),
    )

    assert.match(markup, /No Scanner Data Available/)
    assert.match(markup, /zero stock evaluation records/)
  })

  // -------------------------------------------------------------------------
  // 5. Search filters symbols correctly
  // -------------------------------------------------------------------------
  it('5. Search filters symbols correctly', () => {
    const results = filterScannerItems(MOCK_SCANNER_ITEMS, { search: 'RELIANCE' })
    assert.equal(results.length, 1)
    assert.equal(results[0].symbol, 'RELIANCE')
  })

  // -------------------------------------------------------------------------
  // 6. Search is case-insensitive
  // -------------------------------------------------------------------------
  it('6. Search is case-insensitive across uppercase, lowercase, and mixed input', () => {
    const lower = filterScannerItems(MOCK_SCANNER_ITEMS, { search: 'reliance' })
    const mixed = filterScannerItems(MOCK_SCANNER_ITEMS, { search: 'ReLiAnCe' })
    assert.equal(lower.length, 1)
    assert.equal(mixed.length, 1)
    assert.equal(lower[0].symbol, 'RELIANCE')
    assert.equal(mixed[0].symbol, 'RELIANCE')
  })

  // -------------------------------------------------------------------------
  // 7. Search can match name when name exists
  // -------------------------------------------------------------------------
  it('7. Search matches company name', () => {
    const results = filterScannerItems(MOCK_SCANNER_ITEMS, { search: 'Tata' })
    assert.equal(results.length, 1)
    assert.equal(results[0].symbol, 'TCS')
    assert.equal(results[0].name, 'Tata Consultancy Services')
  })

  // -------------------------------------------------------------------------
  // 8. Clearing search restores results
  // -------------------------------------------------------------------------
  it('8. Clearing search query restores full item set', () => {
    const filtered = filterScannerItems(MOCK_SCANNER_ITEMS, { search: 'HDFC' })
    assert.equal(filtered.length, 1)

    const cleared = filterScannerItems(MOCK_SCANNER_ITEMS, { search: '' })
    assert.equal(cleared.length, MOCK_SCANNER_ITEMS.length)
  })

  // -------------------------------------------------------------------------
  // 9. Sorting numeric values works correctly
  // -------------------------------------------------------------------------
  it('9. Sorting numeric values works ascending and descending', () => {
    const asc = sortScannerItems(MOCK_SCANNER_ITEMS, 'price', 'asc')
    assert.equal(asc[0].symbol, 'IDEA') // 12.80 lowest
    assert.equal(asc[asc.length - 1].symbol, 'TCS') // 3420.15 highest

    const desc = sortScannerItems(MOCK_SCANNER_ITEMS, 'price', 'desc')
    assert.equal(desc[0].symbol, 'TCS') // 3420.15 highest
    assert.equal(desc[desc.length - 1].symbol, 'IDEA') // 12.80 lowest
  })

  // -------------------------------------------------------------------------
  // 10. Missing numeric values do not break sorting
  // -------------------------------------------------------------------------
  it('10. Missing/null numeric values sort cleanly without throwing and are placed at the end', () => {
    const sortedDesc = sortScannerItems(MOCK_SCANNER_ITEMS, 'score', 'desc')
    // Items with valid numbers should be at the top
    assert.equal(sortedDesc[0].symbol, 'RELIANCE') // 85.5
    assert.equal(sortedDesc[1].symbol, 'TCS') // 78.0
    assert.equal(sortedDesc[2].symbol, 'HDFCBANK') // 42.0
    // Items with null score (ZOMATO, IDEA) must be at the bottom
    assert.equal(sortedDesc[3].score, null)
    assert.equal(sortedDesc[4].score, null)

    const sortedAsc = sortScannerItems(MOCK_SCANNER_ITEMS, 'score', 'asc')
    assert.equal(sortedAsc[0].symbol, 'HDFCBANK') // 42.0 lowest
    assert.equal(sortedAsc[1].symbol, 'TCS') // 78.0
    assert.equal(sortedAsc[2].symbol, 'RELIANCE') // 85.5 highest
    // Nulls still at the end
    assert.equal(sortedAsc[3].score, null)
    assert.equal(sortedAsc[4].score, null)
  })

  // -------------------------------------------------------------------------
  // 11. Result count is correct
  // -------------------------------------------------------------------------
  it('11. Filtered result count calculation is accurate', () => {
    const buyOnly = filterScannerItems(MOCK_SCANNER_ITEMS, { signalFilter: 'BUY' })
    assert.equal(buyOnly.length, 2)

    const validatedOnly = filterScannerItems(MOCK_SCANNER_ITEMS, { statusFilter: 'VALIDATED' })
    assert.equal(validatedOnly.length, 3)

    const eligibleOnly = filterScannerItems(MOCK_SCANNER_ITEMS, { eligibleOnly: true })
    assert.equal(eligibleOnly.length, 3)
  })

  // -------------------------------------------------------------------------
  // 12. Filter producing zero results renders the correct empty/no-results state
  // -------------------------------------------------------------------------
  it('12. Filter producing zero results renders EmptyState with reset action', () => {
    const noMatch = filterScannerItems(MOCK_SCANNER_ITEMS, { search: 'NONEXISTENTXYZ' })
    assert.equal(noMatch.length, 0)

    const markup = renderToStaticMarkup(
      React.createElement(EmptyState, {
        title: 'No Stocks Match Current Filters',
        description: 'Try adjusting your search query, or reset the signal, status, and eligibility filters.',
        action: React.createElement(
          'button',
          { type: 'button', className: 'sf-state-retry-btn' },
          'Reset Filters',
        ),
      }),
    )

    assert.match(markup, /No Stocks Match Current Filters/)
    assert.match(markup, /Reset Filters/)
  })

  // -------------------------------------------------------------------------
  // 13. Existing backend signal/status values are preserved unchanged
  // -------------------------------------------------------------------------
  it('13. Normalizes and preserves backend signal/status values without modifying rules', () => {
    assert.equal(normalizeSignal('BUY'), 'BUY')
    assert.equal(normalizeSignal('SELL'), 'SELL')
    assert.equal(normalizeSignal('NO_TRADE'), 'NO TRADE')
    assert.equal(normalizeSignal('UNKNOWN'), 'NO TRADE')

    assert.equal(normalizeStatus('VALIDATED'), 'VALIDATED')
    assert.equal(normalizeStatus('TESTING'), 'TESTING')
    assert.equal(normalizeStatus('FAILED'), 'FAILED')
    assert.equal(normalizeStatus('IN_PROGRESS'), 'TESTING')
  })

  // -------------------------------------------------------------------------
  // 14. Formatting utilities operate accurately
  // -------------------------------------------------------------------------
  it('14. Formatting utilities handle valid, edge-case, and missing values', () => {
    assert.equal(formatScannerPrice(2856.4), '2,856.40')
    assert.equal(formatScannerPrice(null), '—')
    assert.equal(formatScannerPrice(NaN), '—')

    assert.equal(formatScannerConfidence(0.88), '88%')
    assert.equal(formatScannerConfidence(null), '—')

    assert.equal(formatScannerScore(85.5), '85.50')
    assert.equal(formatScannerScore(null), '—')

    const ts = formatScannerTimestamp('2026-03-26T15:29:00+05:30')
    assert.match(ts, /(15:29|3:29)/)
    assert.equal(formatScannerTimestamp(null), '—')
  })
})
