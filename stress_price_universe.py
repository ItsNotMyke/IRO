#!/usr/bin/env python3
"""
Core Universe: Stress & Price extraction for key macro, credit, equity, and sector symbols.
Minimal, focused script. Outputs a CSV with stress + price aligned by date.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
import sqlite3

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

TCA_MACRO_PATH = os.path.join(BASE_DIR, "study", "TCA_unified.txt")
MACRO_DB_PATH = os.path.join(BASE_DIR, "Brain", "MacroDb.db")
OUTPUT_CSV_PATH = os.path.join(BASE_DIR, "stress_price_universe.csv")

ROLL_WINDOW = 7

# ---------------------------------------------------------
# CORE UNIVERSE: 30 symbols (the essentials)
# ---------------------------------------------------------
# Rationale:
#   - Rates/Bonds (duration, credit risk): TLT, SHY, HYG
#   - Commodities/Inflation: GLD, USO, COPX
#   - Equities (broad, tech, mega): SPY, QQQ
#   - Volatility: VIX
#   - FX: UUP (Dollar strength), FXY (Yen safe-haven)
#   - Credit: JNK (High-yield), LQD (Investment-grade)
#   - Emerging Markets: EEM
#   - Currencies/EM credit: EMB
#   - Sectors: XLF (Financials), XLE (Energy), XLK (Tech), XLV (Healthcare), XLY (Consumer Disc)
#   - Global equity: EWJ (Japan), EWG (Germany), EWU (UK)
CORE_UNIVERSE = [
    # Macro anchors
    "TLT",      # Long-term treasuries (duration/rates)
    "SHY",      # Short-term treasuries (money market)
    "SPY",      # S&P 500 (broad equities)
    "QQQ",      # Nasdaq 100 (growth/tech)
    "VIX",      # Volatility index
    "UUP",      # US Dollar (DXY proxy)
    
    # Commodities
    "GLD",      # Gold (inflation, safe-haven)
    "USO",      # Oil
    "COPX",     # Copper (economic growth)
    
    # Credit
    "HYG",      # High-yield bonds (credit risk)
    "JNK",      # High-yield corporates
    "LQD",      # Investment-grade bonds
    "ANGL",     # Fallen angels
    
    # Emerging Markets
    "EEM",      # Emerging market equities
    "EMB",      # Emerging market bonds
    
    # FX/Safe-haven
    "FXY",      # Japanese Yen (safe-haven)
    "FXE",      # Euro
    
    # Sectors (11 total)
    "XLF",      # Financials
    "XLE",      # Energy
    "XLI",      # Industrials
    "XLK",      # Technology
    "XLP",      # Consumer Staples
    "XLY",      # Consumer Discretionary
    "XLV",      # Healthcare
    "XLRE",     # Real Estate
    "XLU",      # Utilities
    "XLC",      # Communication Services
    "XLB",      # Materials
    
    # Global equities
    "EWJ",      # Japan
    "EWG",      # Germany
    "EWU",      # UK
]

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def load_tca(path):
    """Load TCA macro file."""
    df = pd.read_csv(path, sep=r"\s*\|\s*", engine="python", skip_blank_lines=True)
    df.columns = [c.strip() for c in df.columns]
    df = df[df["DATE"].astype(str).str.contains(r"\d{4}-\d{2}-\d{2}")]
    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.sort_values("DATE").reset_index(drop=True)
    return df

def clean_column(df, col):
    """Convert percentage strings to floats."""
    s = df[col].astype(str).str.replace("%", "", regex=False).str.strip()
    s = s.replace(r'^\s*$', np.nan, regex=True)
    return s.astype(float)

def compute_stress(df, symbols, window=7):
    """
    Compute stress for each symbol.
    Stress = D^2 + C^2 + M^2
    where:
      D = rolling std of confidence
      C = 1 - rolling mean of confidence
      M = rolling std of change
    """
    out = {}
    for sym in symbols:
        c_conf = f"{sym}_CONF"
        c_chg = f"{sym}_CHG"
        if c_conf not in df.columns or c_chg not in df.columns:
            continue
        D = df[c_conf].rolling(window, min_periods=1).std()
        C = 1 - df[c_conf].rolling(window, min_periods=1).mean()
        M = df[c_chg].rolling(window, min_periods=1).std()
        out[sym] = D**2 + C**2 + M**2
    return pd.DataFrame(out)

def load_price_data(db_path, symbols):
    """Load price data from PRICE_DATA table."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        price_data = {}
        for symbol in symbols:
            cur.execute("""
                SELECT PRICE_DATE, PRICE 
                FROM PRICE_DATA 
                WHERE SYMBOL = ?
                ORDER BY PRICE_DATE ASC
            """, (symbol,))
            
            rows = cur.fetchall()
            if rows:
                prices = []
                dates = []
                for r in rows:
                    try:
                        price_str = str(r[1]).strip().replace('$', '').replace(',', '')
                        if price_str and price_str.lower() != 'none':
                            price = float(price_str)
                            prices.append(price)
                            dates.append(pd.to_datetime(r[0]))
                    except (ValueError, TypeError):
                        continue
                
                if prices and dates:
                    price_data[symbol] = pd.DataFrame({
                        'DATE': dates,
                        'PRICE': prices
                    }).set_index('DATE').sort_index()
                    print(f"  ✓ {symbol:6s} – {len(prices):4d} price points")
        
        conn.close()
        return price_data
    except Exception as e:
        print(f"[!] Error loading price data: {e}")
        import traceback
        traceback.print_exc()
        return {}

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
print("[*] Loading TCA macro data...")
df_macro = load_tca(TCA_MACRO_PATH)
print(f"    Loaded {len(df_macro)} rows, date range: {df_macro['DATE'].min()} to {df_macro['DATE'].max()}")

print("[*] Cleaning macro columns...")
for col in df_macro.columns:
    if col.endswith("_CONF") or col.endswith("_CHG"):
        df_macro[col] = clean_column(df_macro, col)

print("[*] Computing stress for core universe...")
stress = compute_stress(df_macro, CORE_UNIVERSE, window=ROLL_WINDOW)
stress["DATE"] = df_macro["DATE"]
stress = stress.set_index("DATE")

# Filter to only symbols that have stress data
available_symbols = [sym for sym in CORE_UNIVERSE if sym in stress.columns]
print(f"    {len(available_symbols)}/{len(CORE_UNIVERSE)} symbols available in TCA")

print("[*] Loading price data from database...")
price_data = load_price_data(MACRO_DB_PATH, available_symbols)
print(f"    Loaded price data for {len(price_data)} symbols")

# ---------------------------------------------------------
# ALIGN & MERGE
# ---------------------------------------------------------
print("[*] Aligning stress and price by date...")

# Start with stress index
result_df = stress[available_symbols].copy()
result_df = result_df.reset_index()

# Add price for each symbol
for sym in available_symbols:
    col_name = f"{sym}_PRICE"
    if sym in price_data:
        price_df = price_data[sym][['PRICE']].reset_index()
        price_df.columns = ['DATE', col_name]
        result_df = result_df.merge(price_df, on='DATE', how='left')
    else:
        result_df[col_name] = np.nan

# Reorder: DATE, then for each symbol: STRESS, PRICE
columns_ordered = ['DATE']
for sym in available_symbols:
    columns_ordered.append(f"{sym}")
    columns_ordered.append(f"{sym}_PRICE")

result_df = result_df[columns_ordered]

# Sort by date
result_df = result_df.sort_values('DATE').reset_index(drop=True)

print(f"    Final dataset: {len(result_df)} rows × {len(result_df.columns)} columns")
print(f"    Date range: {result_df['DATE'].min()} to {result_df['DATE'].max()}")

# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------
result_df.to_csv(OUTPUT_CSV_PATH, index=False)
print(f"[✓] Exported to: {OUTPUT_CSV_PATH}")

# Print sample
print("\n[Sample of data (first 5 rows)]:")
print(result_df.head())

print("\n[Column summary]:")
print(result_df.dtypes)

# Print missing data summary
print("\n[Missing data (% by column)]:")
missing_pct = (result_df.isnull().sum() / len(result_df) * 100).sort_values(ascending=False)
print(missing_pct[missing_pct > 0])
