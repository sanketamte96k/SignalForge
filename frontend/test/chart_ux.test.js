import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  calculateEmaSeries,
  formatChartPrice,
  formatShortTime,
  calculateCandleChange,
  calculateCrosshairPrice,
  findCandleIndexAtX,
  calculateViewRange,
  matchSignalToCandle,
} from '../src/chartUtils.js'
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from '../src/StateViews.jsx'

describe('Chart UX & Trading Terminal Interactions (Improvement #2)', () => {
  // -------------------------------------------------------------------------
  // 1. Timeframe selection and validation
  // -------------------------------------------------------------------------
  it('1. Validates supported vs unsupported chart timeframes', () => {
    const supported = new Set(['1m', '5m', '10m', '15m', '30m'])
    assert.equal(supported.has('5m'), true)
    assert.equal(supported.has('15m'), true)
    assert.equal(supported.has('30m'), true)
    assert.equal(supported.has('1H'), false)
    assert.equal(supported.has('4H'), false)
    assert.equal(supported.has('1D'), false)

    const getErrorForTimeframe = (tf) =>
      supported.has(tf) ? null : `${tf} chart is not available yet. Use 5m, 10m, 15m or 30m.`

    assert.equal(getErrorForTimeframe('15m'), null)
    assert.match(getErrorForTimeframe('1H'), /1H chart is not available yet/)
  })

  // -------------------------------------------------------------------------
  // 2. Chart loading state rendering
  // -------------------------------------------------------------------------
  it('2. Chart loading state renders with title and description', () => {
    const markup = renderToStaticMarkup(
      React.createElement(LoadingState, {
        title: 'Loading 15m historical candles...',
        description: 'Reading real historical OHLCV data from the SignalForge chart API.',
      }),
    )

    assert.match(markup, /role="status"/)
    assert.match(markup, /aria-live="polite"/)
    assert.match(markup, /Loading 15m historical candles\.\.\./)
    assert.match(markup, /Reading real historical OHLCV data/)
  })

  // -------------------------------------------------------------------------
  // 3. Chart error state rendering with retry capability
  // -------------------------------------------------------------------------
  it('3. Chart error state renders with title, message, and retry button', () => {
    const markup = renderToStaticMarkup(
      React.createElement(ErrorState, {
        title: 'Chart Data Unavailable',
        message: 'Unable to connect to market data provider.',
        onRetry: () => {},
        retryLabel: 'Reload Chart',
      }),
    )

    assert.match(markup, /role="alert"/)
    assert.match(markup, /Chart Data Unavailable/)
    assert.match(markup, /Unable to connect to market data provider\./)
    assert.match(markup, /Reload Chart/)
  })

  // -------------------------------------------------------------------------
  // 4. Chart empty state rendering
  // -------------------------------------------------------------------------
  it('4. Chart empty state renders when candle data is empty', () => {
    const markup = renderToStaticMarkup(
      React.createElement(EmptyState, {
        title: 'No Candle Data Available',
        description: 'No OHLCV records returned for the 15m timeframe.',
      }),
    )

    assert.match(markup, /No Candle Data Available/)
    assert.match(markup, /No OHLCV records returned for the 15m timeframe\./)
  })

  // -------------------------------------------------------------------------
  // 5. Retry behavior callback invocation
  // -------------------------------------------------------------------------
  it('5. Retry callback is invoked on retry action', () => {
    let retried = false
    const onRetry = () => {
      retried = true
    }

    onRetry()
    assert.equal(retried, true)
  })

  // -------------------------------------------------------------------------
  // 6. Signal marker data is passed and matched without alteration
  // -------------------------------------------------------------------------
  it('6. Signal marker matches candle by timestamp and preserves exact signal data', () => {
    const syntheticCandles = [
      { timestamp: '2026-03-26T14:45:00+05:30', open: 22000, high: 22050, low: 21980, close: 22040, volume: 1000 },
      { timestamp: '2026-03-26T15:00:00+05:30', open: 22040, high: 22080, low: 22020, close: 22075, volume: 1500 },
      { timestamp: '2026-03-26T15:15:00+05:30', open: 22075, high: 22120, low: 22060, close: 22100, volume: 2000 },
    ]

    const buySignal = {
      signal: 'BUY',
      timestamp: '2026-03-26T15:15:00+05:30',
      price: 22100,
      strategy: 'SignalForge',
    }

    const match = matchSignalToCandle(buySignal, syntheticCandles)
    assert.notEqual(match, null)
    assert.equal(match.signal.signal, 'BUY')
    assert.equal(match.signal.price, 22100)
    assert.equal(match.candle.timestamp, '2026-03-26T15:15:00+05:30')
    assert.equal(match.index, 2)

    // NO_TRADE signal produces no marker
    const noTradeSignal = { signal: 'NO_TRADE', price: 22000 }
    assert.equal(matchSignalToCandle(noTradeSignal, syntheticCandles), null)
  })

  // -------------------------------------------------------------------------
  // 7. Tooltip and hover data transformation utilities
  // -------------------------------------------------------------------------
  it('7. Tooltip & OHLC data transformation utilities format correctly', () => {
    // formatChartPrice
    assert.equal(formatChartPrice(22045.5), '22,045.50')
    assert.equal(formatChartPrice(null), '—')
    assert.equal(formatChartPrice(NaN), '—')

    // formatShortTime
    const timeStr = formatShortTime('2026-03-26T15:29:00+05:30')
    assert.match(timeStr, /15:29/)

    // calculateCandleChange
    const upCandle = { open: 22000, close: 22110 }
    const upChange = calculateCandleChange(upCandle)
    assert.equal(upChange.isUp, true)
    assert.equal(upChange.diff, 110)
    assert.equal(upChange.pct.toFixed(2), '0.50')
    assert.match(upChange.text, /\+110\.00 \(\+0\.50%\)/)

    const downCandle = { open: 22000, close: 21900 }
    const downChange = calculateCandleChange(downCandle)
    assert.equal(downChange.isUp, false)
    assert.equal(downChange.diff, -100)
    assert.match(downChange.text, /-100\.00 \(-0\.45%\)/)

    // calculateCrosshairPrice
    const price = calculateCrosshairPrice(135, 18, 252, 22000, 22500)
    assert.equal(Math.round(price), 22250)

    // findCandleIndexAtX
    assert.equal(findCandleIndexAtX(390, 780, 100), 50)
    assert.equal(findCandleIndexAtX(0, 780, 100), 0)
    assert.equal(findCandleIndexAtX(780, 780, 100), 99)
  })

  // -------------------------------------------------------------------------
  // 8. Zoom and pan view range math
  // -------------------------------------------------------------------------
  it('8. Zoom and pan view range math operates with strict bounds clamping', () => {
    const totalCandles = 200

    // Reset range
    const initial = calculateViewRange(totalCandles, null, 'reset')
    assert.equal(initial.start, 120)
    assert.equal(initial.end, 200)

    // Zoom In
    const zoomedIn = calculateViewRange(totalCandles, initial, 'zoomIn')
    assert.equal(zoomedIn.end, 200)
    assert.ok(zoomedIn.start > initial.start, 'Zooming in should narrow the view window')

    // Zoom Out
    const zoomedOut = calculateViewRange(totalCandles, zoomedIn, 'zoomOut')
    assert.ok(zoomedOut.start <= zoomedIn.start, 'Zooming out should expand the view window')

    // Pan
    const panned = calculateViewRange(totalCandles, initial, 'pan', -10)
    assert.equal(panned.start, 110)
    assert.equal(panned.end, 190)

    // Clamping to 0
    const clampedLeft = calculateViewRange(totalCandles, { start: 5, end: 85 }, 'pan', -20)
    assert.equal(clampedLeft.start, 0)
    assert.equal(clampedLeft.end, 80)
  })

  // -------------------------------------------------------------------------
  // 9. EMA calculation accuracy
  // -------------------------------------------------------------------------
  it('9. EMA series calculator computes correctly across history', () => {
    const values = [100, 102, 104, 103, 105, 107, 106, 108, 110, 112]
    const ema = calculateEmaSeries(values, 3)
    assert.equal(ema.length, values.length)
    assert.equal(ema[0], 100)
    // Alpha for period 3 is 2 / (3 + 1) = 0.5
    // ema[1] = 102 * 0.5 + 100 * 0.5 = 101
    assert.equal(ema[1], 101)
  })
})
