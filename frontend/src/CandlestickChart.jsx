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

  const candles = Array.isArray(chartData?.candles) ? chartData.candles : []

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

  const width = 780
  const height = 330
  const chartTop = 18
  const chartBottom = 252
  const volumeTop = 266
  const volumeBottom = 318
  const chartHeight = chartBottom - chartTop
  const volumeHeight = volumeBottom - volumeTop

  // Visible window of candles
  const visibleCandles = candles.slice(currentRange.start, currentRange.end)
  const candleCount = visibleCandles.length || 1

  // Full history EMA series for accurate warm-up
  const allCloses = candles.map((candle) => Number(candle.close))
  const allEma20 = calculateEmaSeries(allCloses, 20)
  const allEma50 = calculateEmaSeries(allCloses, 50)

  const ema20 = allEma20.slice(currentRange.start, currentRange.end)
  const ema50 = allEma50.slice(currentRange.start, currentRange.end)

  const lows = visibleCandles.map((candle) => Number(candle.low))
  const highs = visibleCandles.map((candle) => Number(candle.high))
  const volumes = visibleCandles.map((candle) => Number(candle.volume) || 0)

  const validEma20 = ema20.filter((value) => Number.isFinite(value))
  const validEma50 = ema50.filter((value) => Number.isFinite(value))
  const allPrices = [
    ...lows,
    ...highs,
    ...validEma20,
    ...validEma50,
  ]

  const minPrice = Math.min(...allPrices)
  const maxPrice = Math.max(...allPrices)
  const priceRange = Math.max(maxPrice - minPrice, 0.01)
  const maxVolume = Math.max(...volumes, 1)

  const xStep = width / candleCount
  const candleWidth = Math.max(2, Math.min(10, xStep * 0.65))

  const yPrice = (price) =>
    chartBottom - ((price - minPrice) / priceRange) * chartHeight

  const gridRows = [0, 0.25, 0.5, 0.75, 1]

  const first = visibleCandles[0]
  const last = visibleCandles[visibleCandles.length - 1]
  const latestEma20 = ema20[ema20.length - 1]
  const latestEma50 = ema50[ema50.length - 1]

  const buildLinePath = (series) => {
    const points = series
      .map((value, index) => {
        if (!Number.isFinite(value)) {
          return null
        }

        const x = index * xStep + xStep / 2
        const y = yPrice(value)
        return `${x.toFixed(2)},${y.toFixed(2)}`
      })
      .filter(Boolean)

    return points.length > 0
      ? `M${points.join(' L')}`
      : ''
  }

  const ema20Path = buildLinePath(ema20)
  const ema50Path = buildLinePath(ema50)

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

  // Signal marker
  const matchedSignal = matchSignalToCandle(signal, visibleCandles)

  // Mouse & Touch interaction handlers
  const handleMouseDown = (e) => {
    if (e.button !== 0) return
    setIsPanning(true)
    setPanStart({ x: e.clientX, range: { ...currentRange } })
  }

  const handleMouseMove = (e) => {
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
  }

  const handleMouseLeave = () => {
    if (!isPanning) {
      setPanStart(null)
    }
    setLocalHoverY(null)
    if (onHoverChange) {
      onHoverChange(null, null)
    }
  }

  const handleTouchStart = (e) => {
    if (e.touches.length === 1) {
      setIsPanning(true)
      setPanStart({ x: e.touches[0].clientX, range: { ...currentRange } })
    }
  }

  const handleTouchMove = (e) => {
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
  }

  const handleTouchEnd = () => {
    setIsPanning(false)
    setPanStart(null)
    if (onHoverChange) {
      onHoverChange(null, null)
    }
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
        </div>
      </div>

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
        <rect
          x="0"
          y="0"
          width={width}
          height={height}
          className="chart-background"
        />

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
              className={`candle-group ${isUp ? 'candle-up' : 'candle-down'} ${isHovered ? 'candle-hovered' : ''}`}
            >
              <line
                x1={wickX}
                y1={highY}
                x2={wickX}
                y2={lowY}
                className="candle-wick"
              />
              <rect
                x={x}
                y={bodyTop}
                width={candleWidth}
                height={bodyHeight}
                rx={1}
                className="candle-body"
              />
              <rect
                x={x}
                y={barY}
                width={candleWidth}
                height={barHeight}
                className="volume-bar"
              />
            </g>
          )
        })}

        {ema20Path && <path d={ema20Path} className="ema-line ema-20" />}
        {ema50Path && <path d={ema50Path} className="ema-line ema-50" />}

        {/* Signal Marker if matched to a candle */}
        {matchedSignal && (
          <g
            className={`chart-signal-marker signal-marker-${matchedSignal.isBuy ? 'buy' : 'sell'}`}
            transform={`translate(${matchedSignal.index * xStep + xStep / 2}, ${
              matchedSignal.isBuy
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

  const candles = Array.isArray(chartData?.candles) ? chartData.candles : []

  const currentRange = useMemo(() => {
    if (viewRange && viewRange.end > viewRange.start) {
      return viewRange
    }
    return calculateViewRange(candles.length, null, 'reset')
  }, [viewRange, candles.length])

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

  if (candles.length === 0) {
    return (
      <EmptyState
        compact
        title="No RSI Data"
        description={`No RSI indicator values available for ${symbol || 'this timeframe'}.`}
      />
    )
  }

  const visibleCandles = candles.slice(currentRange.start, currentRange.end)
  const rsiSeries = visibleCandles.map((candle) => {
    const value = Number(candle.rsi14)
    return Number.isFinite(value) ? value : null
  })

  const width = 780
  const height = 96
  const chartTop = 10
  const chartBottom = 78
  const chartHeight = chartBottom - chartTop
  const xStep = width / Math.max(rsiSeries.length, 1)

  const yRsi = (value) =>
    chartBottom - (Math.max(0, Math.min(100, value)) / 100) * chartHeight

  const buildLinePath = (series) => {
    const points = series
      .map((value, index) => {
        if (!Number.isFinite(value)) {
          return null
        }

        const x = index * xStep + xStep / 2
        const y = yRsi(value)
        return `${x.toFixed(2)},${y.toFixed(2)}`
      })
      .filter(Boolean)

    return points.length > 0 ? `M${points.join(' L')}` : ''
  }

  const rsiPath = buildLinePath(rsiSeries)
  const latestRsi = [...rsiSeries].reverse().find((value) => Number.isFinite(value))

  // Synchronized hover crosshair
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

  const handleMouseMove = (e) => {
    if (!svgRef.current || visibleCandles.length === 0) return
    const rect = svgRef.current.getBoundingClientRect()
    const mouseX = Math.max(0, Math.min(rect.width, e.clientX - rect.left))
    const scaledX = (mouseX / rect.width) * width
    const idx = findCandleIndexAtX(scaledX, width, visibleCandles.length)
    const actualIndex = currentRange.start + idx
    if (onHoverChange) {
      onHoverChange(actualIndex)
    }
  }

  const handleMouseLeave = () => {
    if (onHoverChange) {
      onHoverChange(null)
    }
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
