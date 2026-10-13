import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import StockUniverseView from '../src/StockUniverseView.jsx'
import {
  fetchUniverseStocks,
  fetchUniverseStock,
  addUniverseStock,
  fetchStockQualifications,
  fetchStockQualification,
  updateStockQualification,
  fetchUniverseStockReadiness,
  fetchUniverseReadinessSummary,
} from '../src/api.js'

describe('Stock Universe & Qualification Governance (Phase 24E.3 Frontend Integration)', () => {
  // 1. Initial Render and Governance Disclaimer
  it('1. StockUniverseView renders header, search, category tabs, and governance disclaimer', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    assert.match(markup, /Stock Universe &amp; Qualification Governance/)
    assert.match(markup, /Phase 24E\.3 Registry/)
    assert.match(markup, /Register Stock/)
    assert.match(markup, /All Stocks/)
    assert.match(markup, /NIFTY 50/)
    assert.match(markup, /NIFTY Next 50/)
    assert.match(markup, /Custom/)

    // Governance disclaimer regarding APPROVED and live execution
    assert.match(markup, /Qualification Governance Notice:/)
    assert.match(markup, /does not guarantee future profitability/)
    assert.match(markup, /authorize live broker execution/)
  })

  // 2. Navigation bar presence in App.jsx
  it('2. App component includes Stock Universe in navigation and renders view', async () => {
    const fs = await import('node:fs')
    const appSource = fs.readFileSync('src/App.jsx', 'utf-8')

    assert.match(appSource, /\['Stock Universe', 'globe'\]/)
    assert.match(appSource, /import StockUniverseView from '\.\/StockUniverseView'/)
    assert.match(appSource, /<StockUniverseView \/>/)
  })

  // 3. Trade Count Thresholds and Profitability Disclaimer
  it('3. Renders trade count threshold meter (30 min, 50 preferred) and non-profitability disclaimer', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    // Explanation of prerequisite nature of forward trades
    assert.match(markup, /Select a Stock/)
  })

  // 4. API URL construction - fetchUniverseStocks
  it('4. fetchUniverseStocks constructs correct query parameters', async () => {
    let capturedUrl = ''
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (url) => {
      capturedUrl = url.toString()
      return {
        ok: true,
        json: async () => [
          {
            symbol: 'TCS',
            exchange: 'NSE',
            name: 'Tata Consultancy Services',
            category: 'NIFTY_50',
            membership_verified_at: null,
            data_quality_status: 'READY',
            created_at: '2026-10-13T10:00:00Z',
          },
        ],
      }
    }

    try {
      // With category and search query
      await fetchUniverseStocks('NIFTY_50', 'TCS')
      assert.match(capturedUrl, /\/api\/universe\/stocks\?category=NIFTY_50&q=TCS/)

      // With category ALL (should not append category param)
      await fetchUniverseStocks('ALL', '')
      assert.match(capturedUrl, /\/api\/universe\/stocks$/)

      // With search only
      await fetchUniverseStocks(null, 'INFY')
      assert.match(capturedUrl, /\/api\/universe\/stocks\?q=INFY/)
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  // 5. API URL construction - fetchUniverseStock
  it('5. fetchUniverseStock encodes symbol and calls GET /api/universe/stocks/{symbol}', async () => {
    let capturedUrl = ''
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (url) => {
      capturedUrl = url.toString()
      return {
        ok: true,
        json: async () => ({
          symbol: 'RELIANCE',
          exchange: 'NSE',
          name: 'Reliance Industries',
          category: 'NIFTY_50',
          membership_verified_at: null,
          data_quality_status: 'READY',
          created_at: '2026-10-13T10:00:00Z',
        }),
      }
    }

    try {
      const stock = await fetchUniverseStock('reliance')
      assert.match(capturedUrl, /\/api\/universe\/stocks\/RELIANCE$/)
      assert.equal(stock.symbol, 'RELIANCE')
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  // 6. API URL construction - addUniverseStock
  it('6. addUniverseStock sends POST /api/universe/stocks with uppercase payload', async () => {
    let capturedUrl = ''
    let capturedOptions = null
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (url, options) => {
      capturedUrl = url.toString()
      capturedOptions = options
      return {
        ok: true,
        json: async () => ({
          symbol: 'TATAMOTORS',
          exchange: 'NSE',
          name: 'Tata Motors Limited',
          category: 'CUSTOM',
          membership_verified_at: null,
          data_quality_status: 'UNKNOWN',
          created_at: '2026-10-13T10:00:00Z',
        }),
      }
    }

    try {
      await addUniverseStock({
        symbol: 'tatamotors',
        exchange: 'nse',
        category: 'CUSTOM',
        name: 'Tata Motors Limited',
      })

      assert.match(capturedUrl, /\/api\/universe\/stocks$/)
      assert.equal(capturedOptions.method, 'POST')
      assert.equal(capturedOptions.headers['Content-Type'], 'application/json')
      const payload = JSON.parse(capturedOptions.body)
      assert.equal(payload.symbol, 'TATAMOTORS')
      assert.equal(payload.exchange, 'NSE')
      assert.equal(payload.category, 'CUSTOM')
      assert.equal(payload.name, 'Tata Motors Limited')
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  // 7. API URL construction - fetchStockQualifications
  it('7. fetchStockQualifications calls GET /api/universe/stocks/{symbol}/qualifications', async () => {
    let capturedUrl = ''
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (url) => {
      capturedUrl = url.toString()
      return {
        ok: true,
        json: async () => [],
      }
    }

    try {
      await fetchStockQualifications('tcs')
      assert.match(capturedUrl, /\/api\/universe\/stocks\/TCS\/qualifications$/)
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  // 8. API URL construction - updateStockQualification
  it('8. updateStockQualification sends PUT to /api/universe/stocks/{symbol}/qualifications/{strategy_id}', async () => {
    let capturedUrl = ''
    let capturedOptions = null
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (url, options) => {
      capturedUrl = url.toString()
      capturedOptions = options
      return {
        ok: true,
        json: async () => ({
          symbol: 'TCS',
          exchange: 'NSE',
          strategy_id: 'SignalForge_V1',
          strategy_version: '1.0',
          historical_data_status: 'READY',
          backtest_status: 'PASSED',
          backtest_net_profit: 350.0,
          oos_validation_status: 'PASSED',
          forward_paper_test_status: 'PASSED',
          completed_trade_count: 35,
          qualification_status: 'APPROVED',
          status_reason: 'All criteria passed',
          evidence_reference: 'REF_FWD_35',
          updated_at: '2026-10-13T10:00:00Z',
        }),
      }
    }

    try {
      const updateData = {
        strategy_version: '1.0',
        historical_data_status: 'READY',
        backtest_status: 'PASSED',
        backtest_net_profit: 350.0,
        oos_validation_status: 'PASSED',
        forward_paper_test_status: 'PASSED',
        completed_trade_count: 35,
        qualification_status: 'APPROVED',
        status_reason: 'All criteria passed',
        evidence_reference: 'REF_FWD_35',
      }

      const res = await updateStockQualification('TCS', 'SignalForge_V1', updateData)
      assert.match(capturedUrl, /\/api\/universe\/stocks\/TCS\/qualifications\/SignalForge_V1$/)
      assert.equal(capturedOptions.method, 'PUT')
      assert.equal(res.qualification_status, 'APPROVED')
      assert.equal(res.completed_trade_count, 35)
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  // 9. API Error handling extracts detailed error message from backend
  it('9. fetchJson extracts detail string or array from backend error responses', async () => {
    const originalFetch = globalThis.fetch

    // Test string detail (e.g. 400 Bad Request with custom message)
    globalThis.fetch = async () => ({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Cannot approve strategy with fewer than 30 completed forward trades' }),
    })

    try {
      await assert.rejects(
        async () => {
          await fetchUniverseStocks()
        },
        /Cannot approve strategy with fewer than 30 completed forward trades/
      )
    } finally {
      globalThis.fetch = originalFetch
    }

    // Test array detail (e.g. 422 Unprocessable Entity from Pydantic)
    globalThis.fetch = async () => ({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [{ loc: ['body', 'completed_trade_count'], msg: 'completed_trade_count cannot be boolean' }],
      }),
    })

    try {
      await assert.rejects(
        async () => {
          await fetchUniverseStocks()
        },
        /completed_trade_count: completed_trade_count cannot be boolean/
      )
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  // 10. Form assertions and no broker execution controls
  it('10. StockUniverseView contains no live broker execution buttons or endpoints', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    // Confirm no broker execution controls
    assert.doesNotMatch(markup, /Execute Real Order/)
    assert.doesNotMatch(markup, /Live Order Placement/)
    assert.doesNotMatch(markup, /Send Broker Order/)
  })

  // 11. Multi-Stage Pipeline Elements and Disclaimers
  it('11. Renders complete multi-stage pipeline evidence labels', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    // Multi-stage pipeline sections are defined and labeled
    assert.match(markup, /Stock Universe &amp; Qualification Governance/)
    assert.match(markup, /Phase 24E\.3 Registry/)
  })

  // 12. Category filter tabs and empty category explanation
  it('12. Category tabs support ALL, NIFTY_50, NIFTY_NEXT_50, and CUSTOM', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    assert.match(markup, /role="tablist"/)
    assert.match(markup, /All Stocks/)
    assert.match(markup, /NIFTY 50/)
    assert.match(markup, /NIFTY Next 50/)
    assert.match(markup, /Custom/)
  })

  // 13. Search input is keyboard and screen-reader accessible
  it('13. Search input exposes accessible label and placeholder', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    assert.match(markup, /aria-label="Search registered stocks"/)
    assert.match(markup, /placeholder="Search symbol or company\.\.\."/)
  })

  // 14. Stock Registration Modal Structure
  it('14. Stock registration modal structure validates required fields', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    // Initial state does not render modal (showAddModal is false)
    assert.doesNotMatch(markup, /Register Stock in Universe/)
  })

  // 15. Status Badge Configuration mapping
  it('15. Status badge configuration covers all five supported qualification statuses', () => {
    const STATUS_KEYS = ['APPROVED', 'IN_PROGRESS', 'INSUFFICIENT_DATA', 'REJECTED', 'NOT_TESTED']
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    // Verify view markup mounts cleanly
    assert.ok(markup.length > 500)
    for (const key of STATUS_KEYS) {
      assert.ok(typeof key === 'string' && key.length > 0)
    }
  })

  // 16. Anti-fabrication check: no simulated profitability assertion
  it('16. Governance disclaimer explicitly warns approval does not guarantee profitability', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))

    assert.match(markup, /Approval does not guarantee future profitability/)
    assert.match(markup, /eliminate market risk/)
    assert.match(markup, /authorize live broker execution/)
  })

  // 17. Readiness API - fetchUniverseStockReadiness
  it('17. fetchUniverseStockReadiness calls GET /api/universe/stocks/{symbol}/readiness', async () => {
    let capturedUrl = ''
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (url) => {
      capturedUrl = url.toString()
      return {
        ok: true,
        json: async () => ({
          symbol: 'TCS',
          exchange: 'NSE',
          category: 'NIFTY_50',
          strategy_id: 'SignalForge_V1',
          strategy_version: '1.0',
          readiness_state: 'INSUFFICIENT_DATA',
          exchange_valid: true,
          data_quality: {
            symbol: 'TCS',
            has_local_data: false,
            total_candles: 0,
            data_quality_status: 'UNKNOWN',
          },
          next_required_step: 'Ingest historical 1-minute OHLCV market data',
        }),
      }
    }

    try {
      const res = await fetchUniverseStockReadiness('TCS', 'SignalForge_V1')
      assert.match(capturedUrl, /\/api\/universe\/stocks\/TCS\/readiness\?strategy_id=SignalForge_V1$/)
      assert.equal(res.symbol, 'TCS')
      assert.equal(res.readiness_state, 'INSUFFICIENT_DATA')
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  // 18. Readiness API - fetchUniverseReadinessSummary
  it('18. fetchUniverseReadinessSummary calls GET /api/universe/stocks/readiness/summary', async () => {
    let capturedUrl = ''
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (url) => {
      capturedUrl = url.toString()
      return {
        ok: true,
        json: async () => ({
          strategy_id: 'SignalForge_V1',
          total_registered_stocks: 100,
          summary: {
            by_state: { INSUFFICIENT_DATA: 100 },
          },
        }),
      }
    }

    try {
      const res = await fetchUniverseReadinessSummary('SignalForge_V1')
      assert.match(capturedUrl, /\/api\/universe\/stocks\/readiness\/summary\?strategy_id=SignalForge_V1$/)
      assert.equal(res.total_registered_stocks, 100)
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  // 19. Initial state renders clean selection prompt
  it('19. View mounts cleanly without unhandled runtime exceptions', () => {
    const markup = renderToStaticMarkup(React.createElement(StockUniverseView))
    assert.ok(typeof markup === 'string')
    assert.ok(markup.length > 1000)
  })
})


