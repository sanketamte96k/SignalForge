"""
SignalForge - Phase 2: Zerodha Kite Connect Historical Data Feasibility Test.

This script tests whether Zerodha Kite Connect can provide reliable 1-minute
NSE equity historical data for the SignalForge frozen research window:
START: 2015-01-01
END: 2024-03-26 15:29:00

Representative stocks:
- RELIANCE
- TCS
- INFY
- HDFCBANK
- ADANIENT
- SBIN
"""

import os
import sys
import time
import json
import csv
import io
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

# Configuration & Constants
REPRESENTATIVE_STOCKS = [
    'RELIANCE',
    'TCS',
    'INFY',
    'HDFCBANK',
    'ADANIENT',
    'SBIN'
]

KITE_INSTRUMENTS_URL = 'https://api.kite.trade/instruments'
KITE_HISTORICAL_URL = 'https://api.kite.trade/instruments/historical/{token}/{interval}'

FROZEN_START = '2015-01-01'
FROZEN_END = '2024-03-26 15:29:00'

def check_credentials():
    """Check for Zerodha Kite credentials in environment without exposing secrets."""
    api_key = os.environ.get('KITE_API_KEY') or os.environ.get('ZERODHA_API_KEY')
    api_secret = os.environ.get('KITE_API_SECRET') or os.environ.get('ZERODHA_API_SECRET')
    access_token = os.environ.get('KITE_ACCESS_TOKEN') or os.environ.get('ZERODHA_ACCESS_TOKEN')
    
    status = {
        'api_key_configured': bool(api_key),
        'api_secret_configured': bool(api_secret),
        'access_token_configured': bool(access_token),
        'authenticated': bool(api_key and access_token)
    }
    return status, api_key, access_token

def fetch_instrument_tokens():
    """Fetch live instrument master from Zerodha and resolve tokens for the 6 stocks."""
    print(f"Fetching Zerodha instrument master from {KITE_INSTRUMENTS_URL}...")
    r = requests.get(KITE_INSTRUMENTS_URL, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to fetch instrument master: HTTP {r.status_code}")
    
    df = pd.read_csv(io.StringIO(r.text))
    # Filter for NSE Equities
    nse_eq = df[(df['exchange'] == 'NSE') & (df['instrument_type'] == 'EQ')]
    
    token_map = {}
    for sym in REPRESENTATIVE_STOCKS:
        match = nse_eq[nse_eq['tradingsymbol'] == sym]
        if not match.empty:
            row = match.iloc[0]
            token_map[sym] = {
                'instrument_token': int(row['instrument_token']),
                'exchange_token': str(row['exchange_token']),
                'tradingsymbol': str(row['tradingsymbol']),
                'name': str(row['name']),
                'tick_size': float(row['tick_size']),
                'lot_size': int(row['lot_size']),
                'segment': str(row['segment'])
            }
        else:
            token_map[sym] = None
    return token_map

def probe_historical_endpoint(token, api_key=None, access_token=None):
    """Probe the Kite historical endpoint to verify HTTP response and auth requirements."""
    url = KITE_HISTORICAL_URL.format(token=token, interval='minute')
    params = {'from': '2015-01-01', 'to': '2015-01-05'}
    headers = {'X-Kite-Version': '3'}
    
    if api_key and access_token:
        headers['Authorization'] = f"token {api_key}:{access_token}"
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        return {
            'status_code': r.status_code,
            'content_type': r.headers.get('Content-Type', ''),
            'response_json': r.json() if 'application/json' in r.headers.get('Content-Type', '') else None
        }
    except Exception as e:
        return {'error': str(e)}

def analyze_existing_data():
    """Analyze existing RELIANCE historical data in SignalForge for comparison."""
    parquet_path = Path('RELIANCE_test.parquet')
    if not parquet_path.exists():
        return None
    
    df = pd.read_parquet(parquet_path)
    # Convert dates to string for serialization
    sample_head = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].head(3).copy()
    sample_head['Date'] = sample_head['Date'].astype(str)
    sample_tail = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].tail(3).copy()
    sample_tail['Date'] = sample_tail['Date'].astype(str)
    
    return {
        'total_rows': len(df),
        'columns': list(df.columns),
        'min_timestamp': str(df['Date'].min()),
        'max_timestamp': str(df['Date'].max()),
        'sample_head': sample_head.to_dict(orient='records'),
        'sample_tail': sample_tail.to_dict(orient='records'),
    }

def main():
    print("==================================================================")
    print("SIGNALFORGE — PHASE 2: ZERODHA KITE HISTORICAL DATA FEASIBILITY TEST")
    print("==================================================================\n")
    
    # Step 2: Check Zerodha Configuration
    cred_status, api_key, access_token = check_credentials()
    print("1. Zerodha Kite Connect Configuration Check:")
    print(f"   KITE_API_KEY Configured: {cred_status['api_key_configured']}")
    print(f"   KITE_API_SECRET Configured: {cred_status['api_secret_configured']}")
    print(f"   KITE_ACCESS_TOKEN Configured: {cred_status['access_token_configured']}")
    print(f"   Ready for Authenticated Calls: {cred_status['authenticated']}\n")
    
    # Step 3: Fetch Instrument Master
    token_map = fetch_instrument_tokens()
    print("2. Resolved NSE Instrument Master Tokens:")
    for sym, details in token_map.items():
        if details:
            print(f"   {sym:12} -> Token: {details['instrument_token']:<10} | Name: {details['name']}")
        else:
            print(f"   {sym:12} -> NOT FOUND")
    print()
    
    # Step 4: Endpoint Probe
    sample_sym = 'RELIANCE'
    sample_tok = token_map[sample_sym]['instrument_token']
    probe_res = probe_historical_endpoint(sample_tok, api_key, access_token)
    print(f"3. Kite Historical Data API Endpoint Probe ({sample_sym} Token: {sample_tok}):")
    print(f"   HTTP Status: {probe_res.get('status_code')}")
    print(f"   Content-Type: {probe_res.get('content_type')}")
    print(f"   Response Payload: {probe_res.get('response_json')}\n")
    
    # Step 5: Existing Data Analysis (SignalForge RELIANCE parquet)
    existing_data = analyze_existing_data()
    print("4. SignalForge Existing Benchmark Data (RELIANCE_test.parquet):")
    if existing_data:
        print(f"   Total rows: {existing_data['total_rows']:,}")
        print(f"   Time span: {existing_data['min_timestamp']} to {existing_data['max_timestamp']}")
        print(f"   Columns: {existing_data['columns']}\n")
    
    # Save findings for report generation
    output_dir = Path('research')
    output_dir.mkdir(exist_ok=True)
    
    audit_summary = {
        'cred_status': cred_status,
        'token_map': token_map,
        'probe_res': probe_res,
        'existing_data': existing_data,
        'timestamp': datetime.now().isoformat()
    }
    
    with open('research/zerodha_feasibility_audit.json', 'w', encoding='utf-8') as f:
        json.dump(audit_summary, f, indent=2)
        
    print("Audit data saved to research/zerodha_feasibility_audit.json")

if __name__ == '__main__':
    main()
