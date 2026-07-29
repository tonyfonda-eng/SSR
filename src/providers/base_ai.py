from abc import ABC, abstractmethod

class BaseAIProvider(ABC):
    @abstractmethod
    def classify(self, text: str, **kwargs) -> str:
        """Classify the provided text."""
        pass

    @abstractmethod
    def translate(self, text: str, target_language: str = "en", **kwargs) -> str:
        """Translate the provided text."""
        pass

    @abstractmethod
    def research(self, query: str, **kwargs) -> str:
        """Perform research on the provided query."""
        pass
