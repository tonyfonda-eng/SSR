import requests

# Borsa Italiana
try:
    r = requests.get('https://www.borsaitaliana.it/borsa/notizie/price-sensitive/home.html', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
    print(f"Borsa Italiana: {r.status_code}")
except Exception as e:
    print(f"Borsa Italiana failed: {e}")

# CNMV Spain
try:
    r = requests.get('https://www.cnmv.es/Portal/HR/ResultadoBusquedaHR.aspx?division=1&idioma=en', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
    print(f"CNMV Spain: {r.status_code}")
except Exception as e:
    print(f"CNMV failed: {e}")

# Actusnews (France)
try:
    r = requests.get('https://www.actusnews.com/en/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
    print(f"Actusnews: {r.status_code}")
except Exception as e:
    print(f"Actusnews failed: {e}")
