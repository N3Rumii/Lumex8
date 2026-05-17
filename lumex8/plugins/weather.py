from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QTimer
import json
import urllib.request

NAME = "Live Weather"

# Configuration: Users set Lat/Lon for the API
CONFIG_FIELDS = [
    {"key": "city", "label": "City Name", "default": "Warsaw"},
    {"key": "lat", "label": "Latitude", "default": "52.23"},
    {"key": "lon", "label": "Longitude", "default": "21.01"},
    {"key": "static_mode", "label": "Widget Mode", "default": "False",
     "options": ["False", "True"]}
]

def setup(tile):
    # 1. Cleanup old widgets
    while tile.live_layout.count():
        item = tile.live_layout.takeAt(0)
        if item.widget(): item.widget().deleteLater()

    # 2. Create UI Elements
    # Big Temperature Text
    temp_lbl = QLabel("--°")
    temp_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    temp_lbl.setStyleSheet("font-family: 'Segoe UI Light'; font-size: 42px; color: white; background: transparent;")
    
    # Condition / City Text
    desc_lbl = QLabel("Loading...")
    desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    desc_lbl.setStyleSheet("font-family: 'Segoe UI'; font-size: 14px; color: #eee; background: transparent;")
    desc_lbl.setWordWrap(True)
    
    tile.live_layout.addWidget(temp_lbl)
    tile.live_layout.addWidget(desc_lbl)
    tile.live_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # 3. Real Data Fetching Logic (Open-Meteo)
    def refresh_data():
        lat = tile.app_data.get('lat', '52.23')
        lon = tile.app_data.get('lon', '21.01')
        city = tile.app_data.get('city', 'Warsaw')
        
        # API URL (Celsius is the default)
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        
        try:
            # Use urllib so we don't need 'requests' library dependency
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                
                if 'current_weather' in data:
                    cw = data['current_weather']
                    temp = cw['temperature']
                    code = cw['weathercode']
                    
                    # Map WMO Weather Codes to Text
                    condition = "Unknown"
                    if code == 0: condition = "Clear Sky"
                    elif code in [1, 2, 3]: condition = "Cloudy"
                    elif code in [45, 48]: condition = "Fog"
                    elif code in [51, 53, 55]: condition = "Drizzle"
                    elif code in [61, 63, 65]: condition = "Rain"
                    elif code in [71, 73, 75]: condition = "Snow"
                    elif code in [80, 81, 82]: condition = "Showers"
                    elif code in [95, 96, 99]: condition = "Thunderstorm"
                    
                    # Update UI
                    temp_lbl.setText(f"{int(temp)}°")
                    desc_lbl.setText(f"{condition}\n{city}")
                else:
                    desc_lbl.setText("API Error")

        except Exception as e:
            print(f"Weather Fetch Error: {e}")
            desc_lbl.setText("Offline")

    # 4. Timer Setup
    tile.data_timer = QTimer(tile)
    tile.data_timer.timeout.connect(refresh_data)
    # Fetch every 15 minutes (900000 ms) to be polite to the API
    tile.data_timer.start(900000) 
    
    # Initial Fetch
    refresh_data()

    # 5. Apply Widget Mode / Animation Settings
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
    # Opens detailed forecast on click
    import webbrowser
    lat = "52.23" # Fallback
    lon = "21.01"
    # Try to get tile data if possible, otherwise use defaults
    # (Note: 'run' doesn't receive 'tile' object directly in this architecture, 
    # so we use a generic link or could store data on window if needed)
    webbrowser.open(f"https://open-meteo.com/en/docs")
