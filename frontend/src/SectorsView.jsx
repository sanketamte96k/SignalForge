import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  addStockToSector,
  createSector,
  deleteSector,
  removeStockFromSector,
  searchStocks,
  fetchSectors,
} from './api'
import './SectorsView.css'
import { LoadingState, EmptyState } from './StateViews'
import { useToast } from './useToast'
import { sanitizeErrorMessage } from './stateUtils'

function SectorsView() {
  const toast = useToast()
  const [sectors, setSectors] = useState([])
  const [selectedSector, setSelectedSector] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState(null)

  const [newSectorName, setNewSectorName] = useState('')
  const [newSectorDescription, setNewSectorDescription] = useState('')

  const [stockSearch, setStockSearch] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)

  const loadSectors = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await fetchSectors()
      const nextSectors = data.sectors ?? []

      setSectors(nextSectors)

      setSelectedSector((current) => {
        if (!nextSectors.length) {
          return null
        }

        if (!current) {
          return nextSectors[0]
        }

        return (
          nextSectors.find((sector) => sector.name === current.name) ??
          nextSectors[0]
        )
      })
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to load sectors.',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadSectors()
    }, 0)

    return () => window.clearTimeout(timer)
  }, [loadSectors])

  const selectedSymbols = useMemo(
    () => new Set(selectedSector?.symbols ?? []),
    [selectedSector],
  )

  async function handleCreateSector(event) {
    event.preventDefault()

    const name = newSectorName.trim()

    if (!name) {
      setError('Enter a sector name.')
      return
    }

    setActionLoading(true)
    setError(null)

    try {
      const sector = await createSector(
        name,
        newSectorDescription.trim(),
      )

      setNewSectorName('')
      setNewSectorDescription('')
      setSectors((current) => [...current, sector])
      setSelectedSector(sector)
      toast.success(`Sector "${name}" created.`)
    } catch (requestError) {
      const msg = sanitizeErrorMessage(requestError, 'Unable to create sector.')
      setError(msg)
      toast.error(msg)
    } finally {
      setActionLoading(false)
    }
  }

  async function handleDeleteSector() {
    if (!selectedSector) {
      return
    }

    const confirmed = window.confirm(
      `Delete the "${selectedSector.name}" sector?`,
    )

    if (!confirmed) {
      return
    }

    setActionLoading(true)
    setError(null)

    try {
      const deletedName = selectedSector.name
      await deleteSector(deletedName)

      const remaining = sectors.filter(
        (sector) => sector.name !== deletedName,
      )

      setSectors(remaining)
      setSelectedSector(remaining[0] ?? null)
      toast.success(`Sector "${deletedName}" deleted.`)
    } catch (requestError) {
      const msg = sanitizeErrorMessage(requestError, 'Unable to delete sector.')
      setError(msg)
      toast.error(msg)
    } finally {
      setActionLoading(false)
    }
  }

  async function handleSearchStocks(event) {
    const query = event.target.value
    setStockSearch(query)

    const normalized = query.trim()

    if (!normalized) {
      setSearchResults([])
      return
    }

    setSearchLoading(true)

    try {
      const data = await searchStocks(normalized)
      setSearchResults(data.results ?? [])
    } catch (requestError) {
      setSearchResults([])
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to search stocks.',
      )
    } finally {
      setSearchLoading(false)
    }
  }

  async function handleAddStock(symbol) {
    if (!selectedSector) {
      return
    }

    if (selectedSymbols.has(symbol)) {
      return
    }

    setActionLoading(true)
    setError(null)

    try {
      const updatedSector = await addStockToSector(
        selectedSector.name,
        symbol,
      )

      setSectors((current) =>
        current.map((sector) =>
          sector.name === updatedSector.name
            ? updatedSector
            : sector,
        ),
      )

      setSelectedSector(updatedSector)
      setStockSearch('')
      setSearchResults([])
      toast.success(`${symbol} added to "${selectedSector.name}".`)
    } catch (requestError) {
      const msg = sanitizeErrorMessage(requestError, 'Unable to add stock.')
      setError(msg)
      toast.error(msg)
    } finally {
      setActionLoading(false)
    }
  }

  async function handleRemoveStock(symbol) {
    if (!selectedSector) {
      return
    }

    setActionLoading(true)
    setError(null)

    try {
      const updatedSector = await removeStockFromSector(
        selectedSector.name,
        symbol,
      )

      setSectors((current) =>
        current.map((sector) =>
          sector.name === updatedSector.name
            ? updatedSector
            : sector,
        ),
      )

      setSelectedSector(updatedSector)
      toast.success(`${symbol} removed from "${selectedSector.name}".`)
    } catch (requestError) {
      const msg = sanitizeErrorMessage(requestError, 'Unable to remove stock.')
      setError(msg)
      toast.error(msg)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="sectors-view">
      <div className="sectors-page-header">
        <div>
          <span className="sectors-kicker">UNIVERSE MANAGEMENT</span>
          <h1>Sectors</h1>
          <p>
            Create custom stock groups and manage the instruments
            assigned to each sector.
          </p>
        </div>

        <div className="sectors-summary">
          <div className="sectors-summary-item">
            <strong>{sectors.length}</strong>
            <span>SECTORS</span>
          </div>

          <div className="sectors-summary-divider" />

          <div className="sectors-summary-item">
            <strong>{selectedSector?.symbols.length ?? 0}</strong>
            <span>STOCKS</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="sectors-error" role="alert">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      <div className="sectors-layout">
        <section className="panel sectors-list-panel">
          <div className="sectors-panel-header">
            <div>
              <span className="sectors-section-label">CUSTOM GROUPS</span>
              <h2>Your Sectors</h2>
            </div>
          </div>

          <form
            className="create-sector-form"
            onSubmit={handleCreateSector}
          >
            <input
              type="text"
              value={newSectorName}
              onChange={(event) =>
                setNewSectorName(event.target.value)
              }
              placeholder="Sector name"
              maxLength={80}
              disabled={actionLoading}
            />

            <input
              type="text"
              value={newSectorDescription}
              onChange={(event) =>
                setNewSectorDescription(event.target.value)
              }
              placeholder="Description (optional)"
              maxLength={160}
              disabled={actionLoading}
            />

            <button
              type="submit"
              className="primary-sector-button"
              disabled={actionLoading}
            >
              + Create Sector
            </button>
          </form>

          {loading ? (
            <LoadingState
              compact
              title="Loading Sectors..."
              description="Fetching custom sector groups..."
            />
          ) : sectors.length === 0 ? (
            <EmptyState
              compact
              title="No Custom Sectors Yet"
              description="Create your first sector above to organize stocks."
            />
          ) : (
            <div className="sector-cards">
              {sectors.map((sector) => (
                <button
                  type="button"
                  key={sector.name}
                  className={`sector-card ${
                    selectedSector?.name === sector.name
                      ? 'selected'
                      : ''
                  }`}
                  onClick={() => setSelectedSector(sector)}
                >
                  <span className="sector-card-icon">◈</span>

                  <span className="sector-card-content">
                    <strong>{sector.name}</strong>

                    {sector.description && (
                      <small>{sector.description}</small>
                    )}

                    <span>
                      {sector.symbols.length}{' '}
                      {sector.symbols.length === 1
                        ? 'stock'
                        : 'stocks'}
                    </span>
                  </span>

                  <span className="sector-card-arrow">›</span>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="panel sector-detail-panel">
          {!selectedSector ? (
            <div className="sector-detail-empty">
              <div className="sector-empty-icon">◈</div>
              <h2>Select a sector</h2>
              <p>
                Choose a sector from the left or create a new one
                to manage its stocks.
              </p>
            </div>
          ) : (
            <>
              <div className="sector-detail-header">
                <div>
                  <span className="sectors-section-label">
                    SELECTED SECTOR
                  </span>

                  <h2>{selectedSector.name}</h2>

                  {selectedSector.description && (
                    <p>{selectedSector.description}</p>
                  )}
                </div>

                <button
                  type="button"
                  className="danger-sector-button"
                  onClick={handleDeleteSector}
                  disabled={actionLoading}
                >
                  Delete
                </button>
              </div>

              <div className="sector-stock-manager">
                <div className="sector-stock-manager-header">
                  <div>
                    <span className="sectors-section-label">
                      ADD STOCK
                    </span>
                    <h3>Add an instrument</h3>
                  </div>

                  <span className="stock-count-badge">
                    {selectedSector.symbols.length} stocks
                  </span>
                </div>

                <div className="stock-search-box">
                  <input
                    type="search"
                    value={stockSearch}
                    onChange={handleSearchStocks}
                    placeholder="Search NSE stock by symbol or name..."
                    disabled={actionLoading}
                  />
                </div>

                {searchLoading && (
                  <div className="stock-search-status">
                    Searching...
                  </div>
                )}

                {!searchLoading && searchResults.length > 0 && (
                  <div className="stock-search-results">
                    {searchResults.map((stock) => {
                      const alreadyAdded = selectedSymbols.has(
                        stock.symbol,
                      )

                      return (
                        <div
                          className="stock-search-result"
                          key={stock.symbol}
                        >
                          <div>
                            <strong>{stock.symbol}</strong>
                            <span>{stock.name}</span>
                          </div>

                          <div className="stock-search-meta">
                            <small>{stock.exchange}</small>

                            <button
                              type="button"
                              onClick={() =>
                                handleAddStock(stock.symbol)
                              }
                              disabled={
                                alreadyAdded || actionLoading
                              }
                            >
                              {alreadyAdded ? 'Added' : 'Add'}
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}

                {!searchLoading &&
                  stockSearch.trim() &&
                  searchResults.length === 0 && (
                    <div className="stock-search-status">
                      No matching stocks found.
                    </div>
                  )}
              </div>

              <div className="sector-holdings">
                <div className="sector-holdings-header">
                  <div>
                    <span className="sectors-section-label">
                      HOLDINGS
                    </span>
                    <h3>Stocks in {selectedSector.name}</h3>
                  </div>
                </div>

                {selectedSector.symbols.length === 0 ? (
                  <div className="holdings-empty">
                    <strong>No stocks in this sector</strong>
                    <span>
                      Search above to add an NSE stock.
                    </span>
                  </div>
                ) : (
                  <div className="holdings-grid">
                    {selectedSector.symbols.map((symbol) => (
                      <div className="holding-row" key={symbol}>
                        <div className="holding-symbol">
                          <span className="holding-symbol-icon">
                            {symbol.slice(0, 1)}
                          </span>
                          <strong>{symbol}</strong>
                        </div>

                        <button
                          type="button"
                          className="remove-stock-button"
                          onClick={() =>
                            handleRemoveStock(symbol)
                          }
                          disabled={actionLoading}
                          aria-label={`Remove ${symbol}`}
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}

export default SectorsView
