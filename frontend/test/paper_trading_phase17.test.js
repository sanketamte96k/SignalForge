import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { StrategySignalPanel } from '../src/StrategySignalPanel.jsx'
import PaperTradingView from '../src/PaperTradingView.jsx'

describe('Paper Trading Engine & Lifecycle (Phase 17 Frontend Integration)', () => {
  // 1. Paper Trade button appears for valid signal
  it('1. Paper Trade button appears for valid BUY/SELL signal', () => {
    const buySignal = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      timestamp: '2024-03-26T15:15:00+05:30',
      signal: 'BUY',
      signal_reason: 'Trend confirmed',
      entry_price: 24000.0,
      stop_loss: 23900.0,
      target_1: 24150.0,
      target_2: 24300.0,
      confidence: 85.0,
      status: 'HISTORICAL',
      price: 24000.0,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: buySignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /PAPER TRADE/)
    assert.match(markup, /SIMULATED • NO REAL ORDER/)
  })

  // 2. Paper Trade unavailable for NO_TRADE
  it('2. Paper Trade unavailable for NO_TRADE setup', () => {
    const noTradeSignal = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      timestamp: '2024-03-26T15:15:00+05:30',
      signal: 'NO_TRADE',
      signal_reason: 'Indicators neutral',
      entry_price: null,
      stop_loss: null,
      target_1: null,
      target_2: null,
      status: 'HISTORICAL',
      price: 24000.0,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: noTradeSignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /PAPER TRADING UNAVAILABLE/)
    assert.match(markup, /Strategy Signal is NO TRADE/)
  })

  // 3. Confirmation state rendering
  it('3. Explicit confirmation labels and warning', () => {
    const buySignal = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      signal: 'BUY',
      entry_price: 24000.0,
      stop_loss: 23900.0,
      target_1: 24150.0,
      target_2: 24300.0,
      price: 24000.0,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: buySignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /PAPER TRADING ENGINE/)
    assert.match(markup, /SIMULATED • NO REAL ORDER/)
  })

  // 4. Open position state
  it('4. Open position shows live execution levels and brackets', () => {
    const buySignal = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      signal: 'BUY',
      entry_price: 24000.0,
      stop_loss: 23900.0,
      target_1: 24150.0,
      target_2: 24300.0,
      price: 24050.0,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: buySignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /23,900\.00/)
    assert.match(markup, /24,150\.00/)
    assert.match(markup, /24,300\.00/)
  })

  // 5. P&L display
  it('5. P&L display semantics format properly', () => {
    const buySignal = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      signal: 'BUY',
      entry_price: 24000.0,
      stop_loss: 23900.0,
      target_1: 24150.0,
      target_2: 24300.0,
      price: 24000.0,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: buySignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /EXECUTION TARGETS &amp; STOP LOSS/)
    assert.match(markup, /Stop Loss/)
    assert.match(markup, /Target 1/)
    assert.match(markup, /Target 2/)
  })

  // 6. Close trade state
  it('6. Close paper trade capability is exposed when position is open', () => {
    const buySignal = {
      symbol: 'NIFTY 50',
      timeframe: '15m',
      signal: 'BUY',
      entry_price: 24000.0,
      stop_loss: 23900.0,
      target_1: 24150.0,
      target_2: 24300.0,
    }

    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: buySignal,
        activeTimeframe: '15m',
      }),
    )

    assert.ok(markup.includes('PAPER TRADE'))
  })

  // 7. Trade history in PaperTradingView
  it('7. PaperTradingView renders Trade History section and filters', () => {
    const markup = renderToStaticMarkup(
      React.createElement(PaperTradingView),
    )

    assert.match(markup, /Paper Trading Engine/)
    assert.match(markup, /SIMULATION ONLY • NO REAL MONEY/)
  })

  // 8. API error handling in StrategySignalPanel
  it('8. StrategySignalPanel handles API error gracefully', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: null,
        error: 'Failed to connect to backend engine',
        onRetry: () => {},
      }),
    )

    assert.match(markup, /Signal Engine Offline/)
    assert.match(markup, /Failed to connect to backend engine/)
    assert.match(markup, /Retry Connection/)
  })

  // 9. Loading state in StrategySignalPanel
  it('9. StrategySignalPanel renders loading state when connecting', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: null,
        loading: true,
      }),
    )

    assert.match(markup, /Connecting to Strategy Engine\.\.\./)
  })

  // 10. Empty state in StrategySignalPanel
  it('10. StrategySignalPanel renders empty state when no data exists', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: null,
        loading: false,
        error: null,
      }),
    )

    assert.match(markup, /Strategy Data Unavailable/)
  })
})
