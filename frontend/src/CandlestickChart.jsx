import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './CandlestickChart.css'
import { LoadingState, ErrorState, EmptyState } from './StateViews'
import {
  calculateEmaSeries,
  formatChartPrice,
  formatShortTime,
  calculateCandleChange,
  calculateCrosshairPrice,
  findCandleIndexAtX,
  calculateViewRange,
  matchSignalToCandle,
} from './chartUtils'
import { formatAnalysisNumber, formatAnalysisPrice } from './analysisUtils'

const EMPTY_CANDLES = []

export function CandlestickChart({
  symbol = 'NIFTY 50',
  timeframe = '15m',
  signal = null,
  viewRange = null,
  onViewRangeChange = null,
  hoverIndex = null,
  onHoverChange = null,
}) {
  const [chartData, setChartData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [internalRange, setInternalRange] = useState(null)
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState(null)
  const [localHoverY, setLocalHoverY] = useState(null)
  const svgRef = useRef(null)

  const loadChart = useCallback(async () => {
    setLoading(true)
    setError(null)

    const supported = new Set(['1m', '5m', '10m', '15m', '30m'])
    if (!supported.has(timeframe)) {
      setChartData(null)
      setError(
        `${timeframe} chart is not available yet. Use 5m, 10m, 15m or 30m.`,
      )
      setLoading(false)
      return
    }

    try {
      const isNifty =
        !symbol ||
        symbol.toUpperCase() === 'NIFTY 50' ||
        symbol.toUpperCase() === 'NIFTY'

      const url = isNifty
        ? `/api/nifty/chart?timeframe=${encodeURIComponent(timeframe)}&limit=200`
        : `/api/stocks/${encodeURIComponent(symbol)}/chart?timeframe=${encodeURIComponent(timeframe)}&limit=200`

      const response = await fetch(url)

      if (!response.ok) {
        if (response.status === 404 && !isNifty) {
          // Clean handling when backend does not expose candle endpoints for individual stocks
          setChartData({ symbol, timeframe, candles: [] })
          setLoading(false)
          return
        }

        let message = `Chart API returned HTTP ${response.status}`
        try {
          const body = await response.json()
          if (body?.detail) {
            message = body.detail
          }
        } catch {
          // Keep the HTTP status message.
        }
        throw new Error(message)
      }

      const payload = await response.json()
      setChartData(payload)
    } catch (requestError) {
      setChartData(null)
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to load historical chart data.',
      )
    } finally {
      setLoading(false)
    }
  }, [timeframe, symbol])

  useEffect(() => {
    Promise.resolve().then(() => {
      loadChart()
    })
  }, [loadChart])

  // Global mouseup listener so dragging releases anywhere on page
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      setIsPanning(false)
      setPanStart(null)
    }
    window.addEventListener('mouseup', handleGlobalMouseUp)
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp)
    }
  }, [])

  const candles = useMemo(
    () => (Array.isArray(chartData?.candles) ? chartData.candles : EMPTY_CANDLES),
    [chartData?.candles],
  )

  const currentRange = useMemo(() => {
    if (viewRange && viewRange.end > viewRange.start) {
      return viewRange
    }
    if (internalRange && internalRange.end > internalRange.start) {
      return internalRange
    }
    return calculateViewRange(candles.length, null, 'reset')
  }, [viewRange, internalRange, candles.length])

  const updateRange = useCallback(
    (nextRange) => {
      if (onViewRangeChange) {
        onViewRangeChange(nextRange)
      } else {
        setInternalRange(nextRange)
      }
    },
    [onViewRangeChange],
  )

  const handleZoomIn = useCallback(() => {
    const next = calculateViewRange(candles.length, currentRange, 'zoomIn')
    updateRange(next)
  }, [candles.length, currentRange, updateRange])

  const handleZoomOut = useCallback(() => {
    const next = calculateViewRange(candles.length, currentRange, 'zoomOut')
    updateRange(next)
  }, [candles.length, currentRange, updateRange])

  const handleResetZoom = useCallback(() => {
    const next = calculateViewRange(candles.length, null, 'reset')
    updateRange(next)
  }, [candles.length, updateRange])

  const handleJumpToLatest = useCallback(() => {
    const next = calculateViewRange(candles.length, null, 'reset')
    updateRange(next)
  }, [candles.length, updateRange])



  const width = 780
  const height = 330
  const chartTop = 18
  const chartBottom = 252
  const volumeTop = 266
  const volumeBottom = 318
  const chartHeight = chartBottom - chartTop
  const volumeHeight = volumeBottom - volumeTop

  // ---------------------------------------------------------------------------
  // Memoized expensive derivations — these must NOT re-run on every hover
  // ---------------------------------------------------------------------------

  // Full EMA series over all candles (for accurate warm-up). Only recalculated
  // when the raw candle array changes (i.e. after a fresh API fetch).
  const { allEma20, allEma50 } = useMemo(() => {
    const closes = candles.map((c) => Number(c.close))
    return {
      allEma20: calculateEmaSeries(closes, 20),
      allEma50: calculateEmaSeries(closes, 50),
    }
  }, [candles])

  // Visible window + sliced indicator series — recalculated only when the view
  // range changes (zoom/pan), NOT on every mouse move.
  const { visibleCandles, ema20, ema50 } = useMemo(() => {
    const vc = candles.slice(currentRange.start, currentRange.end)
    return {
      visibleCandles: vc,
      ema20: allEma20.slice(currentRange.start, currentRange.end),
      ema50: allEma50.slice(currentRange.start, currentRange.end),
    }
  }, [candles, currentRange, allEma20, allEma50])

  const candleCount = visibleCandles.length || 1

  // Price/volume range + layout constants — recalculated only on range change.
  const { minPrice, maxPrice, priceRange, maxVolume, xStep, candleWidth } = useMemo(() => {
    const lows = visibleCandles.map((c) => Number(c.low))
    const highs = visibleCandles.map((c) => Number(c.high))
    const volumes = visibleCandles.map((c) => Number(c.volume) || 0)
    const validEma20 = ema20.filter(Number.isFinite)
    const validEma50 = ema50.filter(Number.isFinite)
    const allPrices = [...lows, ...highs, ...validEma20, ...validEma50]
    const mn = Math.min(...allPrices)
    const mx = Math.max(...allPrices)
    const pr = Math.max(mx - mn, 0.01)
    const mv = Math.max(...volumes, 1)
    const xs = width / candleCount
    const cw = Math.max(2, Math.min(10, xs * 0.65))
    return { minPrice: mn, maxPrice: mx, priceRange: pr, maxVolume: mv, xStep: xs, candleWidth: cw }
  }, [visibleCandles, ema20, ema50, candleCount])

  // yPrice is derived from minPrice/priceRange — stable when range is stable.
  const yPrice = useCallback(
    (price) => chartBottom - ((price - minPrice) / priceRange) * chartHeight,
    [minPrice, priceRange, chartHeight],
  )

  const gridRows = [0, 0.25, 0.5, 0.75, 1]

  const first = visibleCandles[0]
  const last = visibleCandles[visibleCandles.length - 1]
  const absoluteLastCandle = candles[candles.length - 1]
  const isPannedAway = candles.length > 0 && currentRange.end < candles.length
  const latestEma20 = ema20[ema20.length - 1]
  const latestEma50 = ema50[ema50.length - 1]

  // SVG path strings for EMA overlays — recalculated only when ema series or
  // layout constants change (not on mousemove).
  const { ema20Path, ema50Path } = useMemo(() => {
    const buildPath = (series) => {
      const pts = series
        .map((v, i) => {
          if (!Number.isFinite(v)) return null
          const x = i * xStep + xStep / 2
          const y = chartBottom - ((v - minPrice) / priceRange) * chartHeight
          return `${x.toFixed(2)},${y.toFixed(2)}`
        })
        .filter(Boolean)
      return pts.length > 0 ? `M${pts.join(' L')}` : ''
    }
    return { ema20Path: buildPath(ema20), ema50Path: buildPath(ema50) }
  }, [ema20, ema50, xStep, minPrice, priceRange, chartHeight])

  // Signal marker — memoized separately so hover doesn't recalculate timestamp matching.
  const matchedSignal = useMemo(
    () => matchSignalToCandle(signal, visibleCandles),
    [signal, visibleCandles],
  )

  // Active hover inspection
  const activeHoverOffset =
    hoverIndex !== null &&
      hoverIndex >= currentRange.start &&
      hoverIndex < currentRange.end
      ? hoverIndex - currentRange.start
      : null

  const activeHoverCandle =
    activeHoverOffset !== null ? visibleCandles[activeHoverOffset] : null

  // Crosshair coordinates
  const crosshairX =
    activeHoverOffset !== null
      ? activeHoverOffset * xStep + xStep / 2
      : null

  const crosshairY =
    localHoverY !== null
      ? Math.max(chartTop, Math.min(chartBottom, localHoverY))
      : activeHoverCandle
        ? yPrice(activeHoverCandle.close)
        : null

  const crosshairPrice =
    crosshairY !== null
      ? calculateCrosshairPrice(crosshairY, chartTop, chartBottom, minPrice, maxPrice)
      : null

  // ---------------------------------------------------------------------------
  // Stable event handlers — useCallback so SVG prop references don't change
  // on every render, preventing unnecessary DOM event re-attachment.
  // ---------------------------------------------------------------------------

  const handleMouseDown = useCallback((e) => {
    if (e.button !== 0) return
    setIsPanning(true)
    setPanStart({ x: e.clientX, range: { ...currentRange } })
  }, [currentRange])

  const handleMouseMove = useCallback((e) => {
    if (!svgRef.current || visibleCandles.length === 0) return
    const rect = svgRef.current.getBoundingClientRect()
    const mouseX = Math.max(0, Math.min(rect.width, e.clientX - rect.left))
    const mouseY = Math.max(0, Math.min(rect.height, e.clientY - rect.top))
    const scaledX = (mouseX / rect.width) * width
    const scaledY = (mouseY / rect.height) * height
    setLocalHoverY(scaledY)

    if (isPanning && panStart) {
      const dx = e.clientX - panStart.x
      const candleDelta = Math.round(
        (dx / rect.width) * (panStart.range.end - panStart.range.start),
      )
      const next = calculateViewRange(
        candles.length,
        panStart.range,
        'pan',
        -candleDelta,
      )
      updateRange(next)
      return
    }

    const idx = findCandleIndexAtX(scaledX, width, visibleCandles.length)
    const actualIndex = currentRange.start + idx
    const candle = visibleCandles[idx]
    if (onHoverChange) {
      onHoverChange(actualIndex, candle)
    }
  }, [visibleCandles, isPanning, panStart, candles.length, currentRange, onHoverChange, updateRange])

  const handleMouseLeave = useCallback(() => {
    if (!isPanning) {
      setPanStart(null)
    }
    setLocalHoverY(null)
    if (onHoverChange) {
      onHoverChange(null, null)
    }
  }, [isPanning, onHoverChange])

  const handleTouchStart = useCallback((e) => {
    if (e.touches.length === 1) {
      setIsPanning(true)
      setPanStart({ x: e.touches[0].clientX, range: { ...currentRange } })
    }
  }, [currentRange])

  const handleTouchMove = useCallback((e) => {
    if (!svgRef.current || visibleCandles.length === 0) return
    if (e.touches.length === 1 && panStart) {
      const rect = svgRef.current.getBoundingClientRect()
      const dx = e.touches[0].clientX - panStart.x
      const candleDelta = Math.round(
        (dx / rect.width) * (panStart.range.end - panStart.range.start),
      )
      const next = calculateViewRange(
        candles.length,
        panStart.range,
        'pan',
        -candleDelta,
      )
      updateRange(next)

      const mouseX = Math.max(0, Math.min(rect.width, e.touches[0].clientX - rect.left))
      const scaledX = (mouseX / rect.width) * width
      const idx = findCandleIndexAtX(scaledX, width, visibleCandles.length)
      const actualIndex = currentRange.start + idx
      const candle = visibleCandles[idx]
      if (onHoverChange) {
        onHoverChange(actualIndex, candle)
      }
    }
  }, [visibleCandles, panStart, candles.length, currentRange.start, onHoverChange, updateRange])

  const handleTouchEnd = useCallback(() => {
    setIsPanning(false)
    setPanStart(null)
    if (onHoverChange) {
      onHoverChange(null, null)
    }
  }, [onHoverChange])

  // Early returns after all hooks — rules-of-hooks compliant.
  if (loading && !chartData) {
    return (
      <LoadingState
        title={`Loading ${timeframe} historical candles for ${symbol}...`}
        description="Reading historical OHLCV data from the SignalForge chart API."
      />
    )
  }

  if (error && !chartData) {
    return (
      <ErrorState
        title="Chart Data Unavailable"
        message={error}
        onRetry={loadChart}
        retryLabel="Reload Chart"
      />
    )
  }

  if (candles.length === 0) {
    const isIndividualStock =
      symbol &&
      symbol.toUpperCase() !== 'NIFTY 50' &&
      symbol.toUpperCase() !== 'NIFTY'

    return (
      <EmptyState
        title={`No Candle Data Available for ${symbol}`}
        description={
          isIndividualStock
            ? `Intraday candlestick streaming is not yet configured for ${symbol}. Historical chart data is currently available for benchmark NIFTY 50.`
            : `No OHLCV records returned for the ${timeframe} timeframe.`
        }
        action={
          <button
            type="button"
            className="sf-state-retry-btn"
            onClick={loadChart}
          >
            Try Again
          </button>
        }
      />
    )
  }

  return (
    <div className="real-candlestick-chart">
      <div className="chart-data-header">
        {activeHoverCandle ? (
          <div className="chart-ohlc-hud" aria-live="polite">
            <span>{chartData?.symbol || symbol}</span>
            <span>{formatShortTime(activeHoverCandle.timestamp)}</span>
            <span>O <strong className="hud-val">{formatChartPrice(activeHoverCandle.open)}</strong></span>
            <span>H <strong className="hud-val">{formatChartPrice(activeHoverCandle.high)}</strong></span>
            <span>L <strong className="hud-val">{formatChartPrice(activeHoverCandle.low)}</strong></span>
            <span>C <strong className="hud-val">{formatChartPrice(activeHoverCandle.close)}</strong></span>
            {(() => {
              const chg = calculateCandleChange(activeHoverCandle)
              return chg ? (
                <span className={chg.isUp ? 'hud-up' : 'hud-down'}>
                  <strong>{chg.text}</strong>
                </span>
              ) : null
            })()}
            <span>Vol <strong className="hud-val">{Number(activeHoverCandle.volume || 0).toLocaleString('en-IN')}</strong></span>
          </div>
        ) : (
          <>
            <span>
              {chartData?.symbol || symbol} / {chartData?.timeframe || timeframe}
            </span>
            <span>{visibleCandles.length} candles visible</span>
            <span>
              EMA20 {formatAnalysisNumber(latestEma20)} | EMA50 {formatAnalysisNumber(latestEma50)}
            </span>
            <span>
              {formatShortTime(first?.timestamp)} - {formatShortTime(last?.timestamp)}
            </span>
          </>
        )}

        <div className="chart-zoom-controls">
          <button
            type="button"
            className="chart-zoom-btn"
            onClick={handleZoomIn}
            title="Zoom In (Ctrl+Scroll Up)"
            aria-label="Zoom in"
          >
            +
          </button>
          <button
            type="button"
            className="chart-zoom-btn"
            onClick={handleZoomOut}
            title="Zoom Out (Ctrl+Scroll Down)"
            aria-label="Zoom out"
          >
            −
          </button>
          <button
            type="button"
            className="chart-zoom-btn chart-zoom-reset"
            onClick={handleResetZoom}
            title="Reset Zoom Range"
            aria-label="Reset zoom range"
          >
            Reset
          </button>
          <button
            type="button"
            className="chart-zoom-btn chart-zoom-jump-latest"
            onClick={handleJumpToLatest}
            title="Jump to Latest Candle"
            aria-label="Jump to latest candle"
          >
            Jump to Latest
          </button>
        </div>
      </div>

      {isPannedAway && (
        <div className="chart-panned-notice">
          <span className="panned-text">
            Viewing: {formatShortTime(first?.timestamp)} – {formatShortTime(last?.timestamp)} | Latest available: {formatShortTime(absoluteLastCandle?.timestamp)}
          </span>
          <button
            type="button"
            className="panned-jump-btn"
            onClick={handleJumpToLatest}
          >
            Jump to Latest
          </button>
        </div>
      )}

      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`${chartData?.symbol || symbol} ${timeframe} interactive candlestick and volume chart`}
        className={isPanning ? 'is-dragging' : ''}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        <title>{`${chartData?.symbol || symbol} ${timeframe} Candlestick and Volume Chart`}</title>
        <desc>{`Interactive chart showing ${visibleCandles.length} candles from ${formatShortTime(first?.timestamp)} to ${formatShortTime(last?.timestamp)} with EMA 20, EMA 50, and volume.`}</desc>
        <rect
          x="0"
          y="0"
          width={width}
          height={height}
          className="chart-background"
        />

        <text
          x={width / 2}
          y={chartTop + chartHeight / 2}
          className="chart-watermark"
          textAnchor="middle"
          dominantBaseline="middle"
          fill="rgba(255, 255, 255, 0.06)"
          fontSize="24"
          fontWeight="700"
          letterSpacing="2px"
          pointerEvents="none"
        >
          HISTORICAL DATA • MARCH 2024
        </text>

        {gridRows.map((ratio) => {
          const y = chartTop + ratio * chartHeight
          const price = maxPrice - ratio * priceRange
          return (
            <g key={ratio}>
              <line
                x1="0"
                y1={y}
                x2={width}
                y2={y}
                className="chart-grid-line"
              />
              <text
                x={width - 8}
                y={y - 4}
                textAnchor="end"
                className="chart-price-label"
              >
                {formatChartPrice(price)}
              </text>
            </g>
          )
        })}

        <line
          x1="0"
          y1={volumeTop}
          x2={width}
          y2={volumeTop}
          className="chart-volume-separator"
        />

        {visibleCandles.map((candle, index) => {
          const x = index * xStep + (xStep - candleWidth) / 2
          const openY = yPrice(Number(candle.open))
          const closeY = yPrice(Number(candle.close))
          const highY = yPrice(Number(candle.high))
          const lowY = yPrice(Number(candle.low))
          const isUp = Number(candle.close) >= Number(candle.open)

          const bodyTop = Math.min(openY, closeY)
          const bodyHeight = Math.max(Math.abs(closeY - openY), 1.5)
          const wickX = x + candleWidth / 2

          const volumeValue = Number(candle.volume) || 0
          const barHeight = Math.max(
            (volumeValue / maxVolume) * volumeHeight,
            1,
          )
          const barY = volumeBottom - barHeight

          const isHovered = activeHoverOffset === index

          return (
            <g
              key={`${candle.timestamp}-${index}`}
              className={`candle-group ${isUp ? 'candle-up chart-candle-up' : 'candle-down chart-candle-down'} ${isHovered ? 'candle-hovered' : ''}`}
            >
              <line
                x1={wickX}
                y1={highY}
                x2={wickX}
                y2={lowY}
                className={`candle-wick ${isUp ? 'chart-candle-up' : 'chart-candle-down'}`}
                stroke={isUp ? '#00d9a3' : '#ff5f67'}
                strokeWidth="1"
              />
              <rect
                x={x}
                y={bodyTop}
                width={candleWidth}
                height={bodyHeight}
                rx={1}
                className={`candle-body ${isUp ? 'chart-candle-up' : 'chart-candle-down'}`}
                fill={isUp ? '#00d9a3' : '#ff5f67'}
                stroke={isUp ? '#00d9a3' : '#ff5f67'}
                strokeWidth="1"
              />
              <rect
                x={x}
                y={barY}
                width={candleWidth}
                height={barHeight}
                className="volume-bar chart-volume-bar"
                fill="rgba(99, 151, 190, 0.24)"
              />
            </g>
          )
        })}

        {ema20Path && (
          <path
            d={ema20Path}
            className="ema-line ema-20 chart-ema20"
            fill="none"
            stroke="#24a8ff"
            strokeWidth="1.8"
          />
        )}
        {ema50Path && (
          <path
            d={ema50Path}
            className="ema-line ema-50 chart-ema50"
            fill="none"
            stroke="#ffad42"
            strokeWidth="1.8"
          />
        )}

        {/* Signal Marker if matched to a candle */}
        {matchedSignal && (
          <g
            className={`chart-signal-marker signal-marker-${matchedSignal.isBuy ? 'buy' : 'sell'}`}
            role="note"
            aria-label={`${matchedSignal.type} signal at ${formatShortTime(matchedSignal.candle.timestamp)}`}
            transform={`translate(${matchedSignal.index * xStep + xStep / 2}, ${matchedSignal.isBuy
                ? yPrice(Number(matchedSignal.candle.low)) + 14
                : yPrice(Number(matchedSignal.candle.high)) - 14
              })`}
          >
            <circle r="6" className="marker-pin" />
            <polygon
              points={
                matchedSignal.isBuy
                  ? '-4,-2 4,-2 0,-8'
                  : '-4,2 4,2 0,8'
              }
              className="marker-arrow"
            />
            <text
              y={matchedSignal.isBuy ? 16 : -14}
              textAnchor="middle"
              className="marker-text"
            >
              {matchedSignal.type}
            </text>
          </g>
        )}

        {/* Synchronized Crosshair */}
        {crosshairX !== null && crosshairY !== null && (
          <g className="chart-crosshair-group" pointerEvents="none">
            <line
              x1={crosshairX}
              y1={chartTop}
              x2={crosshairX}
              y2={volumeBottom}
              className="chart-crosshair-v"
            />
            <line
              x1={0}
              y1={crosshairY}
              x2={width}
              y2={crosshairY}
              className="chart-crosshair-h"
            />
            {crosshairPrice !== null && (
              <>
                <rect
                  x={width - 64}
                  y={crosshairY - 9}
                  width={60}
                  height={18}
                  rx={3}
                  className="crosshair-badge"
                />
                <text
                  x={width - 34}
                  y={crosshairY + 4}
                  textAnchor="middle"
                  className="crosshair-badge-text"
                >
                  {formatChartPrice(crosshairPrice)}
                </text>
              </>
            )}
          </g>
        )}
      </svg>

      <div className="chart-data-footer">
        <span>Real OHLCV data</span>
        <span>EMA 20 / EMA 50 calculated from chart closes</span>
        {(chartData?.symbol === 'NIFTY 50' || symbol === 'NIFTY 50') && (
          <span className="nifty-spot-volume-note" title="Volume is zero for cash spot index; genuine trade volume is present on underlying equities and derivatives.">
            Note: Zero volume expected for NIFTY 50 cash spot index
          </span>
        )}
        <span>Latest: {formatAnalysisPrice(Number(last?.close))}</span>
      </div>
    </div>
  )
}

export function RsiChart({
  symbol = 'NIFTY 50',
  timeframe = '15m',
  viewRange = null,
  hoverIndex = null,
  onHoverChange = null,
}) {
  const [chartData, setChartData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const svgRef = useRef(null)

  const loadRsi = useCallback(async () => {
    setLoading(true)
    setError(null)

    const supported = new Set(['1m', '5m', '10m', '15m', '30m'])
    if (!supported.has(timeframe)) {
      setChartData(null)
      setError('RSI chart is not available for this timeframe yet.')
      setLoading(false)
      return
    }

    try {
      const isNifty =
        !symbol ||
        symbol.toUpperCase() === 'NIFTY 50' ||
        symbol.toUpperCase() === 'NIFTY'

      const url = isNifty
        ? `/api/nifty/chart?timeframe=${encodeURIComponent(timeframe)}&limit=200`
        : `/api/stocks/${encodeURIComponent(symbol)}/chart?timeframe=${encodeURIComponent(timeframe)}&limit=200`

      const response = await fetch(url)

      if (!response.ok) {
        if (response.status === 404 && !isNifty) {
          setChartData({ symbol, timeframe, candles: [] })
          setLoading(false)
          return
        }

        let message = `Chart API returned HTTP ${response.status}`
        try {
          const body = await response.json()
          if (body?.detail) {
            message = body.detail
          }
        } catch {
          // Keep the HTTP status message.
        }
        throw new Error(message)
      }

      const payload = await response.json()
      setChartData(payload)
    } catch (requestError) {
      setChartData(null)
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to load the real RSI series.',
      )
    } finally {
      setLoading(false)
    }
  }, [timeframe, symbol])

  useEffect(() => {
    Promise.resolve().then(() => {
      loadRsi()
    })
  }, [loadRsi])

  // ---------------------------------------------------------------------------
  // Derived state — all hooks before early returns (rules-of-hooks).
  // ---------------------------------------------------------------------------

  const candles = useMemo(
    () => (Array.isArray(chartData?.candles) ? chartData.candles : EMPTY_CANDLES),
    [chartData?.candles],
  )
  const candleCount = candles.length

  // currentRange: stable across hover; only changes on zoom/pan or data fetch.
  const currentRange = useMemo(() => {
    if (viewRange && viewRange.end > viewRange.start) {
      return viewRange
    }
    return calculateViewRange(candleCount, null, 'reset')
  }, [viewRange, candleCount])

  // Slice and map RSI — only recomputes on range/data change, not hover.
  const { visibleCandles, rsiSeries } = useMemo(() => {
    const vc = candles.slice(currentRange.start, currentRange.end)
    const rs = vc.map((c) => {
      const v = Number(c.rsi14)
      return Number.isFinite(v) ? v : null
    })
    return { visibleCandles: vc, rsiSeries: rs }
  }, [candles, currentRange])

  // Layout constants
  const width = 780
  const height = 96
  const chartTop = 10
  const chartBottom = 78
  const chartHeight = chartBottom - chartTop
  const xStep = width / Math.max(rsiSeries.length, 1)

  // Pure helper — closes only over compile-time constants, no hook needed.
  const yRsi = (value) =>
    chartBottom - (Math.max(0, Math.min(100, value)) / 100) * chartHeight

  // Memoize the RSI SVG path — avoids re-joining 200 points on every hover.
  const { rsiPath, latestRsi } = useMemo(() => {
    const pts = rsiSeries
      .map((v, i) => {
        if (!Number.isFinite(v)) return null
        const x = i * xStep + xStep / 2
        const y = chartBottom - (Math.max(0, Math.min(100, v)) / 100) * chartHeight
        return `${x.toFixed(2)},${y.toFixed(2)}`
      })
      .filter(Boolean)
    const path = pts.length > 0 ? `M${pts.join(' L')}` : ''
    const latest = [...rsiSeries].reverse().find((v) => Number.isFinite(v))
    return { rsiPath: path, latestRsi: latest }
  }, [rsiSeries, xStep, chartHeight])

  // Crosshair values derived from props — no hooks needed.
  const activeHoverOffset =
    hoverIndex !== null &&
      hoverIndex >= currentRange.start &&
      hoverIndex < currentRange.end
      ? hoverIndex - currentRange.start
      : null

  const hoveredRsiVal =
    activeHoverOffset !== null ? rsiSeries[activeHoverOffset] : null

  const crosshairX =
    activeHoverOffset !== null
      ? activeHoverOffset * xStep + xStep / 2
      : null

  // Stable handlers — defined before early returns.
  const handleMouseMove = useCallback((e) => {
    if (!svgRef.current || visibleCandles.length === 0) return
    const rect = svgRef.current.getBoundingClientRect()
    const mouseX = Math.max(0, Math.min(rect.width, e.clientX - rect.left))
    const scaledX = (mouseX / rect.width) * width
    const idx = findCandleIndexAtX(scaledX, width, visibleCandles.length)
    const actualIndex = currentRange.start + idx
    if (onHoverChange) {
      onHoverChange(actualIndex)
    }
  }, [visibleCandles.length, currentRange.start, onHoverChange])

  const handleMouseLeave = useCallback(() => {
    if (onHoverChange) {
      onHoverChange(null)
    }
  }, [onHoverChange])

  // Early returns — after all hooks.
  if (loading && !chartData) {
    return (
      <LoadingState
        compact
        title="Loading RSI (14) Series..."
        description={`Calculating indicator values for ${timeframe}...`}
      />
    )
  }

  if (error && !chartData) {
    return (
      <ErrorState
        compact
        title="RSI Unavailable"
        message={error}
        onRetry={loadRsi}
        retryLabel="Retry"
      />
    )
  }

  if (candleCount === 0) {
    return (
      <EmptyState
        compact
        title="No RSI Data"
        description={`No RSI indicator values available for ${symbol || 'this timeframe'}.`}
      />
    )
  }

  return (

    <div
      className="real-rsi-chart"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`${chartData?.symbol || symbol} ${timeframe} real RSI 14 indicator chart with synchronized crosshair`}
      >
        <title>{`${chartData?.symbol || symbol} ${timeframe} RSI 14 Indicator Chart`}</title>
        <desc>{`Real RSI(14) indicator series showing momentum levels with overbought band at 70 and oversold band at 30.`}</desc>
        <rect
          x="0"
          y="0"
          width={width}
          height={height}
          className="rsi-chart-background"
        />

        <rect
          x="0"
          y={yRsi(70)}
          width={width}
          height={yRsi(30) - yRsi(70)}
          className="rsi-neutral-band"
        />

        {[70, 50, 30].map((level) => (
          <g key={level}>
            <line
              x1="0"
              y1={yRsi(level)}
              x2={width}
              y2={yRsi(level)}
              className={`rsi-grid rsi-level-${level}`}
            />
            <text
              x="8"
              y={yRsi(level) - 3}
              className="rsi-level-label"
            >
              {level}
            </text>
          </g>
        ))}

        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((ratio) => {
          const x = ratio * width
          return (
            <line
              key={`rsi-v-${ratio}`}
              x1={x}
              y1="0"
              x2={x}
              y2={height}
              className="rsi-grid rsi-vertical-grid"
            />
          )
        })}

        {rsiPath && (
          <path
            d={rsiPath}
            className="rsi-series"
            fill="none"
            aria-label="RSI 14"
          />
        )}

        {/* Synchronized Crosshair */}
        {crosshairX !== null && (
          <g className="rsi-crosshair-group" pointerEvents="none">
            <line
              x1={crosshairX}
              y1={chartTop}
              x2={crosshairX}
              y2={chartBottom}
              className="rsi-crosshair-v"
            />
            {Number.isFinite(hoveredRsiVal) && (
              <>
                <line
                  x1={0}
                  y1={yRsi(hoveredRsiVal)}
                  x2={width}
                  y2={yRsi(hoveredRsiVal)}
                  className="rsi-crosshair-h"
                />
                <rect
                  x={width - 46}
                  y={yRsi(hoveredRsiVal) - 7}
                  width={42}
                  height={14}
                  rx={3}
                  className="rsi-crosshair-badge-val"
                />
                <text
                  x={width - 25}
                  y={yRsi(hoveredRsiVal) + 3}
                  textAnchor="middle"
                  className="rsi-crosshair-badge-text"
                >
                  {hoveredRsiVal.toFixed(1)}
                </text>
              </>
            )}
          </g>
        )}
      </svg>

      <div className="rsi-chart-meta">
        <span>REAL RSI(14) • BACKEND</span>
        <strong>
          {Number.isFinite(hoveredRsiVal)
            ? hoveredRsiVal.toFixed(2)
            : Number.isFinite(latestRsi)
              ? latestRsi.toFixed(2)
              : '—'}
        </strong>
      </div>
    </div>
  )
}
