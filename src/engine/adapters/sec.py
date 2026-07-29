import xml.etree.ElementTree as ET
from typing import Dict, Any, List
from src.engine.connectors import MarketDataConnector, MarketDataAdapter
from src.knowledge.schemas.epistemology import CandidateAssertion, ConfidenceMethod

class SECEDGARConnector(MarketDataConnector):
    def __init__(self, transport):
        super().__init__(transport)
        # The SEC requires a strict User-Agent policy to avoid instant IP bans
        self.transport.session.headers.update({
            "User-Agent": "SpecialSituationsRadar_v1 admin@radar.local",
            "Accept-Encoding": "gzip, deflate"
        })

    def fetch_recent_filings(self, ticker: str, form_type: str = "8-K") -> str:
        """Fetches the live Atom RSS XML feed from SEC EDGAR."""
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type={form_type}&output=atom"
        return self.transport.get(url)
        
    def fetch_market_price(self, ticker: str): pass
    def fetch_option_chain(self, ticker: str): pass

class SECEDGARAdapter(MarketDataAdapter):
    def adapt_filings(self, raw_xml: str, ticker: str, event_id: str) -> List[CandidateAssertion]:
        """Parses Atom XML and transforms recent filings into Canonical Document Candidates."""
        candidates = []
        try:
            root = ET.fromstring(raw_xml)
            # Atom XML uses specific namespace routing
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text
                link = entry.find('atom:link', ns).attrib['href']
                updated = entry.find('atom:updated', ns).text
                
                # Title format is typically "8-K - Company Name (Accession Number)"
                form_type = title.split('-')[0].strip()
                accession = entry.find('atom:id', ns).text.split('accession-number=')[-1]
                
                candidates.append(CandidateAssertion(
                    candidate_id=f"CND.SEC.{accession}",
                    event_id=event_id,
                    schema_id="SCHEMA.DOC.SEC_FILING",
                    object_id=f"OBJ.DOC.FILING.{accession}",
                    value_payload={
                        "ticker": ticker.upper(),
                        "form_type": form_type,
                        "accession_number": accession,
                        "filing_date": updated,
                        "document_url": link
                    },
                    basis_observations=[],
                    confidence_method=ConfidenceMethod.EXACT_MATCH,
                    extractor_profile_id="CONN.SEC.RSS.v1"
                ))
        except Exception as e:
            print(f"[!] SEC XML Parsing Error: {e}")
            
        return candidates

    def adapt_price_snapshot(self, raw, event_id): pass
    def adapt_chain(self, raw, event_id): pass
