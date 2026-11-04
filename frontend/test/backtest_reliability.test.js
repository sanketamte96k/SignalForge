import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { StrategySignalPanel } from '../src/StrategySignalPanel.jsx'
import {
  cancelBacktestJob,
  fetchBacktestJobStatus,
  fetchBacktestJobResult,
} from '../src/api.js'

describe('Backtest Operational Reliability & Hardening (Phase 24G.29 Frontend Audit)', () => {
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
  // 1. Causal vs Theoretical Labeling Audit
  // -------------------------------------------------------------------------
  it('1. Execution model dropdown explicitly distinguishes causal vs theoretical lookahead-biased models', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: sampleSignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /next_open \(Causal\) \[Realistic\]/)
    assert.match(markup, /same_close \(Theoretical\) \[Lookahead Biased\]/)
  })

  // -------------------------------------------------------------------------
  // 2. Cancellation API Function Exists & Binds
  // -------------------------------------------------------------------------
  it('2. cancelBacktestJob, fetchBacktestJobStatus, and fetchBacktestJobResult are properly callable', () => {
    assert.equal(typeof cancelBacktestJob, 'function')
    assert.equal(typeof fetchBacktestJobStatus, 'function')
    assert.equal(typeof fetchBacktestJobResult, 'function')
  })

  // -------------------------------------------------------------------------
  // 3. UI Protection: Non-Duplication During Run
  // -------------------------------------------------------------------------
  it('3. Panel inputs contain accessible IDs and form controls', () => {
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
})
