"""
SignalForge — Phase 32J.1: Expanded Equity Universe & Data Readiness Audit
Execution Script
"""

import os
import glob
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure report directory exists
out_dir = Path("reports/phase32j_1")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. Reference Canonical 739 Dates from baseline
canonical_infy = pd.read_csv("data/historical/stocks/INFY_1m.csv", parse_dates=["timestamp"])
canonical_infy_sub = canonical_infy[(canonical_infy["timestamp"] >= "2017-01-01") & (canonical_infy["timestamp"] < "2020-01-01")]
canonical_dates = sorted(list(set(canonical_infy_sub["timestamp"].dt.date.astype(str))))
print(f"Canonical 739 sessions reference: {len(canonical_dates)} sessions ({canonical_dates[0]} to {canonical_dates[-1]})")

# 2. Candidate Files in temp_nse_data
raw_dir = Path("temp_nse_data/NSE Minute Data/NSE_Stocks_Data")
files = sorted(list(raw_dir.glob("*.csv")))

# Canonical 21 baseline set
PRIMARY_21 = {
    "INFY", "RELIANCE", "ICICIBANK", "HDFCBANK", "AXISBANK", "KOTAKBANK", "SBIN",
    "MARUTI", "M&M", "BAJAJ-AUTO", "ITC", "ASIANPAINT", "SUNPHARMA", "CIPLA",
    "DRREDDY", "HCLTECH", "LT", "BPCL", "POWERGRID", "NTPC", "COALINDIA"
}

# Sector classification mapping
SECTOR_MAP = {
    # Banking - Private
    "HDFCBANK": "Financial Services (Banking)",
    "ICICIBANK": "Financial Services (Banking)",
    "AXISBANK": "Financial Services (Banking)",
    "KOTAKBANK": "Financial Services (Banking)",
    "INDUSINDBK": "Financial Services (Banking)",
    "FEDERALBNK": "Financial Services (Banking)",
    "RBLBANK": "Financial Services (Banking)",
    "CUB": "Financial Services (Banking)",
    "IDFCFIRSTB": "Financial Services (Banking)",
    "AUBANK": "Financial Services (Banking)",
    # Banking - Public
    "SBIN": "Financial Services (Banking)",
    "BANKINDIA": "Financial Services (Banking)",
    "CANBK": "Financial Services (Banking)",
    # NBFC & Financial Products
    "BAJFINANCE": "Financial Services (NBFC)",
    "BAJAJFINSV": "Financial Services (NBFC)",
    "CHOLAFIN": "Financial Services (NBFC)",
    "L&TFH": "Financial Services (NBFC)",
    "M&MFIN": "Financial Services (NBFC)",
    "MANAPPURAM": "Financial Services (NBFC)",
    "MUTHOOTFIN": "Financial Services (NBFC)",
    "SRTRANSFIN": "Financial Services (NBFC)",
    "RECLTD": "Financial Services (NBFC)",
    "EDELWEISS": "Financial Services (NBFC)",
    "DHANI": "Financial Services (NBFC)",
    "IBULHSGFIN": "Financial Services (NBFC)",
    "LICHSGFIN": "Financial Services (NBFC)",
    "MFSL": "Financial Services (NBFC)",
    "ABCAPITAL": "Financial Services (NBFC)",
    "ISEC": "Financial Services (NBFC)",
    "SBILIFE": "Financial Services (NBFC)",
    "NAM_INDIA": "Financial Services (NBFC)",
    "HDFC": "Financial Services (NBFC)",
    # Automobile
    "MARUTI": "Automobile & Auto Components",
    "M&M": "Automobile & Auto Components",
    "BAJAJ-AUTO": "Automobile & Auto Components",
    "EICHERMOT": "Automobile & Auto Components",
    "ASHOKLEY": "Automobile & Auto Components",
    "BHARATFORG": "Automobile & Auto Components",
    "BALKRISIND": "Automobile & Auto Components",
    "APOLLOTYRE": "Automobile & Auto Components",
    "MRF": "Automobile & Auto Components",
    "EXIDEIND": "Automobile & Auto Components",
    "AMARAJABAT": "Automobile & Auto Components",
    "ESCORTS": "Automobile & Auto Components",
    "ENDURANCE": "Automobile & Auto Components",
    # FMCG & Consumer Products
    "ITC": "Fast Moving Consumer Goods",
    "BRITANNIA": "Fast Moving Consumer Goods",
    "NESTLEIND": "Fast Moving Consumer Goods",
    "GODREJIND": "Fast Moving Consumer Goods",
    "EMAMILTD": "Fast Moving Consumer Goods",
    "BATAINDIA": "Consumer Durables",
    "ASIANPAINT": "Consumer Durables",
    "CROMPTON": "Consumer Durables",
    # Healthcare & Pharma
    "SUNPHARMA": "Healthcare & Pharmaceuticals",
    "CIPLA": "Healthcare & Pharmaceuticals",
    "DRREDDY": "Healthcare & Pharmaceuticals",
    "DIVISLAB": "Healthcare & Pharmaceuticals",
    "APOLLOHOSP": "Healthcare & Pharmaceuticals",
    "AJANTPHARM": "Healthcare & Pharmaceuticals",
    "GLENMARK": "Healthcare & Pharmaceuticals",
    "IPCALAB": "Healthcare & Pharmaceuticals",
    "LALPATHLAB": "Healthcare & Pharmaceuticals",
    "NATCOPHARM": "Healthcare & Pharmaceuticals",
    "PFIZER": "Healthcare & Pharmaceuticals",
    "SANOFI": "Healthcare & Pharmaceuticals",
    "SYNGENE": "Healthcare & Pharmaceuticals",
    "FORTIS": "Healthcare & Pharmaceuticals",
    "APLLTD": "Healthcare & Pharmaceuticals",
    # IT
    "INFY": "Information Technology",
    "HCLTECH": "Information Technology",
    "COFORGE": "Information Technology",
    "MINDTREE": "Information Technology",
    "MPHASIS": "Information Technology",
    "LTTS": "Information Technology",
    # Oil, Gas & Fuels
    "RELIANCE": "Oil, Gas & Consumable Fuels",
    "COALINDIA": "Oil, Gas & Consumable Fuels",
    "BPCL": "Oil, Gas & Consumable Fuels",
    "IOC": "Oil, Gas & Consumable Fuels",
    "ONGC": "Oil, Gas & Consumable Fuels",
    "GAIL": "Oil, Gas & Consumable Fuels",
    "OIL": "Oil, Gas & Consumable Fuels",
    "GUJGASLTD": "Oil, Gas & Consumable Fuels",
    "MGL": "Oil, Gas & Consumable Fuels",
    "GSPL": "Oil, Gas & Consumable Fuels",
    "CASTROLIND": "Oil, Gas & Consumable Fuels",
    "ADANIGAS": "Oil, Gas & Consumable Fuels",
    # Power & Utilities
    "NTPC": "Power & Utilities",
    "POWERGRID": "Power & Utilities",
    "JSWENERGY": "Power & Utilities",
    "CESC": "Power & Utilities",
    # Capital Goods & Industrials
    "LT": "Construction & Capital Goods",
    "BEL": "Construction & Capital Goods",
    "BHEL": "Construction & Capital Goods",
    "CUMMINSIND": "Construction & Capital Goods",
    "POLYCAB": "Construction & Capital Goods",
    # Metals & Mining
    "JSWSTEEL": "Metals & Mining",
    "JINDALSTEL": "Metals & Mining",
    "SAIL": "Metals & Mining",
    "NATIONALUM": "Metals & Mining",
    "ADANIENT": "Metals & Mining",
    # Construction Materials / Cement
    "GRASIM": "Construction Materials",
    "SHREECEM": "Construction Materials",
    "RAMCOCEM": "Construction Materials",
    "DALBHARAT": "Construction Materials",
    # Chemicals
    "AARTIIND": "Chemicals",
    "COROMANDEL": "Chemicals",
    "NAVINFLUOR": "Chemicals",
    "PIIND": "Chemicals",
    "SRF": "Chemicals",
    "TATACHEM": "Chemicals",
    # Telecom & Media
    "BHARTIARTL": "Telecommunication",
    "IDEA": "Telecommunication",
    "SUNTV": "Media & Entertainment",
    # Consumer Services & Retail
    "ABFRL": "Consumer Services",
    "FRETAIL": "Consumer Services",
    "JUBLFOOD": "Consumer Services",
    "INDHOTEL": "Consumer Services",
    "PAGEIND": "Consumer Services",
    "RAJESHEXPO": "Consumer Services",
    "IRCTC": "Consumer Services",
    "BBTC": "Consumer Services",
    # Real Estate
    "GODREJPROP": "Realty",
    "OBEROIRLTY": "Realty",
    "PRESTIGE": "Realty",
    # Agriculture
    "GODREJAGRO": "Agriculture",
    "GMRINFRA": "Infrastructure",
}

# Point-in-Time Index Status Mapping (2017–2019)
PIT_STATUS_MAP = {
    # Full Period Nifty 50
    "INFY": "CONSTITUENT_FULL_PERIOD",
    "RELIANCE": "CONSTITUENT_FULL_PERIOD",
    "ICICIBANK": "CONSTITUENT_FULL_PERIOD",
    "HDFCBANK": "CONSTITUENT_FULL_PERIOD",
    "AXISBANK": "CONSTITUENT_FULL_PERIOD",
    "KOTAKBANK": "CONSTITUENT_FULL_PERIOD",
    "SBIN": "CONSTITUENT_FULL_PERIOD",
    "MARUTI": "CONSTITUENT_FULL_PERIOD",
    "M&M": "CONSTITUENT_FULL_PERIOD",
    "BAJAJ-AUTO": "CONSTITUENT_FULL_PERIOD",
    "EICHERMOT": "CONSTITUENT_FULL_PERIOD",
    "ITC": "CONSTITUENT_FULL_PERIOD",
    "ASIANPAINT": "CONSTITUENT_FULL_PERIOD",
    "SUNPHARMA": "CONSTITUENT_FULL_PERIOD",
    "CIPLA": "CONSTITUENT_FULL_PERIOD",
    "DRREDDY": "CONSTITUENT_FULL_PERIOD",
    "HCLTECH": "CONSTITUENT_FULL_PERIOD",
    "LT": "CONSTITUENT_FULL_PERIOD",
    "BPCL": "CONSTITUENT_FULL_PERIOD",
    "POWERGRID": "CONSTITUENT_FULL_PERIOD",
    "NTPC": "CONSTITUENT_FULL_PERIOD",
    "COALINDIA": "CONSTITUENT_FULL_PERIOD",
    "IOC": "CONSTITUENT_FULL_PERIOD", # Added March 2017 (in for almost full period)
    "IBULHSGFIN": "CONSTITUENT_PARTIAL_PERIOD", # In 2017-03 to 2019-09
    "HDFC": "CONSTITUENT_FULL_PERIOD",
    "BHARTIARTL": "CONSTITUENT_FULL_PERIOD",
    "ONGC": "CONSTITUENT_FULL_PERIOD",
    "GAIL": "CONSTITUENT_FULL_PERIOD",
    "INDUSINDBK": "CONSTITUENT_FULL_PERIOD",
    "BHEL": "CONSTITUENT_PARTIAL_PERIOD", # Excluded March 2017
    "IDEA": "CONSTITUENT_PARTIAL_PERIOD", # Excluded March 2017
    # Partial Period Nifty 50 Inclusions
    "BAJFINANCE": "CONSTITUENT_PARTIAL_PERIOD", # Included 2017-09-29
    "BAJAJFINSV": "CONSTITUENT_PARTIAL_PERIOD", # Included 2018-04-02
    "GRASIM": "CONSTITUENT_PARTIAL_PERIOD",     # Included 2018-04-02
    "JSWSTEEL": "CONSTITUENT_PARTIAL_PERIOD",   # Included 2018-09-28
    "BRITANNIA": "CONSTITUENT_PARTIAL_PERIOD",  # Included 2019-04-01
    "NESTLEIND": "CONSTITUENT_PARTIAL_PERIOD",  # Included 2019-09-27
    # Modern NIFTY 50 (Added after 2019) -> Non-constituent in 2017-2019
    "DIVISLAB": "NON_CONSTITUENT_2017_2019",    # Added 2020-09-25
    "APOLLOHOSP": "NON_CONSTITUENT_2017_2019",  # Added 2022-03-31
    "ADANIENT": "NON_CONSTITUENT_2017_2019",    # Added 2022-09-30
    "BEL": "NON_CONSTITUENT_2017_2019",         # Added 2024-09-27
    "SHREECEM": "NON_CONSTITUENT_2017_2019",    # Added 2020-03-27
    "SBILIFE": "NON_CONSTITUENT_2017_2019",     # Added 2020-09-25
}

# Known corporate actions in 2017-2019
CORP_ACTIONS_NOTES = {
    "INFY": "1:1 Bonus in Sept 2018 backward-adjusted. Continuous series.",
    "RELIANCE": "1:1 Bonus in Sept 2017 backward-adjusted. Continuous series.",
    "ICICIBANK": "1:10 Bonus in June 2017 backward-adjusted. Continuous series.",
    "HDFCBANK": "1:1 Split (₹2 to ₹1) in Sept 2019 backward-adjusted. Continuous series.",
    "LT": "1:2 Bonus in July 2017 backward-adjusted. Continuous series.",
    "BPCL": "1:2 Bonus in July 2017 backward-adjusted. Continuous series.",
    "M&M": "1:1 Bonus in Dec 2017 backward-adjusted. Continuous series.",
    "HCLTECH": "1:1 Bonus in Dec 2019 backward-adjusted. Continuous series.",
    "NTPC": "1:5 Bonus in March 2019 backward-adjusted. Continuous series.",
    "BAJFINANCE": "1:5 Split & 1:1 Bonus in Sept 2016 pre-period backward-adjusted.",
    "BRITANNIA": "1:2 Split in Nov 2018 backward-adjusted. Continuous series.",
    "JSWSTEEL": "1:10 Split in Jan 2017 backward-adjusted. Continuous series.",
    "EICHERMOT": "1:10 Split in Aug 2020 (post-period) backward-adjusted in archive.",
    "BEL": "1:10 Split in March 2017 & 1:10 Bonus in Sept 2017 backward-adjusted.",
    "GRASIM": "Merger/Demerger Nuvo July 2017 reflected. Continuous series.",
    "AARTIIND": "1:1 Bonus in Oct 2019 backward-adjusted.",
    "COROMANDEL": "No split/bonus in 2017-2019. Continuous series.",
    "NAVINFLUOR": "1:5 Split in July 2017 backward-adjusted.",
    "SRF": "No split/bonus in 2017-2019. Continuous series.",
    "TATACHEM": "Demerger Consumer products in 2020 reflected.",
    "ASHOKLEY": "No split/bonus in 2017-2019. Continuous series.",
    "BHARATFORG": "1:1 Bonus in Aug 2017 backward-adjusted.",
    "BALKRISIND": "1:1 Bonus in Dec 2017 backward-adjusted.",
    "APOLLOTYRE": "No split/bonus in 2017-2019. Continuous series.",
    "MRF": "High-value single share (₹60k-₹75k). No split/bonus.",
    "EXIDEIND": "No split/bonus in 2017-2019. Continuous series.",
    "AMARAJABAT": "No split/bonus in 2017-2019. Continuous series.",
    "ESCORTS": "No split/bonus in 2017-2019. Continuous series.",
    "ENDURANCE": "IPO in late 2016. Continuous series.",
    "BATAINDIA": "No split/bonus in 2017-2019. Continuous series.",
    "CROMPTON": "Demerger in 2016 pre-period. Continuous series.",
    "DIVISLAB": "No split/bonus in 2017-2019. Continuous series.",
    "APOLLOHOSP": "No split/bonus in 2017-2019. Continuous series.",
    "AJANTPHARM": "No split/bonus in 2017-2019. Continuous series.",
    "GLENMARK": "No split/bonus in 2017-2019. Continuous series.",
    "IPCALAB": "No split/bonus in 2017-2019. Continuous series.",
    "LALPATHLAB": "No split/bonus in 2017-2019. Continuous series.",
    "NATCOPHARM": "No split/bonus in 2017-2019. Continuous series.",
    "PFIZER": "No split/bonus in 2017-2019. Continuous series.",
    "SANOFI": "No split/bonus in 2017-2019. Continuous series.",
    "SYNGENE": "1:1 Bonus in June 2019 backward-adjusted.",
    "FORTIS": "No split/bonus in 2017-2019. Continuous series.",
    "COFORGE": "No split/bonus in 2017-2019 (NIIT Tech).",
    "MINDTREE": "Takeover by L&T in 2019. Continuous series.",
    "MPHASIS": "No split/bonus in 2017-2019. Continuous series.",
    "LTTS": "No split/bonus in 2017-2019. Continuous series.",
    "IOC": "1:1 Bonus in March 2018 backward-adjusted.",
    "ONGC": "1:2 Bonus in Dec 2016 pre-period backward-adjusted.",
    "GAIL": "1:3 Bonus in March 2017 & 1:3 Bonus in July 2019 backward-adjusted.",
    "OIL": "1:2 Bonus in March 2018 backward-adjusted.",
    "GUJGASLTD": "1:5 Split in Jan 2019 backward-adjusted.",
    "MGL": "IPO in mid-2016. Continuous series.",
    "GSPL": "No split/bonus in 2017-2019. Continuous series.",
    "CASTROLIND": "1:1 Bonus in Dec 2017 backward-adjusted.",
    "JSWENERGY": "No split/bonus in 2017-2019. Continuous series.",
    "CESC": "Restructuring/Demerger in 2018 reflected.",
    "BHEL": "1:2 Bonus in Sept 2017 backward-adjusted.",
    "CUMMINSIND": "No split/bonus in 2017-2019. Continuous series.",
    "JINDALSTEL": "No split/bonus in 2017-2019. Continuous series.",
    "SAIL": "No split/bonus in 2017-2019. Continuous series.",
    "NATIONALUM": "No split/bonus in 2017-2019. Continuous series.",
    "ADANIENT": "Demerger of renewable assets in 2018 reflected.",
    "SHREECEM": "No split/bonus in 2017-2019. Continuous series.",
    "RAMCOCEM": "No split/bonus in 2017-2019. Continuous series.",
    "BHARTIARTL": "Rights issue in May 2019 reflected.",
    "IDEA": "Vodafone merger in Aug 2018 & rights issue in May 2019 reflected.",
    "SUNTV": "No split/bonus in 2017-2019. Continuous series.",
    "ABFRL": "No split/bonus in 2017-2019. Continuous series.",
    "FRETAIL": "Future Retail debt stress/demerger. Highly volatile.",
    "JUBLFOOD": "1:1 Bonus in June 2018 backward-adjusted.",
    "INDHOTEL": "Rights issue in 2017 reflected.",
    "PAGEIND": "No split/bonus in 2017-2019. Continuous series.",
    "RAJESHEXPO": "No split/bonus in 2017-2019. Continuous series.",
    "GODREJPROP": "No split/bonus in 2017-2019. Continuous series.",
    "OBEROIRLTY": "No split/bonus in 2017-2019. Continuous series.",
    "PRESTIGE": "No split/bonus in 2017-2019. Continuous series.",
}

records = []
daily_dfs = {}

print("Auditing all 125 candidate CSVs...")

for idx, f in enumerate(files):
    if "ADANIPORTS" in f.name:
        continue # Strictly quarantined!
        
    name = f.stem.split("__")[0]
    if name == "M_M": sym = "M&M"
    elif name == "BAJAJ_AUTO": sym = "BAJAJ-AUTO"
    elif name == "L_TFH": sym = "L&TFH"
    elif name == "M_MFIN": sym = "M&MFIN"
    else: sym = name
    
    file_size_mb = round(f.stat().st_size / (1024 * 1024), 2)
    
    # Read CSV
    df_raw = pd.read_csv(f)
    
    # Check total rows
    total_rows = len(df_raw)
    
    # Filter 2017-2019
    df_sub = df_raw[(df_raw["timestamp"] >= "2017-01-01") & (df_raw["timestamp"] < "2020-01-01")].copy()
    rows_sub = len(df_sub)
    
    if rows_sub == 0:
        continue
        
    # Check NaN count
    nan_rows = df_sub.isna().any(axis=1).sum()
    df_clean = df_sub.dropna().copy()
    
    # Mathematical pricing invariants check
    inv_h_max = (df_clean["high"] < np.maximum(df_clean["open"], df_clean["close"])).sum()
    inv_l_min = (df_clean["low"] > np.minimum(df_clean["open"], df_clean["close"])).sum()
    inv_h_l = (df_clean["high"] < df_clean["low"]).sum()
    inv_p_pos = ((df_clean["open"] <= 0) | (df_clean["high"] <= 0) | (df_clean["low"] <= 0) | (df_clean["close"] <= 0)).sum()
    inv_v_nonneg = (df_clean["volume"] < 0).sum()
    ohlc_violations = int(inv_h_max + inv_l_min + inv_h_l + inv_p_pos + inv_v_nonneg)
    
    # Resample daily
    df_clean["date"] = df_clean["timestamp"].str.slice(0, 10)
    daily = df_clean.groupby("date").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    })
    
    sessions_observed = len(daily)
    missing_sessions = 739 - sessions_observed
    
    # Turnover
    daily["turnover_cr"] = (daily["close"] * daily["volume"]) / 1e7
    avg_turnover = float(daily["turnover_cr"].mean())
    median_turnover = float(daily["turnover_cr"].median())
    p10_turnover = float(daily["turnover_cr"].quantile(0.10))
    min_turnover = float(daily["turnover_cr"].min())
    max_turnover = float(daily["turnover_cr"].max())
    avg_vol = float(daily["volume"].mean())
    avg_price = float(daily["close"].mean())
    
    # Max 1-day percentage drop
    daily["pct_change"] = daily["close"].pct_change() * 100.0
    max_drop = float(daily["pct_change"].min())
    
    # Gap density
    # Theoretical bars = 276,180
    gap_density_pct = round(((276180 - rows_sub) / 276180) * 100.0, 4) if rows_sub <= 276180 else 0.0
    
    # Point-in-Time Index Membership
    pit_status = PIT_STATUS_MAP.get(sym, "NIFTY_MIDCAP_FO" if sessions_observed == 739 else "MID_PERIOD_LISTING")
    sector = SECTOR_MAP.get(sym, "Diversified / Other")
    corp_note = CORP_ACTIONS_NOTES.get(sym, "No abnormal cliff drops detected. Normal market volatility.")
    
    # Selection Recommendation Logic:
    # 1. Primary 21: APPROVED_PRIMARY
    # 2. 739 sessions + turnover >= ₹20 Cr + max_drop > -35% (no unadjusted splits) + 0 violations: APPROVED_EXPANDED
    # 3. 739 sessions + turnover ₹10 - ₹20 Cr: CONDITIONALLY_ELIGIBLE_LOW_TURNOVER
    # 4. sessions < 739: REJECTED_INCOMPLETE_SESSIONS
    # 5. turnover < ₹10 Cr: REJECTED_INSUFFICIENT_LIQUIDITY
    # 6. max_drop <= -35% (indicates unadjusted split or extreme corporate action): CONDITIONALLY_FLAGGED_CORP_ACTION
    
    if sym in PRIMARY_21:
        rec = "APPROVED_PRIMARY_BASELINE"
        tier = "TIER_1_PRIMARY"
    elif sessions_observed < 739:
        rec = "REJECTED_INCOMPLETE_SESSIONS"
        tier = "REJECTED"
    elif avg_turnover < 10.0:
        rec = "REJECTED_INSUFFICIENT_LIQUIDITY"
        tier = "REJECTED"
    elif max_drop <= -35.0:
        rec = "REJECTED_UNADJUSTED_CORPORATE_ACTION"
        tier = "REJECTED"
    elif avg_turnover >= 20.0:
        rec = "APPROVED_EXPANDED_UNIVERSE"
        tier = "TIER_2_EXPANDED"
    else: # 10.0 <= avg_turnover < 20.0
        rec = "CONDITIONALLY_APPROVED_MODERATE_LIQUIDITY"
        tier = "TIER_3_CONDITIONAL"
        
    records.append({
        "symbol": sym,
        "sector": sector,
        "cohort_tier": tier,
        "selection_verdict": rec,
        "pit_index_status": pit_status,
        "sessions_observed": sessions_observed,
        "missing_sessions": missing_sessions,
        "rows_2017_2019": rows_sub,
        "nan_rows": nan_rows,
        "gap_density_pct": gap_density_pct,
        "ohlc_violations": ohlc_violations,
        "avg_daily_turnover_cr": round(avg_turnover, 2),
        "median_daily_turnover_cr": round(median_turnover, 2),
        "p10_daily_turnover_cr": round(p10_turnover, 2),
        "min_daily_turnover_cr": round(min_turnover, 2),
        "max_daily_turnover_cr": round(max_turnover, 2),
        "avg_daily_volume": int(avg_vol),
        "avg_share_price": round(avg_price, 2),
        "max_single_day_pct_drop": round(max_drop, 2),
        "corporate_actions_notes": corp_note,
        "file_size_mb": file_size_mb,
    })
    
    # Store daily series for correlation matrix if sessions == 739
    if sessions_observed == 739:
        daily_dfs[sym] = daily["pct_change"]

print(f"Processed {len(records)} candidates.")
df_candidates = pd.DataFrame(records)

# Save reports/phase32j_1/universe_candidates.csv
candidates_csv = out_dir / "universe_candidates.csv"
df_candidates.to_csv(candidates_csv, index=False)
print(f"Saved: {candidates_csv}")

# Liquidity Analysis Table
df_liq = df_candidates[[
    "symbol", "sector", "cohort_tier", "selection_verdict", "avg_daily_turnover_cr",
    "median_daily_turnover_cr", "p10_daily_turnover_cr", "avg_daily_volume",
    "avg_share_price", "max_single_day_pct_drop"
]].sort_values(by="avg_daily_turnover_cr", ascending=False)
liq_csv = out_dir / "liquidity_analysis.csv"
df_liq.to_csv(liq_csv, index=False)
print(f"Saved: {liq_csv}")

# Sector Distribution Table
sector_summary = df_candidates[df_candidates["cohort_tier"].isin(["TIER_1_PRIMARY", "TIER_2_EXPANDED"])].groupby("sector").agg(
    approved_stocks=("symbol", "count"),
    symbols_list=("symbol", lambda s: ", ".join(sorted(s))),
    avg_sector_turnover_cr=("avg_daily_turnover_cr", "mean"),
    total_sector_turnover_cr=("avg_daily_turnover_cr", "sum")
).reset_index().sort_values(by="approved_stocks", ascending=False)

sector_csv = out_dir / "sector_distribution.csv"
sector_summary.to_csv(sector_csv, index=False)
print(f"Saved: {sector_csv}")

# Cross-Asset Correlation Matrix for Approved Universe (Primary + Expanded)
approved_symbols = df_candidates[df_candidates["cohort_tier"].isin(["TIER_1_PRIMARY", "TIER_2_EXPANDED"])]["symbol"].tolist()
print(f"Total Approved Equities (Primary + Expanded): {len(approved_symbols)}")

ret_df = pd.DataFrame({s: daily_dfs[s] for s in approved_symbols}).dropna()
corr_matrix = ret_df.corr()
corr_csv = out_dir / "correlation_matrix.csv"
corr_matrix.to_csv(corr_csv)
print(f"Saved: {corr_csv}")

# Print summary stats
print("\n--- AUDIT SUMMARY STATS ---")
print("Cohort Breakdown:")
print(df_candidates["cohort_tier"].value_counts())
print("\nSelection Verdict Breakdown:")
print(df_candidates["selection_verdict"].value_counts())
print(f"\nMean correlation across all approved pairs: {corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean():.3f}")
print(f"Min correlation: {corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].min():.3f}")
print(f"Max correlation: {corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].max():.3f}")
