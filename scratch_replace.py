import re

def create_gate_code():
    code = """
# --- PUBLIC TICKER GATE ---
_EXCHANGES = [
    r'NYSE(?:\\s*MKT|\\s*ARCA|\\s*AMERICAN)?', r'NASDAQ', r'AMEX', r'OTCQX', r'OTCQB', r'OTC\\s*PINK', r'PINK', r'OTC(?:PK)?',
    r'TSX(?:-V|V)?', r'CSE',
    r'LSE', r'LON', r'AIM',
    r'EURONEXT(?:\\s*(?:PARIS|AMSTERDAM|BRUSSELS|LISBON|DUBLIN))?', r'EPA', r'ENXTAM', r'ENXTBR', r'ENXTPA',
    r'FRA', r'ETR', r'XETRA', r'SIX', r'SWX', r'BME', r'BIT', r'STO', r'OSL', r'CPH', r'HEL', r'WSE',
    r'ASX', r'NZX', r'HKEX', r'SEHK', r'HKG', r'TYO', r'TSE', r'SSE', r'SZSE', r'TWSE', r'KRX', r'NSE', r'BSE', r'SGX',
    r'BURSA\\s*MALAYSIA', r'SET', r'IDX', r'B3', r'BMV', r'JSE', r'TASE', r'BIST', r'MOEX'
]
_EXCHANGE_REGEX = re.compile(r'\\b(' + '|'.join(_EXCHANGES) + r')\\s*:\\s*([A-Z0-9\\-\\.]{1,10})\\b', re.IGNORECASE)

_SUFFIXES = [r'O', r'OQ', r'L', r'T', r'HK', r'DE', r'SW', r'AX', r'NS', r'SA']
_SUFFIX_REGEX = re.compile(r'\\b([A-Z0-9\\-\\.]{2,10})\\.(' + '|'.join(_SUFFIXES) + r')\\b', re.IGNORECASE)

_LABELS_REGEX = re.compile(r'\\b(?:Ticker|Stock symbol|Trading symbol|Symbol)\\s*:?\\s*([A-Z0-9\\-\\.]{1,10})\\b', re.IGNORECASE)

_CASHTAG_REGEX = re.compile(r'\\$([A-Z]{1,6})\\b')
_CRYPTO_CASHTAGS = {"BTC", "ETH", "USDT", "USDC", "BNB", "XRP", "ADA", "DOGE", "SOL", "DOT"}

_BLOOMBERG_REGEX = re.compile(r'\\b([A-Z0-9]{1,5})\\s+(US|LN|JP)\\b')

def stage_public_ticker_gate(article: dict, ctx: dict) -> tuple:
    text = article.get("body", "") + " " + article.get("headline", "")
    
    # 1. Exchange-qualified
    match = _EXCHANGE_REGEX.search(text)
    if match:
        article["_deterministic_ticker"] = match.group(2).upper()
        article["_deterministic_exchange"] = match.group(1).upper()
        article["_ticker_match_type"] = "EXCHANGE_PREFIX"
        article["_ticker_match"] = match.group(0)
        return True, "passed"
        
    # 2. Explicit labels
    match = _LABELS_REGEX.search(text)
    if match:
        article["_deterministic_ticker"] = match.group(1).upper()
        article["_deterministic_exchange"] = "UNKNOWN"
        article["_ticker_match_type"] = "EXPLICIT_LABEL"
        article["_ticker_match"] = match.group(0)
        return True, "passed"
        
    # 3. Market suffix
    match = _SUFFIX_REGEX.search(text)
    if match:
        article["_deterministic_ticker"] = match.group(1).upper()
        article["_deterministic_exchange"] = match.group(2).upper()
        article["_ticker_match_type"] = "MARKET_SUFFIX"
        article["_ticker_match"] = match.group(0)
        return True, "passed"
        
    # 4. Bloomberg
    match = _BLOOMBERG_REGEX.search(text)
    if match:
        article["_deterministic_ticker"] = match.group(1).upper()
        article["_deterministic_exchange"] = match.group(2).upper()
        article["_ticker_match_type"] = "BLOOMBERG"
        article["_ticker_match"] = match.group(0)
        return True, "passed"
        
    # 5. Cashtags
    for match in _CASHTAG_REGEX.finditer(text):
        ticker = match.group(1).upper()
        if ticker not in _CRYPTO_CASHTAGS:
            article["_deterministic_ticker"] = ticker
            article["_deterministic_exchange"] = "UNKNOWN"
            article["_ticker_match_type"] = "CASHTAG"
            article["_ticker_match"] = match.group(0)
            return True, "passed"
            
    return False, "dropped_no_public_ticker"

"""
    with open('monitor.py', 'r') as f:
        content = f.read()

    # insert the code before stage_python_ticker_lookup
    idx = content.find("def stage_python_ticker_lookup")
    new_content = content[:idx] + code + content[idx:]
    
    # replace python_ticker_lookup with public_ticker_gate in execution_order 1
    new_content = new_content.replace(
        '"python_issuer_extraction", "python_ticker_lookup", "ai_ticker_resolution"',
        '"python_issuer_extraction", "public_ticker_gate", "ai_ticker_resolution"'
    )
    
    # replace python_ticker_lookup with public_ticker_gate in execution_order 2
    # Oh wait, python_ticker_lookup is not in the second execution order, it has candidate_generator.
    # Let's insert public_ticker_gate before candidate_generator
    new_content = new_content.replace(
        '"python_issuer_extraction", "candidate_generator", "ambiguity_gate"',
        '"python_issuer_extraction", "public_ticker_gate", "candidate_generator", "ambiguity_gate"'
    )
    
    # add to STAGE_REGISTRY
    new_content = new_content.replace(
        '"python_ticker_lookup": stage_python_ticker_lookup,',
        '"python_ticker_lookup": stage_python_ticker_lookup,\n    "public_ticker_gate": stage_public_ticker_gate,'
    )
    
    with open('monitor.py', 'w') as f:
        f.write(new_content)

create_gate_code()
