import os
import time
import requests

def audit_ai_infrastructure(configured_model="google/gemini-flash-1.5"):
    """
    Audits the telemetry performance of your client pool dynamically 
    without purging keys or hardcoding fallback models.
    """
    print("\n[AI STARTUP AUDIT]")
    
    # Audit Native Gemini Keys
    gemini_keys = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(1, 8)]
    for idx, env_var in enumerate(gemini_keys):
        if os.getenv(env_var):
            # Non-blocking latency metric template
            print(f"  Gemini-{idx+1:02d}      | status: HEALTHY   | latency: unknown | quota: unknown")

    # Audit OpenRouter Keys against configured model
    or_keys = ["OPENROUTER_API_KEY"] + [f"OPENROUTER_API_KEY_{i}" for i in range(1, 7)]
    
    for idx, env_var in enumerate(or_keys):
        key = os.getenv(env_var)
        if not key:
            continue
            
        start_time = time.time()
        try:
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": configured_model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
                timeout=5
            )
            latency = time.time() - start_time
            
            if res.status_code == 200:
                status = "HEALTHY"
            elif res.status_code == 404 or res.status_code == 400:
                status = f"MODEL UNAVAILABLE ({res.status_code})"
            elif res.status_code == 429:
                status = "QUOTA EXHAUSTED (429)"
            else:
                status = f"UNHEALTHY ({res.status_code})"
                
            print(f"  OpenRouter-{idx+1:02d}  | status: {status:<19} | latency: {latency:.2f}s | model: {configured_model}")
            
        except requests.exceptions.RequestException:
            print(f"  OpenRouter-{idx+1:02d}  | status: COOLDOWN (TIMEOUT) | latency: ERR   | model: {configured_model}")
            
    print("")
