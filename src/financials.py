import yfinance as yf
import datetime

def get_t12_metrics(ticker, pre_halt_price=None, halt_date_str=None):
    """
    Fetches financial metrics required for the T12 Resumption Strategy.
    Uses yfinance to get Cash, Debt, Shares Outstanding, and Short Interest.
    Calculates Net Cash Per Share and checks the Float Filter.
    
    If pre_halt_price is provided (e.g. from the article or previous close),
    it calculates the expected gap down target.
    
    If halt_date_str (YYYY-MM-DD) is provided, it estimates cash burn.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        shares_out = info.get('sharesOutstanding')
        total_cash = info.get('totalCash')
        total_debt = info.get('totalDebt', 0) # If missing, assume 0 debt or it might be a risk.
        short_percent = info.get('shortPercentOfFloat', 0)
        
        # If any crucial data is missing, we must fail gracefully.
        if not shares_out or total_cash is None:
            return {
                "valid": False, 
                "reason": f"Missing critical yfinance data for {ticker} (Shares: {shares_out}, Cash: {total_cash})."
            }
            
        # 1. Phase 4: Float Filter
        if shares_out > 10_000_000:
            return {
                "valid": False,
                "reason": f"Float too large. Shares Outstanding ({shares_out:,.0f}) > 10,000,000."
            }
            
        # 2. Net Cash Calculation
        net_cash = total_cash - total_debt
        if net_cash <= 0:
            return {
                "valid": False,
                "reason": f"No structural floor. Net Cash is negative or zero (${net_cash:,.2f})."
            }
            
        # 3. Burn Rate Risk (Phase 3)
        # Assume a standard microcap burn rate of $1M/month if not disclosed, just as a safety discount.
        # Alternatively, discount net_cash based on months halted.
        discounted_net_cash = net_cash
        halt_duration_days = 0
        
        if halt_date_str:
            try:
                halt_date = datetime.datetime.strptime(halt_date_str, "%Y-%m-%d").date()
                today = datetime.date.today()
                halt_duration_days = (today - halt_date).days
                if halt_duration_days > 0:
                    months_halted = halt_duration_days / 30.0
                    # Assume $500k burn per month for microcaps as a rough proxy
                    estimated_burn = months_halted * 500_000
                    discounted_net_cash -= estimated_burn
            except Exception as e:
                print(f"[WARNING] Could not parse halt date {halt_date_str}: {e}")
                
        if discounted_net_cash <= 0:
            return {
                "valid": False,
                "reason": f"Burn rate wiped out cash floor over {halt_duration_days} days halted."
            }
            
        net_cash_per_share = discounted_net_cash / shares_out
        
        # 4. Gap Down Check (Phase 2)
        # If pre-halt price isn't given, use previous close as a proxy.
        reference_price = pre_halt_price if pre_halt_price else info.get('previousClose')
        
        meets_gap_down = False
        gap_down_target_50 = 0
        gap_down_target_70 = 0
        
        if reference_price and reference_price > 0:
            gap_down_target_50 = reference_price * 0.50
            gap_down_target_70 = reference_price * 0.30
            
            # If a 50-70% gap down pushes the price below or AT the Net Cash Per Share, it's a pass!
            if gap_down_target_50 <= net_cash_per_share or gap_down_target_70 <= net_cash_per_share:
                meets_gap_down = True
            else:
                return {
                    "valid": False,
                    "reason": f"Gap down targets ($ {gap_down_target_70:.2f} - $ {gap_down_target_50:.2f}) do not reach Net Cash floor ($ {net_cash_per_share:.2f})."
                }
        else:
            print(f"[WARNING] No reference price found for {ticker}. Skipping Gap Down check.")
            meets_gap_down = True # Pass if we can't verify, let the analyst decide.

        return {
            "valid": True,
            "net_cash_per_share": net_cash_per_share,
            "shares_outstanding": shares_out,
            "short_percent_of_float": short_percent,
            "halt_duration_days": halt_duration_days,
            "gap_down_target_50": gap_down_target_50,
            "gap_down_target_70": gap_down_target_70,
            "reference_price": reference_price,
            "total_cash": total_cash,
            "total_debt": total_debt
        }
        
    except Exception as e:
        return {
            "valid": False,
            "reason": f"Error fetching financial data: {e}"
        }
