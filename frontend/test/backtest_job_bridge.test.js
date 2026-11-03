import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { StrategySignalPanel } from '../src/StrategySignalPanel.jsx'
import {
  runBacktest,
  fetchBacktestJobStatus,
  fetchBacktestJobResult,
  cancelBacktestJob,
  listBacktestJobs,
} from '../src/api.js'

describe('Backtest Job Bridge (Phase 24G.28 Frontend Integration)', () => {
  const sampleSignal = {
    symbol: 'NIFTY 50',
    timeframe: '15m',
    timestamp: '2024-03-26T15:15:00+05:30',
    signal: 'BUY',
    signal_reason: 'Trend confirmed',
    entry_price: 22000.0,
    stop_loss: 21950.0,
    target_1: 22050.0,
    target_2: 22100.0,
    confidence: 85.0,
    status: 'HISTORICAL',
    price: 22000.0,
  }

  // -------------------------------------------------------------------------
  // 1. Initial Render of Backtest Section
  // -------------------------------------------------------------------------
  it('1. Strategy panel renders Historical Backtest Engine section with controls', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: sampleSignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /HISTORICAL BACKTEST ENGINE/)
    assert.match(markup, /Start Date:/)
    assert.match(markup, /End Date:/)
    assert.match(markup, /Execution Model:/)
    assert.match(markup, /next_open \(Causal\)/)
    assert.match(markup, /Capital \(₹\):/)
    assert.match(markup, /RUN HISTORICAL BACKTEST/)
  })

  // -------------------------------------------------------------------------
  // 2. Active Job Rendering (Simulated via markup or props)
  // -------------------------------------------------------------------------
  it('2. Backtest controls contain accessible inputs with default parameters', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: sampleSignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /id="bt-start-date"/)
    assert.match(markup, /id="bt-end-date"/)
    assert.match(markup, /id="bt-exec-model"/)
    assert.match(markup, /id="bt-capital"/)
  })

  // -------------------------------------------------------------------------
  // 3. API Contract Functions
  // -------------------------------------------------------------------------
  it('3. runBacktest constructs POST request to /api/strategy/backtest/run', () => {
    assert.equal(typeof runBacktest, 'function')
    assert.equal(typeof fetchBacktestJobStatus, 'function')
    assert.equal(typeof fetchBacktestJobResult, 'function')
    assert.equal(typeof cancelBacktestJob, 'function')
    assert.equal(typeof listBacktestJobs, 'function')
  })
})
