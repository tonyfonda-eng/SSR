from src.providers.base_ai import BaseAIProvider

def evaluate_event(text: str, ai_provider: BaseAIProvider) -> str:
    """
    Evaluate the event text using the provided AI provider's classify method.
    """
    return ai_provider.classify(text)
