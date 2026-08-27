import re

EXCHANGES = [
    r'NYSE(?:\s*MKT|\s*ARCA|\s*AMERICAN)?', r'NASDAQ', r'AMEX', r'OTCQX', r'OTCQB', r'OTC\s*PINK', r'PINK', r'OTC(?:PK)?',
    r'TSX(?:-V|V)?', r'CSE',
    r'LSE', r'LON', r'AIM',
    r'EURONEXT(?:\s*(?:PARIS|AMSTERDAM|BRUSSELS|LISBON|DUBLIN))?', r'EPA', r'ENXTAM', r'ENXTBR', r'ENXTPA',
    r'FRA', r'ETR', r'XETRA', r'SIX', r'SWX', r'BME', r'BIT', r'STO', r'OSL', r'CPH', r'HEL', r'WSE',
    r'ASX', r'NZX', r'HKEX', r'SEHK', r'HKG', r'TYO', r'TSE', r'SSE', r'SZSE', r'TWSE', r'KRX', r'NSE', r'BSE', r'SGX',
    r'BURSA\s*MALAYSIA', r'SET', r'IDX', r'B3', r'BMV', r'JSE', r'TASE', r'BIST', r'MOEX'
]
EXCHANGE_REGEX = re.compile(r'\b(' + '|'.join(EXCHANGES) + r')\s*:\s*([A-Z0-9\-\.]{1,10})\b', re.IGNORECASE)

SUFFIXES = [r'O', r'OQ', r'L', r'T', r'HK', r'DE', r'SW', r'AX', r'NS', r'SA']
SUFFIX_REGEX = re.compile(r'\b([A-Z0-9\-\.]{2,10})\.(' + '|'.join(SUFFIXES) + r')\b', re.IGNORECASE)

LABELS_REGEX = re.compile(r'\b(?:Ticker|Stock symbol|Trading symbol|Symbol)\s*:?\s*([A-Z0-9\-\.]{1,10})\b', re.IGNORECASE)

CASHTAG_REGEX = re.compile(r'\$([A-Z]{1,6})\b')
CRYPTO_CASHTAGS = {"BTC", "ETH", "USDT", "USDC", "BNB", "XRP", "ADA", "DOGE", "SOL", "DOT"}

BLOOMBERG_REGEX = re.compile(r'\b([A-Z0-9]{1,5})\s+(US|LN|JP)\b')

def extract_public_ticker(text):
    # 1. Exchange-qualified
    match = EXCHANGE_REGEX.search(text)
    if match:
        return {
            "deterministic_ticker": match.group(2).upper(),
            "deterministic_exchange": match.group(1).upper(),
            "ticker_match_type": "EXCHANGE_PREFIX",
            "ticker_match": match.group(0)
        }
        
    # 2. Explicit labels
    match = LABELS_REGEX.search(text)
    if match:
        return {
            "deterministic_ticker": match.group(1).upper(),
            "deterministic_exchange": "UNKNOWN",
            "ticker_match_type": "EXPLICIT_LABEL",
            "ticker_match": match.group(0)
        }
        
    # 3. Market suffix
    match = SUFFIX_REGEX.search(text)
    if match:
        return {
            "deterministic_ticker": match.group(1).upper(),
            "deterministic_exchange": match.group(2).upper(),
            "ticker_match_type": "MARKET_SUFFIX",
            "ticker_match": match.group(0)
        }
        
    # 4. Bloomberg
    match = BLOOMBERG_REGEX.search(text)
    if match:
        return {
            "deterministic_ticker": match.group(1).upper(),
            "deterministic_exchange": match.group(2).upper(),
            "ticker_match_type": "BLOOMBERG",
            "ticker_match": match.group(0)
        }
        
    # 5. Cashtags
    for match in CASHTAG_REGEX.finditer(text):
        ticker = match.group(1).upper()
        if ticker not in CRYPTO_CASHTAGS:
            return {
                "deterministic_ticker": ticker,
                "deterministic_exchange": "UNKNOWN",
                "ticker_match_type": "CASHTAG",
                "ticker_match": match.group(0)
            }
            
    return None

examples = [
    ("Accelerant Holdings (NYSE: ARX)", True),
    ("Apple Inc. (NASDAQ: AAPL)", True),
    ("Company (TSX: SHOP)", True),
    ("Company (LSE: VOD)", True),
    ("Company (ASX: BHP)", True),
    ("Company (HKEX: 0700)", True),
    ("Company (TSE: 7203)", True),
    ("Company (SSE: 600519)", True),
    ("Company (BSE: 500325)", True),
    ("Company (NSE: RELIANCE)", True),
    ("Company (NYSE: GOLD; TSX: ABX)", True),
    ("$AAPL", True),
    ("CARFAX article with no explicit public ticker", False),
    ("New Earth Resources article with no explicit public ticker", False),
    ("Private company acquisition with no ticker", False),
    ("Article merely containing purchase", False),
    ("Article merely containing an uppercase word", False),
    ("AAPL.O", True),
    ("VOD.L", True),
    ("Ticker: AAPL", True)
]

for text, expected in examples:
    res = extract_public_ticker(text)
    passed = res is not None
    print(f"[{'PASS' if passed == expected else 'FAIL'}] {text} -> {res}")

