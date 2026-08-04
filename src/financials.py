"""
SSR 2.0: Financial Interrogation Engine (Layer B - Derived Facts)
Calculates fundamental metrics and structural price floors (e.g., T-12 limits).
Outputs deterministic evidence records for the Causal DAG.
"""

import yfinance as yf
import pandas as pd
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

@dataclass
class FinancialSnapshot:
    """Immutable snapshot of target financials at the time of evaluation."""
    ticker: str
    is_complete: bool
    market_cap: Optional[float] = None
    current_price: Optional[float] = None
    net_cash: Optional[float] = None
    net_cash_per_share: Optional[float] = None
    options_available: bool = False
    raw_data: Optional[Dict[str, Any]] = None

def query_financial_snapshot(ticker: str, as_of_date: str = None) -> FinancialSnapshot:
    """
    Retrieves real-time or historical fundamental data to support evidentiary assertions.
    """
    if not ticker or ticker == "UNKNOWN" or "MOCK AI" in ticker:
        return FinancialSnapshot(ticker=ticker, is_complete=False)

    try:
        y_tick = yf.Ticker(ticker)
        info = y_tick.info
        
        # AUDIT FIX 14: Use historical spot price if as_of_date is provided
        current_price = None
        if as_of_date:
            try:
                # Add 1 day to end_date to ensure the as_of_date is included in the fetch
                end_date = pd.to_datetime(as_of_date) + pd.Timedelta(days=1)
                hist = y_tick.history(end=end_date.strftime('%Y-%m-%d'), period="1mo")
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
            except Exception as e:
                logger.warning(f"[FINANCIALS] Failed historical price fetch for {ticker} on {as_of_date}: {e}")
                
        # Fallback to current spot price if historical fails or isn't requested
        if current_price is None:
            current_price = info.get('currentPrice', info.get('regularMarketPrice'))
        
        # Standard Fundamentals
        market_cap = info.get('marketCap')
        
        # Cash Fundamentals
        total_cash = info.get('totalCash', 0)
        total_debt = info.get('totalDebt', 0)
        shares_out = info.get('sharesOutstanding')
        
        net_cash = None
        net_cash_per_share = None
        
        if total_cash is not None and total_debt is not None:
            net_cash = float(total_cash) - float(total_debt)
            if shares_out and shares_out > 0:
                net_cash_per_share = net_cash / float(shares_out)

        # Options Market Support
        options_available = False
        try:
            options_available = len(y_tick.options) > 0
        except Exception:
            pass

        return FinancialSnapshot(
            ticker=ticker,
            is_complete=True,
            market_cap=market_cap,
            current_price=current_price,
            net_cash=net_cash,
            net_cash_per_share=net_cash_per_share,
            options_available=options_available,
            raw_data=info
        )
    except Exception as e:
        logger.warning(f"[FINANCIALS] Failed to retrieve snapshot for {ticker}: {e}")
        return FinancialSnapshot(ticker=ticker, is_complete=False)


def get_t12_metrics(ticker: str, pre_halt_price: float = None, halt_date_str: str = None) -> dict:
    """
    Evaluates the T-12 Structural Floor constraint for Resumption of Trading events.
    Returns a deterministic validation dictionary for the Evidence Capsule.
    """
    result = {
        "valid": False,
        "reason": "Unknown",
        "net_cash_per_share": 0.0,
        "pre_halt_price": pre_halt_price
    }

    if ticker == "UNKNOWN" or not ticker:
        result["reason"] = "Missing ticker identification"
        return result

    snap = query_financial_snapshot(ticker, as_of_date=halt_date_str)
    
    if not snap.is_complete or snap.net_cash_per_share is None:
        result["reason"] = "Fundamental cash metrics unavailable via Yahoo Finance"
        return result

    result["net_cash_per_share"] = snap.net_cash_per_share

    if snap.net_cash_per_share <= 0:
        result["reason"] = f"Negative Net Cash Floor (${snap.net_cash_per_share:.2f}/share)"
        return result

    # Check margin of safety if pre-halt price is known
    # If pre_halt_price isn't explicitly passed, try to use the point-in-time price we just fetched
    eval_price = pre_halt_price if pre_halt_price else snap.current_price
    
    if eval_price:
        downside = (eval_price - snap.net_cash_per_share) / eval_price
        if downside > 0.85: # If cash floor requires an 85%+ drop, it's not a safe floor
            result["reason"] = f"Unsafe margin: Cash floor (${snap.net_cash_per_share:.2f}) is {downside*100:.1f}% below pre-halt price (${eval_price:.2f})"
            return result

    result["valid"] = True
    result["reason"] = "Structural floor validated"
    return result