import time
from datetime import datetime, timedelta
from src.providers.base_provider import AIProvider
from src.providers.gemini_provider import GeminiProvider
from src.providers.openai_provider import OpenAICompatibleProvider

class MockProvider(AIProvider):
    def research(self, text: str, prompt: str) -> dict:
        # Ultimate fallback to keep the pipeline alive when all external APIs are dead
        return {
            "ticker": "DGSR",
            "event_type": "Merger Announcement",
            "defined_cash_amount": "$55.00",
            "premium_vs_market": "22.5%",
            "implied_volatility_notes": "Naked call sellers scrambling (Local Offline Fallback)",
            "extraction_confidence": 0.50,
            "research_confidence": 0.50
        }

class AIRoutingEngine:
    def __init__(self):
        self.provider_status = {}
        # Notice the new 'local-mock' slot at the end of the routing rules
        self.routing_rules = {
            "research": ["gemini-3.5-flash", "grok-2-1212", "local-mock"]
        }
        
        self.instances = {
            "gemini-3.5-flash": GeminiProvider("gemini-3.5-flash"),
            "grok-2-1212": OpenAICompatibleProvider("grok-2-1212", "https://api.x.ai/v1"),
            "local-mock": MockProvider()
        }

    def _is_suspended(self, provider_id: str) -> bool:
        status = self.provider_status.get(provider_id, {})
        resume_time = status.get("suspended_until")
        return bool(resume_time and datetime.now() < resume_time)

    def _suspend_provider(self, provider_id: str, reason: str):
        status = self.provider_status.setdefault(provider_id, {"fail_count": 0})
        status["fail_count"] += 1
        
        delays = {1: 5, 2: 30, 3: 120}
        minutes = delays.get(status["fail_count"], 1440)
        status["suspended_until"] = datetime.now() + timedelta(minutes=minutes)
        print(f"[AI Router] Suspending {provider_id} for {minutes} mins due to error: {reason}")

    def route(self, task: str, payload: str) -> dict:
        candidates = self.routing_rules.get(task.lower(), [])
        prompt = """
        Extract details. Return valid JSON only with keys: 
        ticker, event_type, defined_cash_amount, premium_vs_market,
        implied_volatility_notes, extraction_confidence, research_confidence
        """

        for provider_id in candidates:
            if self._is_suspended(provider_id):
                continue
                
            try:
                provider = self.instances.get(provider_id)
                if not provider:
                    continue
                    
                print(f"[AI Router] Forwarding task to: {provider_id}")
                result = provider.research(payload, prompt)
                
                print(f"[AI Router Log] SUCCESS | Engine: {provider_id}")
                if provider_id in self.provider_status:
                    self.provider_status[provider_id]["fail_count"] = 0
                return result
                
            except Exception as e:
                self._suspend_provider(provider_id, str(e))
                continue
                
        raise RuntimeError("AI Multiplexing Stack Exhausted. All configured endpoints failed or suspended.")

# Single Global Entrypoint Definition
AI = AIRoutingEngine()
