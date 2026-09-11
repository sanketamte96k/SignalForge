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

export function fetchNiftySignal() {
  return fetchJson('/api/nifty/signal')
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
// Paper Trading API
// ---------------------------------------------------------------------------

export function fetchPaperTradingStatus() {
  return fetchJson('/api/paper-trading/status')
}

export function fetchPaperTradingReport() {
  return fetchJson('/api/paper-trading/report')
}

export function fetchPaperTradingTrades() {
  return fetchJson('/api/paper-trading/trades')
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
