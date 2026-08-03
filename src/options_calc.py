"""
SSR 2.0: Strategy Engine & Options Evaluator
Downstream quantitative evaluation. Decoupled from the detection pipeline.
Calculates expected return thresholds and ROI logic (e.g., Naked Call Strategy).
"""
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

def calculate_naked_call_roi(ticker: str) -> str:
    """
    Strategy Engine: Calculates theoretical Return on Investment (ROI)
    for short-term M&A option writing strategies.
    Designed to append execution rationales to reminder alerts.
    """
    if not ticker or ticker == "UNKNOWN":
        return "Strategy constraints not met: Invalid ticker."
        
    try:
        stock = yf.Ticker(ticker)
        current_price = stock.info.get("currentPrice", stock.info.get("regularMarketPrice"))
        
        if not current_price:
            return f"Strategy constraints not met: Unable to resolve current spot price for {ticker}."
            
        options = stock.options
        if not options:
            return f"Strategy Alert: No exchange-listed options chains available for {ticker}."
            
        # Grab the nearest expiration date sequence
        nearest_expiry = options[0]
        chain = stock.option_chain(nearest_expiry)
        calls = chain.calls
        
        if calls.empty:
            return f"Strategy Alert: No call options open interest found for expiry {nearest_expiry}."
            
        # Filter for strictly Out-Of-The-Money (OTM) calls
        otm_calls = calls[calls['strike'] > current_price]
        if otm_calls.empty:
            return f"Strategy Alert: No OTM call options available for {ticker} at {nearest_expiry}."
            
        # Select the nearest OTM strike allocation
        target_call = otm_calls.iloc[0]
        strike = target_call['strike']
        bid = target_call['bid']
        
        if bid <= 0.01:
            return f"Strategy Alert: Bid too low on {nearest_expiry} ${strike}C. Market maker liquidity insufficient."
            
        roi = (bid / current_price) * 100
        
        return (
            f"--- STRATEGY ENGINE: NAKED CALL ROI EVALUATION ---\n"
            f"Target Ticker: {ticker}\n"
            f"Current Spot Price: ${current_price:.2f}\n"
            f"Nearest Expiration: {nearest_expiry}\n"
            f"Target Strike (OTM): ${strike:.2f}\n"
            f"Current Bid Premium: ${bid:.2f}\n"
            f"Theoretical Unlevered Yield: {roi:.2f}%\n"
            f"--------------------------------------------------\n"
        )
        
    except Exception as e:
        logger.error(f"[STRATEGY ENGINE] Execution failed for {ticker}: {e}")
        return f"Strategy evaluation failed due to upstream market data fault: {e}"