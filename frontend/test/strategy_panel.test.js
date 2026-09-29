import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { StrategySignalPanel } from '../src/StrategySignalPanel.jsx'

describe('Strategy Signal Panel (Phase 16 Frontend Integration)', () => {
  // -------------------------------------------------------------------------
  // 1. Strategy panel renders BUY
  // -------------------------------------------------------------------------
  it('1. Strategy panel renders BUY with execution brackets and confirmations', () => {
    const buyData = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      timestamp: '2024-03-26T15:15:00+05:30',
      signal: 'BUY',
      signal_reason: '4/4 timeframes aligned LONG. Momentum confirmed.',
      entry_price: 22040.0,
      stop_loss: 22002.5,
      target_1: 22096.25,
      target_2: 22115.0,
      confidence: 85.0,
      indicators: {
        ema_fast: 22010.0,
        ema_slow: 21980.0,
        rsi: 65.0,
        atr: 25.0,
        volume: null,
        vwap: null,
      },
      confirmation: {
        ema: true,
        rsi_momentum: true,
        volume: null,
        multi_timeframe: true,
      },
      status: 'HISTORICAL',
      price: 22040.0,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: buyData,
        activeTimeframe: '15m',
      }),
    )

    // Signal status
    assert.match(markup, /BUY/)
    assert.match(markup, /BUY SIGNAL FROM STRATEGY ENGINE/)
    assert.match(markup, /signal-dominant-box buy/)

    // Price & metrics
    assert.match(markup, /22,040\.00/)
    assert.match(markup, /4\/4 timeframes aligned LONG/)
    assert.match(markup, /85%/)

    // Execution targets
    assert.match(markup, /22,002\.50/)
    assert.match(markup, /22,096\.25/)
    assert.match(markup, /22,115\.00/)

    // Confirmations
    assert.match(markup, /Confirmed/)
    assert.match(markup, /EMA20: 22,010\.00 • EMA50: 21,980\.00/)
    assert.match(markup, /RSI\(14\): 65\.00/)
  })

  // -------------------------------------------------------------------------
  // 2. Strategy panel renders SELL
  // -------------------------------------------------------------------------
  it('2. Strategy panel renders SELL with execution brackets and confirmations', () => {
    const sellData = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      timestamp: '2024-03-26T15:15:00+05:30',
      signal: 'SELL',
      signal_reason: '4/4 timeframes aligned SHORT. Momentum confirmed.',
      entry_price: 21960.0,
      stop_loss: 21990.0,
      target_1: 21915.0,
      target_2: 21900.0,
      confidence: 80.0,
      indicators: {
        ema_fast: 21980.0,
        ema_slow: 22010.0,
        rsi: 38.0,
        atr: 20.0,
        volume: null,
        vwap: null,
      },
      confirmation: {
        ema: true,
        rsi_momentum: true,
        volume: null,
        multi_timeframe: true,
      },
      status: 'HISTORICAL',
      price: 21960.0,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: sellData,
        activeTimeframe: '15m',
      }),
    )

    // Signal status
    assert.match(markup, /SELL/)
    assert.match(markup, /SELL SIGNAL FROM STRATEGY ENGINE/)
    assert.match(markup, /signal-dominant-box sell/)

    // Price & metrics
    assert.match(markup, /21,960\.00/)
    assert.match(markup, /4\/4 timeframes aligned SHORT/)
    assert.match(markup, /80%/)

    // Execution targets
    assert.match(markup, /21,990\.00/)
    assert.match(markup, /21,915\.00/)
    assert.match(markup, /21,900\.00/)

    // Confirmations
    assert.match(markup, /Confirmed/)
    assert.match(markup, /EMA20: 21,980\.00 • EMA50: 22,010\.00/)
  })

  // -------------------------------------------------------------------------
  // 3. Strategy panel renders NO TRADE
  // -------------------------------------------------------------------------
  it('3. Strategy panel renders NO TRADE without fabricating execution levels', () => {
    const noTradeData = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      timestamp: '2024-03-26T15:29:00+05:30',
      signal: 'NO_TRADE',
      signal_reason: 'Incomplete or neutral timeframe trend alignment.',
      entry_price: null,
      stop_loss: null,
      target_1: null,
      target_2: null,
      confidence: 0.0,
      indicators: {
        ema_fast: 22005.1,
        ema_slow: 21995.4,
        rsi: 54.2,
        atr: 22.1,
        volume: null,
        vwap: null,
      },
      confirmation: {
        ema: false,
        rsi_momentum: false,
        volume: null,
        multi_timeframe: false,
      },
      status: 'HISTORICAL',
      price: 22004.7,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: noTradeData,
        activeTimeframe: '15m',
      }),
    )

    // Signal status
    assert.match(markup, /NO TRADE/)
    assert.match(markup, /NO ACTIVE TRADE SETUP/)
    assert.match(markup, /signal-dominant-box no-trade/)

    // Metrics & Reason
    assert.match(markup, /Incomplete or neutral timeframe trend alignment\./)

    // Brackets: must NOT fabricate prices
    assert.match(markup, /No active setup/)

    // Disagreement in MTF
    assert.match(markup, /Disagreement across evaluated timeframes/)
  })

  // -------------------------------------------------------------------------
  // 4. Loading state
  // -------------------------------------------------------------------------
  it('4. Strategy panel renders loading state with accessible semantics', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: null,
        loading: true,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /role="status"/)
    assert.match(markup, /aria-live="polite"/)
    assert.match(markup, /Connecting to Strategy Engine\.\.\./)
  })

  // -------------------------------------------------------------------------
  // 5. API error state
  // -------------------------------------------------------------------------
  it('5. Strategy panel renders API error state with retry action', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: null,
        loading: false,
        error: 'Backend API connection failed (HTTP 503)',
        activeTimeframe: '15m',
        onRetry: () => {},
      }),
    )

    assert.match(markup, /role="alert"/)
    assert.match(markup, /Signal Engine Offline/)
    assert.match(markup, /Backend API connection failed \(HTTP 503\)/)
    assert.match(markup, /Retry Connection/)
  })

  // -------------------------------------------------------------------------
  // 6. Unsupported timeframe state
  // -------------------------------------------------------------------------
  it('6. Strategy panel renders unsupported timeframe state with quick switch options', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: null,
        loading: false,
        error: null,
        activeTimeframe: '1H',
        isUnsupported: true,
        onSelectTimeframe: () => {},
      }),
    )

    assert.match(markup, /Timeframe 1H Not Supported/)
    assert.match(markup, /5m, 10m, 15m, and 30m intervals/)
    assert.match(markup, /Switch to 15m/)
    assert.match(markup, /Switch to 5m/)
  })

  // -------------------------------------------------------------------------
  // 7. Null optional fields do not crash the UI
  // -------------------------------------------------------------------------
  it('7. Null optional fields render safe fallbacks without throwing', () => {
    const nullData = {
      symbol: 'NIFTY 50',
      timeframe: '5m',
      timestamp: null,
      signal: 'NO_TRADE',
      signal_reason: 'Warmup',
      entry_price: null,
      stop_loss: null,
      target_1: null,
      target_2: null,
      confidence: null,
      indicators: {
        ema_fast: null,
        ema_slow: null,
        rsi: null,
        atr: null,
        volume: null,
        vwap: null,
      },
      confirmation: {
        ema: null,
        rsi_momentum: null,
        volume: null,
        multi_timeframe: null,
      },
      status: 'HISTORICAL',
      price: null,
    }

    assert.doesNotThrow(() => {
      const markup = renderToStaticMarkup(
        React.createElement(StrategySignalPanel, {
          signalData: nullData,
          activeTimeframe: '5m',
        }),
      )
      assert.match(markup, /NO TRADE/)
      assert.match(markup, /No active setup/)
    })
  })
})
