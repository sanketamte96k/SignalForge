/**
 * SignalForge Trading Chart Utilities
 * Pure mathematical, formatting, and interaction helpers.
 */

export function calculateEmaSeries(values, period) {
  if (!Array.isArray(values) || values.length === 0 || period <= 0) {
    return []
  }

  const alpha = 2 / (period + 1)
  const series = new Array(values.length)
  let previous = Number(values[0])

  series[0] = Number.isFinite(previous) ? previous : null

  for (let index = 1; index < values.length; index += 1) {
    const value = Number(values[index])

    if (!Number.isFinite(value)) {
      series[index] = previous
      continue
    }

    previous = value * alpha + previous * (1 - alpha)
    series[index] = previous
  }

  return series
}

export function formatChartPrice(value, decimals = 2) {
  if (typeof value !== 'number' || Number.isNaN(value) || !Number.isFinite(value)) {
    return '—'
  }

  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

export function formatShortTime(timestamp) {
  if (!timestamp) return '—'
  let iso = String(timestamp).trim()
  if (!/[Z+-]\d{2}:?\d{2}$/.test(iso) && !iso.endsWith('Z')) {
    iso = `${iso}+05:30`
  }
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return String(timestamp)
  }
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    day: '2-digit',
    month: 'short',
    timeZone: 'Asia/Kolkata',
  }).format(date)
}

export function calculateCandleChange(candle) {
  if (!candle) return null
  const open = Number(candle.open)
  const close = Number(candle.close)
  if (!Number.isFinite(open) || !Number.isFinite(close) || open <= 0) {
    return null
  }
  const diff = close - open
  const pct = (diff / open) * 100
  const isUp = diff >= 0
  const sign = isUp ? '+' : ''
  return {
    diff,
    pct,
    isUp,
    text: `${sign}${diff.toFixed(2)} (${sign}${pct.toFixed(2)}%)`,
  }
}

export function calculateCrosshairPrice(mouseY, chartTop, chartBottom, minPrice, maxPrice) {
  const chartHeight = chartBottom - chartTop
  if (chartHeight <= 0 || maxPrice <= minPrice) return minPrice
  const clampedY = Math.max(chartTop, Math.min(chartBottom, mouseY))
  const ratio = (clampedY - chartTop) / chartHeight
  return maxPrice - ratio * (maxPrice - minPrice)
}

export function findCandleIndexAtX(mouseX, width, candleCount) {
  if (!candleCount || candleCount <= 0 || width <= 0) return 0
  const rawIndex = Math.floor((mouseX / width) * candleCount)
  return Math.max(0, Math.min(candleCount - 1, rawIndex))
}

export function calculateViewRange(totalCandles, currentRange, action, delta = 0) {
  if (!totalCandles || totalCandles <= 0) {
    return { start: 0, end: 0 }
  }

  const defaultWindow = Math.min(80, totalCandles)
  const minWindow = Math.min(15, totalCandles)

  if (!currentRange || action === 'reset') {
    return {
      start: Math.max(0, totalCandles - defaultWindow),
      end: totalCandles,
    }
  }

  let { start, end } = currentRange
  start = Math.max(0, Math.min(totalCandles - 1, start))
  end = Math.max(start + 1, Math.min(totalCandles, end))
  const currentSize = end - start

  if (action === 'zoomIn') {
    const zoomStep = Math.max(2, Math.round(currentSize * 0.2))
    const newSize = Math.max(minWindow, currentSize - zoomStep)
    const diff = currentSize - newSize
    const newStart = Math.min(end - newSize, start + diff)
    return {
      start: Math.max(0, newStart),
      end: end,
    }
  }

  if (action === 'zoomOut') {
    const zoomStep = Math.max(2, Math.round(currentSize * 0.25))
    const newSize = Math.min(totalCandles, currentSize + zoomStep)
    const diff = newSize - currentSize
    const newStart = Math.max(0, start - diff)
    return {
      start: newStart,
      end: Math.min(totalCandles, newStart + newSize),
    }
  }

  if (action === 'pan') {
    let newStart = start + delta
    let newEnd = end + delta
    if (newStart < 0) {
      newEnd -= newStart
      newStart = 0
    }
    if (newEnd > totalCandles) {
      newStart -= (newEnd - totalCandles)
      newEnd = totalCandles
    }
    newStart = Math.max(0, newStart)
    return { start: newStart, end: newEnd }
  }

  return { start, end }
}

export function matchSignalToCandle(signal, candles) {
  if (!signal || !Array.isArray(candles) || candles.length === 0) {
    return null
  }

  const signalType = signal.signal
  if (signalType !== 'BUY' && signalType !== 'SELL') {
    return null
  }

  if (signal.timestamp) {
    const signalTime = new Date(signal.timestamp).getTime()
    if (!Number.isNaN(signalTime)) {
      // Determine candle duration tolerance from adjacent candles or signal timeframe
      let toleranceMs = 60000
      if (candles.length >= 2) {
        const t0 = new Date(candles[0].timestamp).getTime()
        const t1 = new Date(candles[1].timestamp).getTime()
        if (!Number.isNaN(t0) && !Number.isNaN(t1)) {
          const delta = Math.abs(t1 - t0)
          if (delta > 0 && delta <= 24 * 3600 * 1000) {
            toleranceMs = Math.max(toleranceMs, delta)
          }
        }
      } else if (signal.timeframe) {
        const tf = String(signal.timeframe).toLowerCase()
        const match = tf.match(/^(\d+)([mhd])$/)
        if (match) {
          const val = parseInt(match[1], 10)
          const unit = match[2]
          const multiplier = unit === 'm' ? 60000 : unit === 'h' ? 3600000 : 86400000
          toleranceMs = Math.max(toleranceMs, val * multiplier)
        }
      }

      for (let i = candles.length - 1; i >= 0; i--) {
        const candleTime = new Date(candles[i].timestamp).getTime()
        if (!Number.isNaN(candleTime) && Math.abs(candleTime - signalTime) <= toleranceMs) {
          return { candle: candles[i], index: i, signal }
        }
      }
    }
  }

  // Strict safety: do not fall back to pinning off-screen or mismatched signals to lastIndex
  return null
}
