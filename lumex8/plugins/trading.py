from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer
import json
import urllib.request

NAME = "Market Tracker"

# --- CONFIGURATION (Dropdowns will now work!) ---
CONFIG_FIELDS = [
    {
        "key": "home_currency", 
        "label": "Home Currency", 
        "default": "PLN", 
        "options": ["PLN", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY"]
    },
    {
        "key": "assets", 
        "label": "Assets to Track (comma sep)", 
        "default": "USD, GBP, BTC"
    },
    {
        "key": "static_mode", 
        "label": "Widget Mode", 
        "default": "False",
        "options": ["False", "True"]
    }
]

def setup(tile):
    # 1. Cleanup
    while tile.live_layout.count():
        item = tile.live_layout.takeAt(0)
        if item.widget(): item.widget().deleteLater()

    # 2. Layout
    container = QWidget()
    vbox = QVBoxLayout(container)
    vbox.setContentsMargins(15, 5, 15, 5)
    vbox.setSpacing(2)
    vbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    
    # Store labels to update later
    tile.rate_labels = {}
    
    # Create placeholder labels immediately based on settings
    assets_str = tile.app_data.get('assets', 'USD, GBP, BTC')
    assets = [a.strip().upper() for a in assets_str.split(',') if a.strip()]
    
    for asset in assets:
        lbl = QLabel(f"{asset}: ...")
        lbl.setStyleSheet("font-family: 'Segoe UI'; font-size: 15px; color: #f0f0f0; font-weight: 500;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        vbox.addWidget(lbl)
        tile.rate_labels[asset] = lbl
        
    tile.live_layout.addWidget(container)

    # 3. Hybrid Data Logic (Fiat + Crypto)
    def refresh_data():
        home = tile.app_data.get('home_currency', 'PLN')
        
        # A. Fetch Standard Fiat Rates first
        fiat_rates = {}
        try:
            # API: 1 HOME = X TARGETS. (e.g. 1 PLN = 0.25 USD)
            url = f"https://open.er-api.com/v6/latest/{home}"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                if 'rates' in data:
                    fiat_rates = data['rates']
        except Exception as e:
            print(f"Fiat API Error: {e}")

        # B. Process each asset
        for asset, label in tile.rate_labels.items():
            price_in_home = 0.0
            
            # --- STRATEGY 1: Is it a Fiat currency? ---
            if asset in fiat_rates:
                rate = fiat_rates[asset]
                if rate > 0:
                    # Convert: If 1 PLN = 0.25 USD, then 1 USD = 1/0.25 = 4 PLN
                    price_in_home = 1.0 / rate
            
            # --- STRATEGY 2: Not found? Try Crypto API ---
            else:
                try:
                    # CryptoCompare: Supports BTC -> PLN directly
                    c_url = f"https://min-api.cryptocompare.com/data/price?fsym={asset}&tsyms={home}"
                    with urllib.request.urlopen(c_url, timeout=5) as response:
                        c_data = json.loads(response.read().decode())
                        if home in c_data:
                            price_in_home = float(c_data[home])
                except:
                    pass # Failed both APIs

            # Update UI
            if price_in_home > 0:
                # Formatting
                if price_in_home < 1:
                    val_str = f"{price_in_home:.4f}"
                elif price_in_home > 1000:
                    val_str = f"{price_in_home/1000:.1f}k"
                else:
                    val_str = f"{price_in_home:.2f}"
                    
                label.setText(f"{asset}:  {val_str} {home}")
            else:
                # Keep old text if update fails, or show error
                if "..." in label.text():
                    label.setText(f"{asset}: N/A")

    # 4. Timer (Update every 60s)
    tile.data_timer = QTimer(tile)
    tile.data_timer.timeout.connect(refresh_data)
    tile.data_timer.start(60000) 
    
    # Run once immediately
    refresh_data()

    # 5. Widget Mode Handling
    def apply_view_mode():
        want_slideshow = tile.app_data.get('static_mode', 'False') == 'True'

        if want_slideshow:
            # Slideshow mode: cycle between static and live
            tile.live_timer.setInterval(8000)
        else:
            # Default: always show live content, no slide
            tile.slide_to_live()
            tile.live_timer.stop()
            
    QTimer.singleShot(100, apply_view_mode)

def run(window):
    import webbrowser
    webbrowser.open("https://finance.yahoo.com")
