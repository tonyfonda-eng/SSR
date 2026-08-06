import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ai import extract_entities_and_roles
from src.providers.router import ProviderRouter

router = ProviderRouter()
router.update_config({"ENABLE_OPENROUTER": True})

print("\n--- TEST 1: VERALTO ACQUIRES ALFAA UV ---")
body_1 = "Veralto Corporation (NYSE: VLTO), a global leader in essential water and product quality solutions, today announced it has acquired Alfaa UV, a privately held manufacturer of ultraviolet water purification systems."
parsed_1 = extract_entities_and_roles(body_1, router=router)
print(json.dumps(parsed_1.__dict__, default=lambda o: o.__dict__, indent=2))

print("\n--- TEST 2: EQUIFAX ACQUIRES CIRCULO DE CREDITO ---")
body_2 = "Equifax® (NYSE: EFX) today announced it has signed a definitive agreement to acquire Círculo de Crédito, a leading credit bureau in Mexico. Círculo de Crédito is currently privately held."
parsed_2 = extract_entities_and_roles(body_2, router=router)
print(json.dumps(parsed_2.__dict__, default=lambda o: o.__dict__, indent=2))

