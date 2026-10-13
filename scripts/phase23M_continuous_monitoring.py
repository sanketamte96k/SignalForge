import os
import time
import json
import logging
from datetime import datetime, timezone, time as datetime_time
import pandas as pd

from src.data.market_data import MarketDataRequest
from src.data.market_data_service import MarketDataService, ProviderUnavailableError
from src.data.providers.local import LocalProvider
from src.data.providers.groww import GrowwProvider
from src.data.providers.yfinance_provider import YFinanceProvider, YFinanceRateLimitError

from src.paper_trading.interactive_engine import InteractivePaperTradingService
from src.strategy.backtest_strategy import StrategyConfig, evaluate_timestamp, calculate_timeframe_indicators
from src.signals.signal_engine import Signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LiveScheduler:
    def __init__(self, data_service: MarketDataService, paper_service: InteractivePaperTradingService, symbols: list[str]):
        self.data_service = data_service
        self.paper_service = paper_service
        self.symbols = symbols
        self.config = StrategyConfig()
        
        # In-memory tracking of processed candles to prevent duplicate work during the same run
        self.last_processed_candle: dict[str, pd.Timestamp] = {}
        self.last_evaluated_1m_candle: dict[str, pd.Timestamp] = {}

    def get_latest_completed_15m_time(self) -> pd.Timestamp:
        """Get the expected latest completed 15m candle timestamp (naive IST)."""
        now = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)
        # Round down to nearest 15m
        latest_start = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        return latest_start - pd.Timedelta(minutes=15)

    def is_market_open(self) -> bool:
        """Check if current time is within NSE market hours (09:15 - 15:30 IST) on a weekday."""
        now_ist = pd.Timestamp.now(tz="Asia/Kolkata")
        if now_ist.weekday() >= 5: # 5=Sat, 6=Sun
            return False
            
        current_time = now_ist.time()
        market_open = datetime_time(9, 15)
        market_close = datetime_time(15, 30)
        
        return market_open <= current_time <= market_close

    def poll_once(self):
        expected_completed = self.get_latest_completed_15m_time()
        
        for symbol in self.symbols:
            active_trade = self.paper_service.get_active_trade(symbol, "15m")
            
            if not active_trade and symbol in self.last_processed_candle and self.last_processed_candle[symbol] >= expected_completed:
                logger.debug(f"Already processed 15m candle {expected_completed} for {symbol}. Skipping.")
                continue
                
            logger.info(f"Data fetch requested for {symbol}. Expected 15m candle: {expected_completed}. Active trade: {active_trade.trade_id if active_trade else 'None'}")
                
            max_retries = 3
            backoff = 5
            success = False
            
            for attempt in range(max_retries):
                try:
                    now = pd.Timestamp.now(tz="Asia/Kolkata")
                    start_date = (now - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
                    end_date = (now + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                    req = MarketDataRequest(symbol=symbol, interval="1m", start=start_date, end=end_date)
                    result = self.data_service.get_historical(req)
                    
                    df = result.data
                    if df.empty:
                        logger.warning(f"No data returned for {symbol}")
                        break
                        
                    if active_trade:
                        last_eval = self.last_evaluated_1m_candle.get(active_trade.trade_id)
                        
                        # Data Freshness Check
                        if not df.empty:
                            latest_candle_time = df.index[-1].tz_localize("Asia/Kolkata")
                            data_lag = now - latest_candle_time
                            
                            if data_lag > pd.Timedelta(minutes=5):
                                logger.warning(f"Data for {symbol} is stale! Lag: {data_lag}. Status: STALE/UNAVAILABLE. Current P&L is stale.")
                            else:
                                logger.info(f"Data for {symbol} is fresh. Lag: {data_lag}. Feed status: LIVE")
                        
                        # Feed all fresh uncompleted OHLC data chronologically
                        for ts, row in df.iterrows():
                            candle_time_ist = ts.tz_localize("Asia/Kolkata")
                            
                            if candle_time_ist.astimezone(timezone.utc) < active_trade.entry_timestamp:
                                continue
                                
                            if last_eval and candle_time_ist <= last_eval:
                                continue
                            
                            if active_trade.is_terminal:
                                logger.info(f"Trade {active_trade.trade_id} has already reached terminal state: {active_trade.status}")
                                break
                                
                            logger.info(f"New 1m candle detected for {symbol}: {candle_time_ist}. Evaluating open position...")
                            try:
                                updated_trade = self.paper_service.update_trade(
                                    trade_id=active_trade.trade_id,
                                    candle_open=float(row['Open']),
                                    candle_high=float(row['High']),
                                    candle_low=float(row['Low']),
                                    candle_close=float(row['Close']),
                                    timestamp=candle_time_ist
                                )
                                
                                self.last_evaluated_1m_candle[active_trade.trade_id] = candle_time_ist
                                active_trade = updated_trade
                                
                                if active_trade.is_terminal:
                                    logger.info(f"Exit processing complete: Trade {active_trade.trade_id} closed as {active_trade.status} at {active_trade.exit_price}")
                                else:
                                    # If lag is > 5 minutes, we already logged STALE above. The update is just for historical catch-up.
                                    logger.info(f"Unrealized P&L updated for {active_trade.trade_id}: {active_trade.unrealized_pnl:.2f} (Candle time: {candle_time_ist})")
                                    
                            except ValueError as ve:
                                if "Look-ahead violation" in str(ve):
                                    continue
                                logger.error(f"Trade update validation failed: {ve}")
                                
                        success = True
                        break
                        
                    # Enforce 1-trade-per-day rule by inspecting persisted trades
                    today = pd.Timestamp.now(tz="Asia/Kolkata").date()
                    has_traded_today = False
                    
                    all_trades = self.paper_service.list_trades(symbol=symbol)
                    for t in all_trades:
                        if t.entry_timestamp.date() == today:
                            has_traded_today = True
                            break
                            
                    if has_traded_today:
                        logger.info(f"Symbol {symbol} has already traded today. Enforcing 1-trade-per-day rule.")
                        self.last_processed_candle[symbol] = expected_completed
                        success = True
                        break

                    # Lowercase columns for legacy strategy engine
                    df.columns = [c.lower() for c in df.columns]
                    timeframe_data = calculate_timeframe_indicators(df, self.config)
                    signal_res = evaluate_timestamp(expected_completed, timeframe_data, self.config)
                    
                    if signal_res and signal_res.signal in (Signal.BUY, Signal.SELL):
                        logger.info(f"Signal {signal_res.signal} generated for {symbol} at {expected_completed}!")
                        
                        price = float(df.iloc[-1]['close']) 
                        side = "LONG" if signal_res.signal == Signal.BUY else "SHORT"
                        
                        atr = 5.0
                        sl = price - atr if side == "LONG" else price + atr
                        t1 = price + (atr * 2) if side == "LONG" else price - (atr * 2)
                        t2 = price + (atr * 3) if side == "LONG" else price - (atr * 3)
                        
                        try:
                            self.paper_service.create_trade(
                                symbol=symbol,
                                side=side,
                                timeframe="15m",
                                entry_price=price,
                                stop_loss=sl,
                                target_1=t1,
                                target_2=t2,
                                signal_timestamp=expected_completed.tz_localize("Asia/Kolkata"),
                                strategy_signal=signal_res.signal.value,
                            )
                        except (ValueError, KeyError) as ve:
                            logger.error(f"Trade validation failed for {symbol}: {ve}")
                            # Mark as processed so we don't infinitely retry deterministic validation failures
                            self.last_processed_candle[symbol] = expected_completed
                            success = True
                            break
                    
                    self.last_processed_candle[symbol] = expected_completed
                    success = True
                    break
                    
                except YFinanceRateLimitError:
                    logger.warning(f"Rate limited by Yahoo Finance. Backing off for {backoff} seconds...")
                    time.sleep(backoff)
                    backoff *= 2
                except Exception as e:
                    logger.error(f"Error polling {symbol}: {e}. Backing off for {backoff} seconds...")
                    time.sleep(backoff)
                    backoff *= 2
                    
            if not success:
                logger.error(f"Failed to fetch data for {symbol} after {max_retries} attempts.")
            
            time.sleep(1) # Stagger requests between symbols

    def run_continuous(self):
        logger.info("Starting continuous paper trading monitor...")
        try:
            while True:
                if self.is_market_open():
                    self.poll_once()
                    # Sleep for 1 minute before checking again
                    time.sleep(60)
                else:
                    logger.info("Outside market hours. Sleeping for 5 minutes...")
                    time.sleep(300)
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt. Shutting down gracefully.")

def main():
    out_dir = 'research/strategy_evolution_2018/phase23M_continuous_monitoring'
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Initialize Reversible Provider Selection
    providers = [
        LocalProvider(),
        GrowwProvider(),
        YFinanceProvider(drop_forming_candle=True)
    ]
    
    data_service = MarketDataService(providers=providers, default_provider="yfinance")
    paper_service = InteractivePaperTradingService(
        persistence_file=f"{out_dir}/interactive_trades.json",
        starting_capital=100000.0
    )
    
    symbols = ['HDFCBANK', 'ICICIBANK', 'INFY', 'RELIANCE']
    
    scheduler = LiveScheduler(data_service, paper_service, symbols)
    scheduler.run_continuous()

if __name__ == "__main__":
    main()
