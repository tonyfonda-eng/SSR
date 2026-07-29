import logging
from typing import Dict, List
from src.app.market.interfaces import ProviderRegistry, ProviderBundle, MarketCapability, MarketDataPoller

class MarketProviderRegistry(ProviderRegistry):
    def __init__(self):
        self.logger = logging.getLogger("SSR.ProviderRegistry")
        self._bundles: Dict[str, ProviderBundle] = {}

    def register_bundle(self, bundle: ProviderBundle) -> None:
        name = bundle.descriptor.name
        self._bundles[name] = bundle
        self.logger.info(f"Registered capability bundle for provider: {name}")

    def resolve_pollers(self, capability: MarketCapability) -> List[MarketDataPoller]:
        results = []
        for bundle in self._bundles.values():
            if bundle.descriptor.supports(capability):
                results.extend(bundle.pollers)
        return results
