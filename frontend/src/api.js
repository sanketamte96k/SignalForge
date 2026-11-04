const RAW_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '')

async function fetchJson(path, options = {}) {
  const url = API_BASE_URL ? `${API_BASE_URL}${path}` : path

  const response = await fetch(url, options)

  if (!response.ok) {
    let detail = `API request failed with status ${response.status}`

    try {
      const body = await response.json()

      if (typeof body?.detail === 'string') {
        detail = body.detail
      } else if (Array.isArray(body?.detail)) {
        detail = body.detail
          .map((item) => (item?.msg ? (item?.loc ? `${item.loc.join('.')}: ${item.msg}` : item.msg) : JSON.stringify(item)))
          .join(', ')
      }
    } catch {
      // Keep the HTTP-status error when the response is not JSON.
    }

    throw new Error(detail)
  }

  return response.json()
}

export function fetchHealth() {
  return fetchJson('/api/health')
}

export function fetchNiftyLatest() {
  return fetchJson('/api/nifty/latest')
}

export function fetchNiftySignal(timeframe = '15m') {
  return fetchJson(`/api/nifty/signal?timeframe=${encodeURIComponent(timeframe)}`)
}

export function fetchStrategySignal(symbol = 'NIFTY 50', timeframe = '15m') {
  return fetchJson(
    `/api/strategy/signal?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`,
  )
}

export function fetchNiftyAnalysis() {
  return fetchJson('/api/nifty/analysis')
}

export function searchStocks(query) {
  const encodedQuery = encodeURIComponent(query.trim())

  return fetchJson(`/api/stocks/search?q=${encodedQuery}`)
}

export function addStock(stock) {
  return fetchJson('/api/stocks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(stock),
  })
}

export function fetchStock(symbol) {
  return fetchJson(
    `/api/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}`,
  )
}

export function fetchStockValidation(symbol) {
  return fetchJson(
    `/api/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}/validation`,
  )
}

export function fetchStockReadiness(symbol) {
  return fetchJson(
    `/api/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}/readiness`,
  )
}

export function validateStock(symbol) {
  return fetchJson(
    `/api/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}/validate`,
    {
      method: 'POST',
    },
  )
}

export function fetchStockScanner() {
  return fetchJson('/api/stocks/scanner')
}

// ---------------------------------------------------------------------------
// Sector API
// ---------------------------------------------------------------------------

export function fetchSectors() {
  return fetchJson('/api/sectors')
}

export function fetchSector(name) {
  return fetchJson(
    `/api/sectors/${encodeURIComponent(name.trim())}`,
  )
}

export function createSector(name, description = '') {
  return fetchJson('/api/sectors', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      name: name.trim(),
      description: description.trim(),
    }),
  })
}

export function deleteSector(name) {
  return fetchJson(
    `/api/sectors/${encodeURIComponent(name.trim())}`,
    {
      method: 'DELETE',
    },
  )
}

export function addStockToSector(sectorName, symbol) {
  return fetchJson(
    `/api/sectors/${encodeURIComponent(sectorName.trim())}/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}`,
    {
      method: 'POST',
    },
  )
}

export function removeStockFromSector(sectorName, symbol) {
  return fetchJson(
    `/api/sectors/${encodeURIComponent(sectorName.trim())}/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}`,
    {
      method: 'DELETE',
    },
  )
}

export function fetchSectorStocks(sectorName, search = '') {
  const query = search.trim()

  if (!query) {
    return fetchJson(
      `/api/sectors/${encodeURIComponent(sectorName.trim())}/stocks`,
    )
  }

  return fetchJson(
    `/api/sectors/${encodeURIComponent(sectorName.trim())}/stocks?search=${encodeURIComponent(query)}`,
  )
}

// ---------------------------------------------------------------------------
// Watchlist API
// ---------------------------------------------------------------------------

export function fetchWatchlists() {
  return fetchJson('/api/watchlists')
}

export function fetchWatchlist(name) {
  return fetchJson(
    `/api/watchlists/${encodeURIComponent(name.trim())}`,
  )
}

export function createWatchlist(name, description = '') {
  return fetchJson('/api/watchlists', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      name: name.trim(),
      description: description.trim(),
    }),
  })
}

export function deleteWatchlist(name) {
  return fetchJson(
    `/api/watchlists/${encodeURIComponent(name.trim())}`,
    {
      method: 'DELETE',
    },
  )
}

export function addStockToWatchlist(watchlistName, symbol) {
  return fetchJson(
    `/api/watchlists/${encodeURIComponent(watchlistName.trim())}/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}`,
    {
      method: 'POST',
    },
  )
}

export function removeStockFromWatchlist(watchlistName, symbol) {
  return fetchJson(
    `/api/watchlists/${encodeURIComponent(watchlistName.trim())}/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}`,
    {
      method: 'DELETE',
    },
  )
}

export function fetchWatchlistStocks(watchlistName, search = '') {
  const query = search.trim()

  if (!query) {
    return fetchJson(
      `/api/watchlists/${encodeURIComponent(watchlistName.trim())}/stocks`,
    )
  }

  return fetchJson(
    `/api/watchlists/${encodeURIComponent(watchlistName.trim())}/stocks?search=${encodeURIComponent(query)}`,
  )
}

// ---------------------------------------------------------------------------
// Paper Trading API (Phase 17 Interactive + Legacy Replay)
// ---------------------------------------------------------------------------

export function fetchPaperTradingStatus() {
  return fetchJson('/api/paper-trading/status')
}

export function fetchPaperTradingReport() {
  return fetchJson('/api/paper-trading/report')
}

export function fetchPaperTradingTrades(params = {}) {
  const query = new URLSearchParams()
  if (params.symbol) query.append('symbol', params.symbol)
  if (params.side) query.append('side', params.side)
  if (params.timeframe) query.append('timeframe', params.timeframe)
  if (params.status) query.append('status', params.status)
  const qs = query.toString()
  return fetchJson(`/api/paper-trading/trades${qs ? `?${qs}` : ''}`)
}

export function fetchOpenPaperTrades() {
  return fetchJson('/api/paper-trading/open')
}

export function fetchPaperTrade(tradeId) {
  return fetchJson(`/api/paper-trading/trades/${encodeURIComponent(tradeId)}`)
}

export function createPaperTrade(tradeData) {
  return fetchJson('/api/paper-trading/trades', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(tradeData),
  })
}

export function updatePaperTrade(tradeId, updateData) {
  return fetchJson(`/api/paper-trading/trades/${encodeURIComponent(tradeId)}/update`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updateData),
  })
}

export function closePaperTrade(tradeId, closeData = {}) {
  return fetchJson(`/api/paper-trading/trades/${encodeURIComponent(tradeId)}/close`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(closeData),
  })
}

export function fetchPaperTradingSummary() {
  return fetchJson('/api/paper-trading/summary')
}

export function startPaperTrading() {
  return fetchJson('/api/paper-trading/start', {
    method: 'POST',
  })
}

export function resetPaperTrading() {
  return fetchJson('/api/paper-trading/reset', {
    method: 'POST',
  })
}

// ---------------------------------------------------------------------------
// Market Intelligence & Opportunity Scoring API
// ---------------------------------------------------------------------------

export function fetchIntelligenceOverview() {
  return fetchJson('/api/intelligence/overview')
}

export function fetchScannedOpportunities(params = {}) {
  const query = new URLSearchParams()
  if (params.decision) query.append('decision', params.decision)
  if (params.bias) query.append('bias', params.bias)
  if (params.min_opportunity) query.append('min_opportunity', params.min_opportunity)

  const qs = query.toString()
  return fetchJson(`/api/intelligence${qs ? `?${qs}` : ''}`)
}

export function fetchSymbolIntelligence(symbol) {
  return fetchJson(`/api/intelligence/${encodeURIComponent(symbol)}`)
}

export function fetchSymbolExplanation(symbol) {
  return fetchJson(`/api/intelligence/${encodeURIComponent(symbol)}/explanation`)
}

export function fetchSymbolIntelligenceHistory(symbol, bars = 60, step = 5) {
  return fetchJson(`/api/intelligence/${encodeURIComponent(symbol)}/history?bars=${bars}&step=${step}`)
}

// ---------------------------------------------------------------------------
// Stock Universe & Qualification Gate API (Phase 24E)
// ---------------------------------------------------------------------------

export function fetchUniverseStocks(category = null, search = '') {
  const params = new URLSearchParams()
  if (category && category !== 'ALL') {
    params.append('category', category)
  }
  if (search && search.trim()) {
    params.append('q', search.trim())
  }
  const qs = params.toString()
  return fetchJson(`/api/universe/stocks${qs ? `?${qs}` : ''}`)
}

export function fetchUniverseStock(symbol) {
  return fetchJson(`/api/universe/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}`)
}

export function addUniverseStock(stock) {
  return fetchJson('/api/universe/stocks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      symbol: stock.symbol.trim().toUpperCase(),
      exchange: stock.exchange ? stock.exchange.trim().toUpperCase() : 'NSE',
      category: stock.category,
      name: stock.name && stock.name.trim() ? stock.name.trim() : null,
    }),
  })
}

export function fetchStockQualifications(symbol) {
  return fetchJson(`/api/universe/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}/qualifications`)
}

export function fetchStockQualification(symbol, strategyId) {
  return fetchJson(
    `/api/universe/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}/qualifications/${encodeURIComponent(strategyId.trim())}`
  )
}

export function updateStockQualification(symbol, strategyId, data) {
  return fetchJson(
    `/api/universe/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}/qualifications/${encodeURIComponent(strategyId.trim())}`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  )
}

export function fetchUniverseStockReadiness(symbol, strategyId = 'SignalForge_V1') {
  return fetchJson(
    `/api/universe/stocks/${encodeURIComponent(symbol.trim().toUpperCase())}/readiness?strategy_id=${encodeURIComponent(strategyId.trim())}`
  )
}

export function fetchUniverseReadinessSummary(strategyId = 'SignalForge_V1') {
  return fetchJson(
    `/api/universe/stocks/readiness/summary?strategy_id=${encodeURIComponent(strategyId.trim())}`
  )
}

export function runBacktest(params = {}) {
  return fetchJson('/api/strategy/backtest/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  })
}

export function fetchBacktestJobStatus(jobId) {
  return fetchJson(`/api/strategy/backtest/jobs/${encodeURIComponent(jobId)}`)
}

export function fetchBacktestJobResult(jobId) {
  return fetchJson(`/api/strategy/backtest/jobs/${encodeURIComponent(jobId)}/result`)
}

export function cancelBacktestJob(jobId) {
  return fetchJson(`/api/strategy/backtest/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  })
}

export function listBacktestJobs() {
  return fetchJson('/api/strategy/backtest/jobs')
}

export function fetchBacktestAnalytics(jobId) {
  return fetchJson(`/api/strategy/backtest/jobs/${encodeURIComponent(jobId)}/analytics`)
}

export function getBacktestTearsheetUrl(jobId, download = false) {
  return `/api/strategy/backtest/jobs/${encodeURIComponent(jobId)}/tearsheet${download ? '?download=true' : ''}`
}



