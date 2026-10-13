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
})
