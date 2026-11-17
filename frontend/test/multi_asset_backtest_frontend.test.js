import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { StrategySignalPanel } from '../src/StrategySignalPanel.jsx'
import { BacktestAnalyticsModal } from '../src/BacktestAnalyticsModal.jsx'
import {
  runMultiAssetBacktest,
  fetchMultiAssetBacktestJobResult,
} from '../src/api.js'

describe('Multi-Asset Backtest Frontend Integration (Phase 27C.7)', () => {
  const sampleSignal = {
    symbol: 'RELIANCE',
    timeframe: '15m',
    timestamp: '2024-03-26T15:15:00+05:30',
    signal: 'BUY',
    signal_reason: 'Trend confirmed',
    entry_price: 2500.0,
    stop_loss: 2470.0,
    target_1: 2530.0,
    target_2: 2560.0,
    confidence: 85.0,
    status: 'HISTORICAL',
    price: 2500.0,
  }

  const sampleMultiResult = {
    job_id: 'job-multi-test-123',
    status: 'COMPLETED',
    symbols: ['RELIANCE', 'INFY'],
    execution_model: 'next_open',
    date_range: { start: '2019-01-02', end: '2019-01-15', total_candles: 750 },
    portfolio: {
      initial_capital: 100000.0,
      final_equity: 104500.0,
      realized_net_pnl: 4500.0,
      unrealized_pnl: 0.0,
      total_transaction_costs: 250.0,
      peak_equity: 105200.0,
      max_drawdown_pct: 2.1,
      total_trades: 12,
      win_rate_pct: 66.67,
      gross_exposure: 0.0,
      available_margin: 85000.0,
      allocated_margin: 0.0,
      is_bankrupt: false,
    },
    metrics: {
      total_return_pct: 4.5,
      total_pnl: 4500.0,
      total_trades: 12,
      winning_trades: 8,
      losing_trades: 4,
      win_rate_pct: 66.67,
      profit_factor: 2.45,
      max_drawdown_pct: 2.1,
      expectancy: 375.0,
      average_win: 700.0,
      average_loss: -275.0,
    },
    symbol_metrics: {
      RELIANCE: {
        symbol: 'RELIANCE',
        trades: 7,
        winning_trades: 5,
        losing_trades: 2,
        net_pnl: 3200.0,
        gross_pnl: 3350.0,
        total_transaction_costs: 150.0,
        win_rate_pct: 71.43,
        profit_factor: 2.8,
        position_status: 'CLOSED',
      },
      INFY: {
        symbol: 'INFY',
        trades: 5,
        winning_trades: 3,
        losing_trades: 2,
        net_pnl: 1300.0,
        gross_pnl: 1400.0,
        total_transaction_costs: 100.0,
        win_rate_pct: 60.0,
        profit_factor: 2.1,
        position_status: 'CLOSED',
      },
    },
    risk_and_quality: {
      active_risk_blockers: {},
      stale_symbols: [],
      missing_candle_stats: { RELIANCE: 0, INFY: 0 },
      global_feed_outage_events: 0,
      indeterminate_valuation_events: 0,
      stale_price_events: 0,
      stale_notional_exposure: 0.0,
      unresolved_liquidation_exposure: 0.0,
      global_outage_detection_status: 'LIMITED_TO_RECEIVED_UNION',
      expected_timeline_provided: false,
    },
    trades: [
      {
        trade_id: 1,
        symbol: 'RELIANCE',
        side: 'BUY',
        entry_time: '2019-01-03 09:30:00',
        entry_price: 2450.0,
        exit_time: '2019-01-03 14:15:00',
        exit_price: 2480.0,
        quantity: 20,
        gross_pnl: 600.0,
        costs: 20.0,
        net_pnl: 580.0,
        return_pct: 1.22,
        exit_reason: 'TARGET_1',
      },
      {
        trade_id: 2,
        symbol: 'INFY',
        side: 'BUY',
        entry_time: '2019-01-04 10:00:00',
        entry_price: 720.0,
        exit_time: '2019-01-04 12:30:00',
        exit_price: 735.0,
        quantity: 50,
        gross_pnl: 750.0,
        costs: 25.0,
        net_pnl: 725.0,
        return_pct: 2.08,
        exit_reason: 'TARGET_2',
      },
    ],
    unresolved_positions: [],
  }

  // 1. API Contract
  it('1. API exports runMultiAssetBacktest and fetchMultiAssetBacktestJobResult', () => {
    assert.equal(typeof runMultiAssetBacktest, 'function')
    assert.equal(typeof fetchMultiAssetBacktestJobResult, 'function')
  })

  // 2. Strategy Panel Mode Controls
  it('2. Strategy panel renders mode toggle buttons for Single Symbol and Multi-Asset', () => {
    const markup = renderToStaticMarkup(
      React.createElement(StrategySignalPanel, {
        signalData: sampleSignal,
        activeTimeframe: '15m',
      }),
    )

    assert.match(markup, /id="bt-mode-single-btn"/)
    assert.match(markup, /id="bt-mode-multi-btn"/)
    assert.match(markup, /Single Symbol/)
    assert.match(markup, /Multi-Asset Portfolio/)
  })

  // 3. Backtest Analytics Modal Multi-Asset Header & Attribution Tab
  it('3. BacktestAnalyticsModal renders multi-asset attribution tab and per-symbol metrics', () => {
    const markup = renderToStaticMarkup(
      React.createElement(BacktestAnalyticsModal, {
        isOpen: true,
        onClose: () => {},
        result: sampleMultiResult,
        initialTab: 'attribution',
      }),
    )

    // Header checks
    assert.match(markup, /Portfolio \(RELIANCE, INFY\)/)
    assert.match(markup, /id="bam-tab-attribution"/)
    assert.match(markup, /Attribution &amp; Risk/)

    // Symbol metrics rendered
    assert.match(markup, /RELIANCE/)
    assert.match(markup, /INFY/)
    assert.match(markup, /Zero unresolved or stranded positions/)
  })

  // 4. Backtest Analytics Modal Unresolved Positions Display
  it('4. BacktestAnalyticsModal correctly visualizes unresolved stranded positions when present', () => {
    const resultWithUnresolved = {
      ...sampleMultiResult,
      unresolved_positions: [
        {
          symbol: 'TCS',
          side: 'BUY',
          entry_time: '2019-01-15 14:00:00',
          entry_price: 2000.0,
          quantity: 10,
          current_price: 1980.0,
          allocated_margin: 20000.0,
          notional_value: 19800.0,
          unrealized_pnl: -200.0,
          is_stale: true,
          pending_liquidation: true,
          pending_liquidation_reason: 'GLOBAL_OUTAGE_SESSION_END',
        },
      ],
    }

    const markup = renderToStaticMarkup(
      React.createElement(BacktestAnalyticsModal, {
        isOpen: true,
        onClose: () => {},
        result: resultWithUnresolved,
        initialTab: 'attribution',
      }),
    )

    assert.match(markup, /TCS/)
    assert.match(markup, /PENDING LIQUIDATION/)
    assert.match(markup, /GLOBAL_OUTAGE_SESSION_END/)
  })
})
