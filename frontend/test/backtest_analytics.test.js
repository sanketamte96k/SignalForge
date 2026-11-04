import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { BacktestAnalyticsModal } from '../src/BacktestAnalyticsModal.jsx'
import {
  fetchBacktestAnalytics,
  getBacktestTearsheetUrl,
} from '../src/api.js'

describe('Backtest Analytics & Interactive Equity Reporting (Phase 24G.30 Frontend Test)', () => {
  const sampleBacktestResult = {
    job_id: 'job-test-7788',
    status: 'COMPLETED',
    symbol: 'NIFTY 50',
    date_range: {
      start: '2024-01-01 09:15:00',
      end: '2024-01-31 15:30:00',
      total_candles: 7500,
    },
    execution_model: 'next_open',
    metrics: {
      total_trades: 4,
      winning_trades: 2,
      losing_trades: 2,
      breakeven_trades: 0,
      total_pnl: 150.0,
      total_return_pct: 0.15,
      win_rate_pct: 50.0,
      average_win: 200.0,
      average_loss: -125.0,
      profit_factor: 1.6,
      expectancy: 37.5,
      max_drawdown_pct: 0.25,
    },
    portfolio: {
      initial_capital: 100000.0,
      final_equity: 100150.0,
      peak_equity: 100200.0,
      max_drawdown_pct: 0.25,
      is_bankrupt: false,
    },
    trades: [
      {
        trade_id: 1,
        entry_time: '2024-01-02 09:30:00',
        exit_time: '2024-01-02 10:15:00',
        side: 'BUY',
        entry_price: 21700.0,
        exit_price: 21900.0,
        quantity: 1,
        gross_pnl: 200.0,
        costs: 4.0,
        net_pnl: 196.0,
        return_pct: 0.9,
        exit_reason: 'TAKE_PROFIT',
      },
      {
        trade_id: 2,
        entry_time: '2024-01-05 11:00:00',
        exit_time: '2024-01-05 11:45:00',
        side: 'BUY',
        entry_price: 21850.0,
        exit_price: 21750.0,
        quantity: 1,
        gross_pnl: -100.0,
        costs: 4.0,
        net_pnl: -104.0,
        return_pct: -0.48,
        exit_reason: 'STOP_LOSS',
      },
      {
        trade_id: 3,
        entry_time: '2024-01-10 13:00:00',
        exit_time: '2024-01-10 14:15:00',
        side: 'SELL',
        entry_price: 21600.0,
        exit_price: 21750.0,
        quantity: 1,
        gross_pnl: -150.0,
        costs: 4.0,
        net_pnl: -154.0,
        return_pct: -0.71,
        exit_reason: 'STOP_LOSS',
      },
      {
        trade_id: 4,
        entry_time: '2024-01-15 10:00:00',
        exit_time: '2024-01-15 12:30:00',
        side: 'BUY',
        entry_price: 21500.0,
        exit_price: 21716.0,
        quantity: 1,
        gross_pnl: 216.0,
        costs: 4.0,
        net_pnl: 212.0,
        return_pct: 0.98,
        exit_reason: 'TAKE_PROFIT',
      },
    ],
  }

  // -------------------------------------------------------------------------
  // 1. API Helper Functions Verification
  // -------------------------------------------------------------------------
  it('1. API exports getBacktestTearsheetUrl and fetchBacktestAnalytics', () => {
    assert.equal(typeof getBacktestTearsheetUrl, 'function')
    assert.equal(typeof fetchBacktestAnalytics, 'function')

    const urlView = getBacktestTearsheetUrl('job-xyz')
    assert.equal(urlView, '/api/strategy/backtest/jobs/job-xyz/tearsheet')

    const urlDownload = getBacktestTearsheetUrl('job-xyz', true)
    assert.equal(urlDownload, '/api/strategy/backtest/jobs/job-xyz/tearsheet?download=true')
  })

  // -------------------------------------------------------------------------
  // 2. BacktestAnalyticsModal Render Verification
  // -------------------------------------------------------------------------
  it('2. BacktestAnalyticsModal renders header, model badge, KPI grid, and SVG charts', () => {
    const markup = renderToStaticMarkup(
      React.createElement(BacktestAnalyticsModal, {
        isOpen: true,
        onClose: () => {},
        result: sampleBacktestResult,
      }),
    )

    // Header & Symbol
    assert.match(markup, /Quantitative Backtest Analytics — NIFTY 50/)
    assert.match(markup, /Causal Next-Open/)

    // Tearsheet action links
    assert.match(markup, /href="\/api\/strategy\/backtest\/jobs\/job-test-7788\/tearsheet"/)
    assert.match(markup, /href="\/api\/strategy\/backtest\/jobs\/job-test-7788\/tearsheet\?download=true"/)

    // Navigation Tabs
    assert.match(markup, /Equity &amp; Drawdown/)
    assert.match(markup, /Trade History \(4\)/)
    assert.match(markup, /Extended Metrics/)

    // SVG Charts
    assert.match(markup, /aria-label="Account equity progression chart"/)
    assert.match(markup, /aria-label="Underwater drawdown percentage chart"/)
    assert.match(markup, /Start: ₹1,00,000/)
  })

  // -------------------------------------------------------------------------
  // 3. Modal Hidden When Closed or Result Null
  // -------------------------------------------------------------------------
  it('3. BacktestAnalyticsModal returns null when isOpen is false or result is null', () => {
    const closedMarkup = renderToStaticMarkup(
      React.createElement(BacktestAnalyticsModal, {
        isOpen: false,
        onClose: () => {},
        result: sampleBacktestResult,
      }),
    )
    assert.equal(closedMarkup, '')

    const nullResultMarkup = renderToStaticMarkup(
      React.createElement(BacktestAnalyticsModal, {
        isOpen: true,
        onClose: () => {},
        result: null,
      }),
    )
    assert.equal(nullResultMarkup, '')
  })

  // -------------------------------------------------------------------------
  // 4. Empty Result (0 Trades) Handling
  // -------------------------------------------------------------------------
  it('4. Handles empty result (0 trades) gracefully with baseline equity and 0.0% drawdown', () => {
    const emptyResult = {
      ...sampleBacktestResult,
      metrics: {
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        breakeven_trades: 0,
        total_pnl: 0.0,
        total_return_pct: 0.0,
        win_rate_pct: 0.0,
        average_win: 0.0,
        average_loss: 0.0,
        profit_factor: 0.0,
        expectancy: 0.0,
        max_drawdown_pct: 0.0,
      },
      portfolio: {
        initial_capital: 100000.0,
        final_equity: 100000.0,
        peak_equity: 100000.0,
        max_drawdown_pct: 0.0,
        is_bankrupt: false,
      },
      trades: [],
    }

    const markup = renderToStaticMarkup(
      React.createElement(BacktestAnalyticsModal, {
        isOpen: true,
        onClose: () => {},
        result: emptyResult,
      }),
    )

    assert.match(markup, /Trade History \(0\)/)
    assert.match(markup, /aria-label="Account equity progression chart"/)
    assert.match(markup, /aria-label="Underwater drawdown percentage chart"/)
  })

  // -------------------------------------------------------------------------
  // 5. Theoretical Execution Warning Badge
  // -------------------------------------------------------------------------
  it('5. Renders Theoretical Lookahead badge when execution_model is same_close', () => {
    const theoreticalResult = {
      ...sampleBacktestResult,
      execution_model: 'same_close',
    }

    const markup = renderToStaticMarkup(
      React.createElement(BacktestAnalyticsModal, {
        isOpen: true,
        onClose: () => {},
        result: theoreticalResult,
      }),
    )

    assert.match(markup, /Theoretical Lookahead/)
    assert.match(markup, /bam-badge-theoretical/)
  })
})
