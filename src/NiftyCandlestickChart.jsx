import "./NiftyCandlestickChart.css";
import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
} from "lightweight-charts";

const TIMEFRAMES = ["1m", "5m", "10m", "15m", "30m"];

function NiftyCandlestickChart() {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);

  const [timeframe, setTimeframe] = useState("5m");
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadChartData() {
      setLoading(true);
      setError("");

      try {
        const response = await fetch(
          `/api/nifty/chart?timeframe=${encodeURIComponent(
            timeframe,
          )}&limit=300`,
        );

        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(
            body.detail || `Chart request failed: ${response.status}`,
          );
        }

        const payload = await response.json();

        if (!cancelled) {
          setCandles(Array.isArray(payload.candles) ? payload.candles : []);
        }
      } catch (requestError) {
        if (!cancelled) {
          setCandles([]);
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Unable to load chart data.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadChartData();

    return () => {
      cancelled = true;
    };
  }, [timeframe]);

  useEffect(() => {
    if (!chartContainerRef.current) {
      return undefined;
    }

    const container = chartContainerRef.current;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 420,
      layout: {
        background: {
          type: ColorType.Solid,
          color: "transparent",
        },
        textColor: "#8f9bb3",
      },
      grid: {
        vertLines: {
          color: "rgba(143, 155, 179, 0.08)",
        },
        horzLines: {
          color: "rgba(143, 155, 179, 0.08)",
        },
      },
      rightPriceScale: {
        borderColor: "rgba(143, 155, 179, 0.18)",
      },
      timeScale: {
        borderColor: "rgba(143, 155, 179, 0.18)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: {
          color: "rgba(143, 155, 179, 0.35)",
        },
        horzLine: {
          color: "rgba(143, 155, 179, 0.35)",
        },
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];

      if (!entry) {
        return;
      }

      chart.applyOptions({
        width: entry.contentRect.width,
      });
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) {
      return;
    }

    const formattedCandles = candles
      .map((candle) => ({
        time: Math.floor(
          new Date(candle.timestamp).getTime() / 1000,
        ),
        open: Number(candle.open),
        high: Number(candle.high),
        low: Number(candle.low),
        close: Number(candle.close),
      }))
      .filter(
        (candle) =>
          Number.isFinite(candle.time) &&
          Number.isFinite(candle.open) &&
          Number.isFinite(candle.high) &&
          Number.isFinite(candle.low) &&
          Number.isFinite(candle.close),
      )
      .sort((a, b) => a.time - b.time);

    if (formattedCandles.length === 0) {
      seriesRef.current.setData([]);
      return;
    }

    const uniqueCandles = [];
    let lastTime = null;

    for (const candle of formattedCandles) {
      if (candle.time === lastTime) {
        uniqueCandles[uniqueCandles.length - 1] = candle;
      } else {
        uniqueCandles.push(candle);
        lastTime = candle.time;
      }
    }

    seriesRef.current.setData(uniqueCandles);

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [candles]);

  return (
    <section className="nifty-chart-card">
      <div className="nifty-chart-header">
        <div>
          <div className="nifty-chart-title-row">
            <h2>NIFTY 50</h2>
            <span className="nifty-chart-badge">INDEX</span>
          </div>
          <p>Price chart</p>
        </div>

        <div className="nifty-timeframe-selector">
          {TIMEFRAMES.map((value) => (
            <button
              key={value}
              type="button"
              className={
                timeframe === value
                  ? "nifty-timeframe active"
                  : "nifty-timeframe"
              }
              onClick={() => setTimeframe(value)}
              disabled={loading}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      <div className="nifty-chart-status">
        {loading && <span>Loading market data...</span>}

        {!loading && error && (
          <span className="nifty-chart-error">{error}</span>
        )}

        {!loading && !error && candles.length === 0 && (
          <span>No chart data available.</span>
        )}

        {!loading && !error && candles.length > 0 && (
          <span>
            {timeframe} • {candles.length} candles
          </span>
        )}
      </div>

      <div
        ref={chartContainerRef}
        className="nifty-chart-container"
      />
    </section>
  );
}

export default NiftyCandlestickChart;