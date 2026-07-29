from unittest.mock import MagicMock
from src.classifiers.event_classifier import evaluate_event
from src.providers.base_ai import BaseAIProvider

def test_evaluate_event_options_tender_offer():
    # Arrange
    mock_provider = MagicMock(spec=BaseAIProvider)
    mock_provider.classify.return_value = "M&A Event Detected"
    
    test_text = "Acquisition alert: dgsr options tender offer is underway with premium price."
    
    # Act
    result = evaluate_event(test_text, mock_provider)
    
    # Assert
    mock_provider.classify.assert_called_once_with(test_text)
    assert result == "M&A Event Detected"
