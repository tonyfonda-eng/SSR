import os
from monitor import _process_article
import src.ai

def mock_extract_target_ticker(body):
    return "INHD"

def mock_extract_halt_date(body):
    return "2024-03-15"

src.ai.extract_target_ticker = mock_extract_target_ticker
src.ai.extract_halt_date = mock_extract_halt_date

def test_t12():
    mock_body = """
    INNO HOLDINGS INC. ANNOUNCES RESUMPTION OF TRADING ON NASDAQ
    
    AUSTIN, Texas, April 10, 2024 /PRNewswire/ -- Inno Holdings Inc. (Nasdaq: INHD) today announced that Nasdaq has authorized the resumption of trading of its common stock.
    The trading halt was initiated on March 15, 2024 (Code T12) pending the release of material news regarding the company's internal accounting audit. The company has now satisfied the requests of Nasdaq and filed its delayed 10-K.
    """
    
    mock_rules = [
        {"Keywords": "Code T12, resumption of trading", "Score": 10, "Event Family": "Resumption of Trading", "AI Prompt": ""}
    ]
    
    mock_playbook_map = {
        "Resumption of Trading": "Standard research for T12."
    }
    
    funnel_metrics = {i: 0 for i in range(1, 13)}
    
    _process_article(
        source_name="Mock Source",
        article_id="mock_inno_t12_v3",
        title="Inno Holdings Inc. Announces Resumption of Trading on Nasdaq",
        url="http://mock.com",
        published="2024-04-10",
        body=mock_body,
        rules=mock_rules,
        playbook_map=mock_playbook_map,
        global_exclusions=[],
        gold_standards={},
        funnel_metrics=funnel_metrics
    )

if __name__ == "__main__":
    test_t12()
