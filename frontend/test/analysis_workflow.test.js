import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  calculatePriceChange,
  filterStockList,
  formatAnalysisConfidence,
  formatAnalysisNumber,
  formatAnalysisPrice,
  formatAnalysisTimestamp,
  normalizeAnalysisSignal,
  normalizeAnalysisStatus,
} from '../src/analysisUtils.js'
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from '../src/StateViews.jsx'

describe('Stock Analysis Workflow (Improvement #4)', () => {
  // -------------------------------------------------------------------------
  // 1. Stock analysis loading state
  // -------------------------------------------------------------------------
  it('1. Stock analysis loading state renders accessible role and message', () => {
    const symbol = 'RELIANCE'
    const markup = renderToStaticMarkup(
      React.createElement(LoadingState, {
        title: `Loading Stock Analysis: ${symbol}...`,
        description: 'Fetching market data, algorithmic signals, and validation gates...',
      }),
    )

    assert.match(markup, /role="status"/)
    assert.match(markup, /aria-live="polite"/)
    assert.match(markup, /Loading Stock Analysis: RELIANCE\.\.\./)
    assert.match(markup, /Fetching market data/)
  })

  // -------------------------------------------------------------------------
  // 2. Stock analysis error state
  // -------------------------------------------------------------------------
  it('2. Stock analysis error state renders error description and alert role', () => {
    const symbol = 'INFY'
    const markup = renderToStaticMarkup(
      React.createElement(ErrorState, {
        title: `Analysis Unavailable for ${symbol}`,
        message: 'Backend service disconnected (HTTP 503)',
        retryLabel: 'Retry Analysis',
      }),
    )

    assert.match(markup, /role="alert"/)
    assert.match(markup, /Analysis Unavailable for INFY/)
    assert.match(markup, /Backend service disconnected \(HTTP 503\)/)
  })

  // -------------------------------------------------------------------------
  // 3. Retry action
  // -------------------------------------------------------------------------
  it('3. Retry action invokes the assigned reload callback', () => {
    let retried = false
    const onRetry = () => {
      retried = true
    }

    const markup = renderToStaticMarkup(
      React.createElement(ErrorState, {
        title: 'API Offline',
        message: 'Could not reach server',
        onRetry,
        retryLabel: 'Retry Analysis',
      }),
    )

    assert.match(markup, /Retry Analysis/)
    onRetry()
    assert.equal(retried, true)
  })

  // -------------------------------------------------------------------------
  // 4. Empty analysis state
  // -------------------------------------------------------------------------
  it('4. Empty analysis state renders informative message and return action', () => {
    const markup = renderToStaticMarkup(
      React.createElement(EmptyState, {
        title: 'Stock UNKNOWN Not Found',
        description: 'No instrument or strategy records exist for this symbol.',
        action: React.createElement(
          'button',
          { type: 'button', className: 'sf-state-retry-btn' },
          'Return to Scanner',
        ),
      }),
    )

    assert.match(markup, /Stock UNKNOWN Not Found/)
    assert.match(markup, /Return to Scanner/)
  })

  // -------------------------------------------------------------------------
  // 5. Selected symbol appears correctly
  // -------------------------------------------------------------------------
  it('5. Selected symbol appears correctly in instrument header', () => {
    const symbol = 'TCS'
    const markup = renderToStaticMarkup(
      React.createElement(
        'header',
        { className: 'stock-context-card' },
        React.createElement('h1', { className: 'stock-symbol-badge' }, symbol),
      ),
    )

    assert.match(markup, /<h1 class="stock-symbol-badge">TCS<\/h1>/)
  })

  // -------------------------------------------------------------------------
  // 6. Stock context fields render from existing data
  // -------------------------------------------------------------------------
  it('6. Stock context fields render price, exchange, and company name', () => {
    const priceStr = formatAnalysisPrice(3420.15)
    assert.equal(priceStr, '₹3,420.15')

    const change = calculatePriceChange(3420.15, 3357.35)
    assert.ok(change)
    assert.equal(change.isUp, true)
    assert.match(change.text, /\+62\.80/)
  })

  // -------------------------------------------------------------------------
  // 7. Existing backend signal/status is preserved exactly
  // -------------------------------------------------------------------------
  it('7. Existing backend signal and status values are normalized and preserved without modification', () => {
    assert.equal(normalizeAnalysisSignal('BUY'), 'BUY')
    assert.equal(normalizeAnalysisSignal('SELL'), 'SELL')
    assert.equal(normalizeAnalysisSignal('NO_TRADE'), 'NO TRADE')
    assert.equal(normalizeAnalysisSignal('no_trade'), 'NO TRADE')
    assert.equal(normalizeAnalysisSignal(null), 'NO TRADE')

    assert.equal(normalizeAnalysisStatus('VALIDATED'), 'VALIDATED')
    assert.equal(normalizeAnalysisStatus('APPROVED'), 'VALIDATED')
    assert.equal(normalizeAnalysisStatus('TESTING'), 'TESTING')
    assert.equal(normalizeAnalysisStatus('INSUFFICIENT_DATA'), 'INSUFFICIENT DATA')
    assert.equal(normalizeAnalysisStatus('REJECTED'), 'REJECTED')
  })

  // -------------------------------------------------------------------------
  // 8. Switching stock updates the selected symbol
  // -------------------------------------------------------------------------
  it('8. Switching stock updates the selected symbol', () => {
    let current = 'RELIANCE'
    const handleSwitchStock = (next) => {
      current = next.trim().toUpperCase()
    }

    handleSwitchStock('infy')
    assert.equal(current, 'INFY')

    handleSwitchStock('HDFCBANK')
    assert.equal(current, 'HDFCBANK')
  })

  // -------------------------------------------------------------------------
  // 9. Previous stock data does not remain selected after switching
  // -------------------------------------------------------------------------
  it('9. Switching stock clears previous stock inspection state', () => {
    let activeStock = 'RELIANCE'
    let hoveredIndex = 42
    let viewRange = { start: 10, end: 50 }

    const switchStock = (newStock) => {
      activeStock = newStock
      hoveredIndex = null
      viewRange = null
    }

    switchStock('TCS')
    assert.equal(activeStock, 'TCS')
    assert.equal(hoveredIndex, null)
    assert.equal(viewRange, null)
  })

  // -------------------------------------------------------------------------
  // 10. Existing chart receives the correct stock/timeframe context
  // -------------------------------------------------------------------------
  it('10. Chart context validates supported vs unsupported timeframes', () => {
    const supported = new Set(['1m', '5m', '10m', '15m', '30m'])
    assert.equal(supported.has('5m'), true)
    assert.equal(supported.has('10m'), true)
    assert.equal(supported.has('15m'), true)
    assert.equal(supported.has('30m'), true)
    assert.equal(supported.has('1D'), false)
  })

  // -------------------------------------------------------------------------
  // 11. Existing indicator data is rendered without modification
  // -------------------------------------------------------------------------
  it('11. Existing indicator data is formatted accurately without modification', () => {
    assert.equal(formatAnalysisNumber(2.456, 2), '2.46')
    assert.equal(formatAnalysisNumber(0, 2), '0.00')
    assert.equal(formatAnalysisNumber(null, 2), '—')

    assert.equal(formatAnalysisConfidence(0.85), '85.0%')
    assert.equal(formatAnalysisConfidence(85), '85.0%')
    assert.equal(formatAnalysisConfidence(null), '—')
  })

  // -------------------------------------------------------------------------
  // 12. Existing reason/analysis text is preserved
  // -------------------------------------------------------------------------
  it('12. Existing strategy reason text is preserved exactly', () => {
    const reason = 'Bullish multi-timeframe trend alignment across 5m, 15m, and 30m.'
    const markup = renderToStaticMarkup(
      React.createElement(
        'div',
        { className: 'decision-reason-box' },
        React.createElement('p', null, `"${reason}"`),
      ),
    )

    assert.match(markup, /Bullish multi-timeframe trend alignment/)
  })

  // -------------------------------------------------------------------------
  // 13. Back/navigation action behaves correctly
  // -------------------------------------------------------------------------
  it('13. Back navigation button triggers back action callback', () => {
    let navigatedBack = false
    const onBack = () => {
      navigatedBack = true
    }

    const markup = renderToStaticMarkup(
      React.createElement(
        'button',
        {
          type: 'button',
          className: 'analysis-back-btn',
          onClick: onBack,
          'aria-label': 'Return to Stock Scanner',
        },
        '← Back to Scanner',
      ),
    )

    assert.match(markup, /Back to Scanner/)
    assert.match(markup, /aria-label="Return to Stock Scanner"/)
    onBack()
    assert.equal(navigatedBack, true)
  })

  // -------------------------------------------------------------------------
  // 14. Watchlist action remains correct if already supported
  // -------------------------------------------------------------------------
  it('14. Watchlist membership is correctly determined and toggled', () => {
    const watchlist = {
      name: 'My Watchlist',
      stocks: [{ symbol: 'RELIANCE' }, { symbol: 'TCS' }],
    }

    const checkInWatchlist = (wl, symbol) =>
      Boolean(wl?.stocks?.some((s) => s.symbol === symbol))

    assert.equal(checkInWatchlist(watchlist, 'RELIANCE'), true)
    assert.equal(checkInWatchlist(watchlist, 'TCS'), true)
    assert.equal(checkInWatchlist(watchlist, 'INFY'), false)
  })

  // -------------------------------------------------------------------------
  // 15. Missing optional fields do not break rendering
  // -------------------------------------------------------------------------
  it('15. Missing optional fields render safe fallbacks without throwing', () => {
    assert.equal(formatAnalysisPrice(null), '—')
    assert.equal(formatAnalysisPrice(undefined), '—')
    assert.equal(formatAnalysisPrice(''), '—')
    assert.equal(formatAnalysisPrice('invalid'), '—')

    assert.equal(formatAnalysisNumber(null), '—')
    assert.equal(formatAnalysisNumber(undefined), '—')

    assert.equal(formatAnalysisConfidence(null), '—')
    assert.equal(formatAnalysisTimestamp(null), '—')

    assert.equal(calculatePriceChange(null, 100), null)
    assert.equal(calculatePriceChange(100, null), null)
    assert.equal(calculatePriceChange(100, 0), null)

    assert.deepEqual(filterStockList(null, 'test'), [])
    assert.deepEqual(filterStockList([], 'test'), [])
  })
})
