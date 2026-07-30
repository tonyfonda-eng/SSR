from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    def research(self, text: str, prompt: str) -> dict:
        """Extracts and parses unstructured text into standard JSON structural schemas."""
        pass
