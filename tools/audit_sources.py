"""
SSR 2.0 Hardening Sprint: Standalone Source Auditor
Decouples ingestion health from AI processing by independently measuring scraper uptime and WAF blocks.
"""
import sys
import time
import requests
from colorama import init, Fore, Style
from src.sheets import load_sources
from src.config.settings import SHEET_URL

init(autoreset=True)

def audit_sources():
    print(f"{Fore.CYAN}{Style.BRIGHT}=== SSR 2.0 Ingestion Health Matrix ===")
    print("Auditing all configured sources for RSS/HTML availability and WAF blocks...\n")
    
    try:
        sources = load_sources(SHEET_URL)
    except Exception as e:
        print(f"{Fore.RED}Failed to load sources from Google Sheets: {e}")
        return

    if not sources:
        print(f"{Fore.YELLOW}No sources found in the configuration sheet.")
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    healthy_count = 0
    failed_count = 0

    print(f"{'SOURCE NAME':<30} | {'METHOD':<6} | {'STATUS':<20} | {'LATENCY':<8}")
    print("-" * 75)

    for src in sources:
        enabled = str(src.get("Enabled", src.get("Status", "TRUE"))).upper()
        if enabled != "TRUE" and enabled != "ACTIVE":
            continue
            
        name = src.get("Source", "Unknown")
        html_url = src.get("HTML URL", "")
        rss_url = src.get("RSS URL", "")
        ingestion_method = src.get("Ingestion Method", "HTML").upper()
        
        target_url = rss_url if ingestion_method == "RSS" and rss_url else html_url
        if not target_url:
            continue

        try:
            start_time = time.time()
            resp = requests.get(target_url, headers=headers, timeout=10)
            latency = (time.time() - start_time) * 1000
            
            if resp.status_code == 200:
                # Basic WAF Check
                if "cloudflare" in resp.headers.get("Server", "").lower() and "challenge" in resp.text.lower():
                    status = f"{Fore.YELLOW}WAF Block (Cloudflare)"
                    failed_count += 1
                else:
                    status = f"{Fore.GREEN}OK (200)"
                    healthy_count += 1
            elif resp.status_code in [403, 401]:
                status = f"{Fore.RED}Blocked ({resp.status_code})"
                failed_count += 1
            else:
                status = f"{Fore.RED}Error ({resp.status_code})"
                failed_count += 1
                
        except requests.exceptions.Timeout:
            latency = 10000
            status = f"{Fore.RED}Timeout"
            failed_count += 1
        except Exception as e:
            latency = 0
            status = f"{Fore.RED}Failed"
            failed_count += 1

        print(f"{name[:28]:<30} | {ingestion_method[:6]:<6} | {status:<20} | {int(latency):>4}ms")
        time.sleep(0.5) # Be polite

    print("-" * 75)
    print(f"\n{Style.BRIGHT}Audit Complete: {healthy_count} Healthy, {failed_count} Blocked/Failed.")
    
    if failed_count > 0:
        print(f"{Fore.YELLOW}Warning: Proceeding with broken scrapers may impact pipeline accuracy.")
        sys.exit(1)
    else:
        print(f"{Fore.GREEN}All active sources are online and returning valid payloads.")
        sys.exit(0)

if __name__ == "__main__":
    audit_sources()
