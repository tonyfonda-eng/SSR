from src.providers.gemini import GeminiProvider

def get_ai_provider(provider_name: str, **kwargs):
    """
    Factory function to return the selected AI provider adapter.
    """
    name = provider_name.lower().strip()
    if name == "gemini":
        return GeminiProvider(**kwargs)
    else:
        raise ValueError(f"Unsupported AI provider: {provider_name}")
