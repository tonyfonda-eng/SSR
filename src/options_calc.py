import yfinance as yf
import pandas as pd
import datetime

def calculate_naked_call_roi(ticker):
    try:
        yf_ticker = yf.Ticker(ticker)
        current_price = yf_ticker.info.get('currentPrice', yf_ticker.info.get('regularMarketPrice', 0))
        if current_price == 0:
            return "Could not retrieve current price for ROI calculation."
            
        options = yf_ticker.options
        if not options:
            return "No options chain available for ROI calculation."
            
        results = []
        today = datetime.date.today()
        
        for exp in options:
            exp_date = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if dte <= 0:
                continue
                
            chain = yf_ticker.option_chain(exp).calls
            
            for _, row in chain.iterrows():
                strike = row['strike']
                # only calculate for OTM options
                if strike <= current_price:
                    continue
                    
                bid = row.get('bid', 0)
                ask = row.get('ask', 0)
                last = row.get('lastPrice', 0)
                
                if bid > 0 and ask > 0:
                    premium = (bid + ask) / 2
                else:
                    premium = last
                    
                if premium <= 0.05: # Skip effectively worthless options
                    continue
                    
                otm_amount = strike - current_price
                
                # Reg T Margin for naked call
                margin1 = 0.20 * current_price - otm_amount + premium
                margin2 = 0.10 * current_price + premium
                margin_req = max(margin1, margin2)
                
                # Minimum margin requirement is usually $250 per contract, meaning $2.50 per share
                if margin_req < 2.50:
                    margin_req = 2.50
                    
                roi = premium / margin_req
                annualized_roi = roi * (365 / dte)
                
                results.append({
                    'Expiry': exp,
                    'Strike': strike,
                    'Premium': f"${premium:.2f}",
                    'Margin Req': f"${margin_req:.2f}",
                    'Ann. ROI': f"{annualized_roi * 100:.1f}%"
                })
                
        if not results:
            return "No OTM options available with significant premium to calculate ROI."
            
        df = pd.DataFrame(results)
        # Limit to top 15 highest ROI
        df['sort_roi'] = df['Ann. ROI'].str.replace('%', '').astype(float)
        df = df.sort_values('sort_roi', ascending=False).drop('sort_roi', axis=1).head(15)
        
        return "### Naked Call Annualized ROI (Reg T Margin)\\nUnderlying Price: $" + str(current_price) + "\\n\\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"Error calculating ROI: {e}"
