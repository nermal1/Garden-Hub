from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
import sqlite3
from datetime import datetime

app = FastAPI()

# --- Database Setup ---
DB_FILE = "garden.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                moisture INTEGER,
                temperature REAL,
                humidity REAL,
                pressure REAL,
                rssi INTEGER
            )
        """)
        conn.commit()

init_db()

# --- API Endpoints ---
@app.post("/api/data")
async def receive_data(request: Request):
    data = await request.json()
    
    AIR_VALUE = 3400   
    WATER_VALUE = 1400 
    
    raw_moisture = int(data.get("moisture", 0))
    moisture_pct = ((AIR_VALUE - raw_moisture) / (AIR_VALUE - WATER_VALUE)) * 100
    moisture_pct = max(0, min(100, round(moisture_pct)))
    
    temp_c = float(data.get("temperature", 0.0))
    temp_f = round((temp_c * 9/5) + 32, 2)
    
    humidity = float(data.get("humidity", 0.0))
    
    # --- PRESSURE CONVERSION HERE ---
    pressure_hpa = float(data.get("pressure", 0.0))
    pressure_inhg = round(pressure_hpa * 0.02953, 2) # Convert hPa to inHg
    
    rssi = int(data.get("rssi", 0))
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sensor_data (moisture, temperature, humidity, pressure, rssi) VALUES (?, ?, ?, ?, ?)",
            (moisture_pct, temp_f, humidity, pressure_inhg, rssi)
        )
        conn.commit()
        
    print(f"Logged: Temp {temp_f}°F, Moisture {moisture_pct}%, Pressure {pressure_inhg}inHg, RSSI {rssi}")
    return {"status": "success"}

@app.get("/api/latest")
async def get_latest():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        
    if row:
        return dict(row)
    return {"moisture": 0, "temperature": 0.0, "humidity": 0.0, "pressure": 0.0, "rssi": 0}

@app.get("/api/history")
async def get_history(timeframe: str = 'daily'):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if timeframe == 'past_hour':
            query = """
                SELECT strftime('%H:%M', timestamp) as time_label,
                       AVG(moisture) as moisture, AVG(temperature) as temperature, 
                       AVG(humidity) as humidity, AVG(pressure) as pressure
                FROM sensor_data WHERE timestamp >= datetime('now', '-1 hour')
                GROUP BY time_label ORDER BY time_label ASC
            """
        elif timeframe == 'hourly':
            query = """
                SELECT strftime('%m-%d %H:00', timestamp) as time_label,
                       AVG(moisture) as moisture, AVG(temperature) as temperature, 
                       AVG(humidity) as humidity, AVG(pressure) as pressure
                FROM sensor_data WHERE timestamp >= datetime('now', '-1 day')
                GROUP BY time_label ORDER BY time_label ASC
            """
        elif timeframe == 'weekly':
            query = """
                SELECT strftime('%Y-%W', timestamp) as time_label,
                       AVG(moisture) as moisture, AVG(temperature) as temperature, 
                       AVG(humidity) as humidity, AVG(pressure) as pressure
                FROM sensor_data WHERE timestamp >= datetime('now', '-28 days')
                GROUP BY time_label ORDER BY time_label ASC
            """
        else: 
            query = """
                SELECT strftime('%Y-%m-%d', timestamp) as time_label,
                       AVG(moisture) as moisture, AVG(temperature) as temperature, 
                       AVG(humidity) as humidity, AVG(pressure) as pressure
                FROM sensor_data WHERE timestamp >= datetime('now', '-7 days')
                GROUP BY time_label ORDER BY time_label ASC
            """
            
        cursor.execute(query)
        rows = cursor.fetchall()
        
    return {"labels": [r["time_label"] for r in rows], 
            "moisture": [r["moisture"] for r in rows], 
            "temperature": [r["temperature"] for r in rows],
            "humidity": [r["humidity"] for r in rows],
            "pressure": [r["pressure"] for r in rows]}

# --- Dashboard HTML ---
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Smart Garden Dashboard</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 20px; margin-bottom: 20px; }
                h1 { color: #bb86fc; margin: 0; }
                .controls select { background-color: #1e1e1e; color: #bb86fc; border: 1px solid #bb86fc; padding: 8px 12px; border-radius: 4px; font-size: 16px; cursor: pointer; }
                
                /* Layout Grids */
                .health-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-bottom: 20px; }
                .live-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
                .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
                
                /* Cards */
                .card { background-color: #1e1e1e; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); text-align: center; }
                .health-card { background-color: #181818; border: 1px solid #333; padding: 15px; border-radius: 8px; text-align: center; }
                .card h3, .health-card h3 { margin-top: 0; color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
                .card .value { font-size: 32px; font-weight: bold; color: #fff; }
                .health-card .value { font-size: 20px; color: #03dac6; font-weight: bold; margin-top: 5px; }
                .health-card .subtext { font-size: 12px; color: #888; margin-top: 5px; }
                
                .progress-bg { background-color: #333; border-radius: 10px; height: 12px; width: 100%; margin-top: 15px; overflow: hidden; }
                .progress-bar { height: 100%; transition: width 0.5s ease, background-color 0.5s ease; width: 0%; }
                .labels { display: flex; justify-content: space-between; font-size: 12px; color: #888; margin-top: 5px; font-weight: bold; }
                .chart-container { background-color: #1e1e1e; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Garden Telemetry</h1>
                    <div class="controls">
                        <select id="timeframe" onchange="updateCharts()">
                            <option value="past_hour">Past Hour (Minute-by-Minute)</option>
                            <option value="hourly">Past 24 Hours</option>
                            <option value="daily" selected>Past 7 Days</option>
                            <option value="weekly">Past 4 Weeks</option>
                        </select>
                    </div>
                </div>

                <div class="health-cards">
                    <div class="health-card">
                        <h3>System Status</h3>
                        <div class="value" id="time-since">Waiting for signal...</div>
                    </div>
                    <div class="health-card">
                        <h3>Hub Wi-Fi Strength</h3>
                        <div class="value" id="rssi">-- dBm</div>
                        <div class="subtext"></div>
                    </div>
                    <div class="health-card">
                        <h3>Predicted Forecast</h3>
                        <div class="value"><span id="forecast-temp">--</span>°F | <span id="forecast-humidity">--</span>%</div>
                        <div class="subtext"></div>
                    </div>
                </div>

                <div class="live-cards">
                    <div class="card">
                        <h3>Garden Moisture</h3>
                        <div class="value" id="moisture">--%</div>
                        <div class="progress-bg"><div class="progress-bar" id="moisture-bar"></div></div>
                        <div class="labels"><span>DRY</span><span>WET</span></div>
                    </div>
                    <div class="card">
                        <h3>Garden Temp (°F)</h3>
                        <div class="value" id="temp">--</div>
                    </div>
                    <div class="card">
                        <h3>Garden Humidity</h3>
                        <div class="value" id="humidity">--%</div>
                    </div>
                    <div class="card">
                        <h3>Atmospheric Pressure</h3>
                        <div class="value" id="pressure">-- inHg</div>
                    </div>
                </div>

                <div class="charts">
                    <div class="chart-container"><canvas id="moistureChart"></canvas></div>
                    <div class="chart-container"><canvas id="tempChart"></canvas></div>
                    <div class="chart-container"><canvas id="pressureChart"></canvas></div>
                </div>
            </div>

            <script>
                Chart.defaults.color = '#888';
                Chart.defaults.borderColor = '#333';
                let moistureChart, tempChart, pressureChart;
                let lastDataTime = Date.now();

                function initCharts() {
                    const ctxMoisture = document.getElementById('moistureChart').getContext('2d');
                    const ctxTemp = document.getElementById('tempChart').getContext('2d');
                    const ctxPressure = document.getElementById('pressureChart').getContext('2d');

                    moistureChart = new Chart(ctxMoisture, {
                        type: 'line',
                        data: { labels: [], datasets: [{ label: 'Avg Moisture (%)', borderColor: '#03dac6', backgroundColor: 'rgba(3, 218, 198, 0.1)', fill: true, data: [], tension: 0.4 }] },
                        options: { responsive: true, scales: { y: { min: 0, max: 100 } }, plugins: { title: { display: true, text: 'Soil Moisture Trend', color: '#fff' } } }
                    });

                    tempChart = new Chart(ctxTemp, {
                        type: 'line',
                        data: { labels: [], datasets: [{ label: 'Avg Temperature (°F)', borderColor: '#cf6679', backgroundColor: 'rgba(207, 102, 121, 0.1)', fill: true, data: [], tension: 0.4 }] },
                        options: { responsive: true, plugins: { title: { display: true, text: 'Temperature Trend', color: '#fff' } } }
                    });
                    
                    pressureChart = new Chart(ctxPressure, {
                        type: 'line',
                        data: { labels: [], datasets: [{ label: 'Avg Pressure (inHg)', borderColor: '#bb86fc', backgroundColor: 'rgba(187, 134, 252, 0.1)', fill: true, data: [], tension: 0.4 }] },
                        options: { responsive: true, plugins: { title: { display: true, text: 'Pressure Trend', color: '#fff' } } }
                    });
                }

                async function fetchLive() {
                    try {
                        const res = await fetch('/api/latest');
                        const data = await res.json();
                        
                        if(data.moisture !== undefined && data.timestamp) {
                            lastDataTime = Date.now(); 
                            
                            document.getElementById('moisture').innerText = data.moisture + '%';
                            document.getElementById('temp').innerText = data.temperature.toFixed(1);
                            document.getElementById('humidity').innerText = data.humidity.toFixed(1) + '%';
                            document.getElementById('pressure').innerText = data.pressure.toFixed(2) + ' inHg';
                            document.getElementById('rssi').innerText = data.rssi + ' dBm';
                            
                            const bar = document.getElementById('moisture-bar');
                            bar.style.width = data.moisture + '%';
                            bar.style.backgroundColor = data.moisture < 30 ? '#cf6679' : '#03dac6';
                        }
                    } catch (e) {
                        console.error("Error fetching live data", e);
                    }
                }
                
                async function fetchForecast() {
                    try {
                        const res = await fetch('https://api.open-meteo.com/v1/forecast?latitude=42.27&longitude=-89.09&current=temperature_2m,relative_humidity_2m&temperature_unit=fahrenheit');
                        const data = await res.json();
                        document.getElementById('forecast-temp').innerText = data.current.temperature_2m;
                        document.getElementById('forecast-humidity').innerText = data.current.relative_humidity_2m;
                    } catch (e) {
                        console.error("Error fetching forecast", e);
                    }
                }

                async function updateCharts() {
                    const tf = document.getElementById('timeframe').value;
                    const res = await fetch(`/api/history?timeframe=${tf}`);
                    const data = await res.json();

                    moistureChart.data.labels = data.labels;
                    moistureChart.data.datasets[0].data = data.moisture;
                    moistureChart.update();

                    tempChart.data.labels = data.labels;
                    tempChart.data.datasets[0].data = data.temperature;
                    tempChart.update();
                    
                    pressureChart.data.labels = data.labels;
                    pressureChart.data.datasets[0].data = data.pressure;
                    pressureChart.update();
                }

                setInterval(() => {
                    const secondsAgo = Math.floor((Date.now() - lastDataTime) / 1000);
                    const timeEl = document.getElementById('time-since');
                    timeEl.innerText = `Online (Updated ${secondsAgo}s ago)`;
                    
                    if (secondsAgo > 15) {
                        timeEl.style.color = '#cf6679';
                        timeEl.innerText = `OFFLINE (Last seen ${secondsAgo}s ago)`;
                    } else {
                        timeEl.style.color = '#03dac6';
                    }
                }, 1000);

                initCharts();
                updateCharts();
                fetchForecast(); 
                
                setInterval(fetchLive, 2000); 
                setInterval(updateCharts, 15000); 
                setInterval(fetchForecast, 300000); 
            </script>
        </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)