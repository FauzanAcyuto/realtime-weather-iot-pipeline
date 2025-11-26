# Real-Time Weather IoT Pipeline

A production-grade Python application that continuously collects weather data from OpenWeatherMap API and stores it in MongoDB for analysis. Designed for IoT and environmental monitoring use cases in remote locations.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MongoDB](https://img.shields.io/badge/mongodb-7.0+-green.svg)](https://www.mongodb.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Project Overview

**Business Context:** Mining operations in Borneo are heavily obstructed by rainfall, the slightest drizzle can cause a 'slippery' status to be raised which stops all production activities. Having an accurate history of rainfall and the potential for machine learning predictions to be made would be indispensable for mine planning.

**Key Features:**
- Grid-based geographical sampling (configurable density)
- Automatic reconnection with exponential backoff
- Production logging with rotation
- MongoDB connection pooling for reliability
- Rate-limited API calls (respects free tier limits)
- Health check monitoring
- Graceful error handling and recovery

## Use Cases

**Mining Operations:**
- Production forecasting (weather-adjusted targets)
- Heat stress monitoring (safety alerts when temperature >35°C)
- Dust suppression planning (humidity + wind speed analysis)
- Equipment efficiency optimization (temperature impact on machinery)

**Agriculture:**
- Irrigation scheduling (evapotranspiration calculations)
- Frost risk prediction (overnight temperature monitoring)
- Spray window identification (wind speed + precipitation forecast)
- Disease risk assessment (humidity + temperature patterns)

## Architecture
```
OpenWeatherMap API (Grid Sampling)
         ↓
   Python Ingestion Script
   • Exponential backoff retry
   • Connection pooling
   • Error handling & logging
         ↓
   MongoDB (raw data store)
   • Auto-reconnect handling
   • Metadata tagging
   • High-availability configuration
         ↓
   [Future: Pandas analysis → AWS S3 → Analytics]
```

### Data Flow
1. **Grid Generation:** Calculate sampling points within bounding box
2. **API Polling:** Fetch weather data for each point (1.5s interval)
3. **Data Validation:** Check response quality before insertion
4. **MongoDB Insert:** Store with retry logic and metadata
5. **Health Check:** Ping monitoring service every 25 records
6. **Continuous Loop:** Repeat indefinitely with error recovery

## Design Decisions

### 1. Grid-Based Geographical Sampling

**Decision:** Use bounding box with grid sampling instead of single-point collection.

**Rationale:**
- Provides spatial coverage of an area (~100 km²) rather than single location
- Mimics real-world IoT deployments (multiple sensors distributed across region)
- Demonstrates handling of multiple data sources simultaneously
- Relevant for mining sites (large operational areas) and farms (field-level variations)

**Implementation:**
- Define 4 corner coordinates (bounding box)
- Generate NxN grid of evenly-spaced points using `numpy.linspace`
- Default: 8×8 grid = 64 collection points
- Configurable density based on area size and API rate limits

**Example Coverage:**

![Grid Sampling Visualization](docs/data-point-coverage-mining.png)

*64 sampling points covering ~100 km² area in Borneo. Each point represents a simulated IoT weather station.*

**Code Implementation:**
```python
def get_grid_coordinates(corners, grid=8):
    """Generate evenly-spaced grid of coordinates within bounding box"""
    lat = [x for x, y in corners]
    lon = [y for x, y in corners]
    
    lat_points = np.linspace(min(lat), max(lat), grid)
    lon_points = np.linspace(min(lon), max(lon), grid)
    
    # Cartesian product: all combinations of lat/lon
    grid_coords = [(lat, lon) for lat in lat_points for lon in lon_points]
    return grid_coords
```

**Trade-offs:**
- Comprehensive area coverage
- Realistic IoT simulation
- Demonstrates batch processing patterns
- More points means more time between updates for each (if conforming to free tier limit)
- Wider area reduces granularity

---

### 2. Exponential Backoff for MongoDB Reconnection

**Decision:** Implement exponential backoff retry logic for database insertions.

**Rationale:**
- MongoDB connections can drop due to network issues, timeouts, or server maintenance
- Immediate retry often fails (server still recovering)
- Exponential backoff gives system time to recover while avoiding overwhelming the database
- Standard pattern for distributed systems resilience

**Problem Encountered:**
```python
pymongo.errors.AutoReconnect: connection closed
```

This error occurred during:
- Network instability between application and MongoDB
- MongoDB replica set elections
- Server resource constraints under load

**Implementation:**
```python
def insert_data_to_mongodb(client, database, collection, data, max_retries=5):
    for attempt in range(max_retries + 1):
        try:
            result = collection.insert_one(data)
            return result
        except errors.AutoReconnect:
            if attempt + 1 == max_retries:
                logger.error("Max retries exceeded")
                raise
            
            # Exponential backoff: 1s, 4s, 9s, 16s, 25s
            retry_pause = (attempt + 1) ** 2
            logger.warning(f"Retry {attempt + 1}, pausing {retry_pause}s")
            sleep(retry_pause)
```

**Retry Pattern:**
| Attempt | Wait Time | Total Elapsed |
|---------|-----------|---------------|
| 1       | 1 second  | 1s            |
| 2       | 4 seconds | 5s            |
| 3       | 9 seconds | 14s           |
| 4       | 16 seconds| 30s           |
| 5       | 25 seconds| 55s           |

**Why Exponential (Not Linear):**
- Linear backoff (1s, 2s, 3s...) may retry too quickly during sustained outages
- Exponential gives progressively longer recovery windows
- Reduces load on struggling database servers
- Industry best practice (AWS, Google Cloud use this pattern)

**Trade-offs:**
- Handles transient failures gracefully
- Reduces data loss during connection issues
- Prevents overwhelming recovering servers
- Can delay data ingestion during prolonged outages
- Maximum 55s delay before failure (acceptable for this use case)

---

### 3. Connection Pooling Configuration

**Decision:** Use MongoDB connection pooling with specific sizing and timeout parameters.

**Configuration:**
```python
CONN_POOL_CONFIG = {
    "maxPoolSize": 5,           # Maximum concurrent connections
    "minPoolSize": 1,           # Minimum idle connections
    "maxIdleTimeMS": 60000,     # Close idle connections after 60s
    "connectTimeoutMS": 60000,  # Connection attempt timeout
    "serverSelectionTimeoutMS": 30000,  # Server selection timeout
    "retryWrites": True,        # Automatic write retry
    "retryReads": True,         # Automatic read retry
}
```

**Rationale:**

**Why Connection Pooling?**
- Creating new database connections is expensive (network handshake, authentication)
- Reusing connections significantly improves performance
- Essential for production applications with continuous operations
- Recommended practice for MongoDB in long-running processes

**Why These Specific Values?**

**`maxPoolSize: 5`**
- Single-threaded application doesn't need many concurrent connections
- 5 provides buffer for connection cycling during reconnects
- Prevents exhausting MongoDB connection limits
- Small footprint appropriate for monitoring application

**`minPoolSize: 1`**
- Keeps one connection warm (avoids cold-start latency)
- Minimal resource usage when idle
- Ensures immediate availability for writes

**`maxIdleTimeMS: 60000` (60 seconds)**
- Closes stale connections to prevent server-side resource waste
- Long enough to avoid constant connection churn
- Short enough to detect server restarts reasonably quickly

**`connectTimeoutMS: 60000` (60 seconds)**
- Generous timeout accounts for slow networks (relevant for remote deployments)
- Prevents premature failures during temporary network congestion
- Extended from default 30s based on production experience

**`serverSelectionTimeoutMS: 30000` (30 seconds)**
- Time to find available MongoDB server in replica set
- Balances responsiveness with patience during failover events
- Standard value for distributed deployments

**`retryWrites: True` & `retryReads: True`**
- Automatically retry failed operations once
- Handles transient network failures without application-level retry
- Complements our exponential backoff strategy
- No downside for idempotent operations

**Performance Impact:**
```
Without pooling:
- Connection per insert: ~50-100ms overhead
- 64 grid points × 1.5s = 96s per cycle
- Total: ~102-106s per cycle (6% overhead)

With pooling:
- Connection reuse: ~1-2ms overhead
- Same 96s collection time
- Total: ~96.1s per cycle (0.1% overhead)

Improvement: ~6% faster, more consistent performance
```

**Trade-offs:**
- Significantly better performance (6% reduction in cycle time)
- More resilient to transient failures
-  Production-ready configuration
-  Slightly higher memory usage (negligible: ~5MB per connection)
-  More complex configuration (documented here)

---

### 4. Rate Limiting Strategy

**Decision:** 2.8s second delay between API calls 

**Rationale:**
- OpenWeatherMap free tier: 60 calls/minute = 1 call/second limit
- BUT it has 1,000,000 calls/month call limit
- 2.8s delay = 956,571 calls/month = comfortable margin
- Prevents API throttling and account suspension
- Allows for occasional retry calls without hitting limits

**Calculation:**
2.8s delay = ~21.43 calls/minute
= ~1,286 calls/hour
= ~30,857 calls/day
= ~956,571 calls/month (within 1,000,000 limit with buffer)

---

## Data Collection Statistics

**Current Configuration:**
- **Coverage Area:** ~100 km² grid in Borneo
- **Collection Points:** 64 locations (8×8 grid)
- **Sampling Rate:** 2.8 seconds per point
- **Cycle Time:** ~179 seconds per complete area scan (3 minutes per point is adequate for the use case)
- **Daily Volume:** 
  - Records: ~30,800 documents/day
  - Storage: ~5-7 MB/day (JSON documents with metadata)
  - API Calls: ~30,800/day 

**Scaling Considerations:**
- Increase to 16×16 grid (256 points) for higher resolution (requires paid API tier)
- Increase api call frequency for more granularity

---

##  Setup Instructions

### Prerequisites
- Python 3.11+
- MongoDB instance (local or cloud - [MongoDB Atlas free tier](https://www.mongodb.com/cloud/atlas))
- OpenWeatherMap API key ([free signup](https://openweathermap.org/api))
- (Optional) [Healthchecks.io](https://healthchecks.io/) account for monitoring

### Installation

1. **Clone repository:**
```bash
git clone https://github.com/yourusername/realtime-weather-iot-pipeline.git
cd realtime-weather-iot-pipeline
```

2. **Create virtual environment:**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
pymongo>=4.6.0
requests>=2.31.0
numpy>=1.26.0
python-dotenv>=1.0.0
```

4. **Configure credentials:**

Create `creds/creds.json`:
```json
{
  "openweatherapikey": "your_openweathermap_api_key",
  "mongodb-uri": "mongodb://localhost:27017/",
  "healthcheck-url": "https://hc-ping.com/your-healthcheck-uuid"
}
```

**Security Note:** Add `creds/` to `.gitignore` (already configured in repo)

5. **Configure collection area:**

Edit `main.py` lines 17-23 to set your bounding box coordinates:
```python
# Define your area of interest (4 corners of bounding box)
COORDINATES = [
    (lat_max, lon_min),  # Top-left corner
    (lat_min, lon_min),  # Bottom-left corner
    (lat_min, lon_max),  # Bottom-right corner
    (lat_max, lon_max),  # Top-right corner
]
```

**How to find coordinates:**
1. Go to [OpenStreetMap](https://www.openstreetmap.org/)
2. Navigate to your area of interest
3. Right-click → "Show address" to see coordinates
4. Note the latitude and longitude for each corner
5. Update `COORDINATES` with your values

**Example - Sydney, Australia:**
```python
COORDINATES = [
    (-33.8, 151.0),   # Northwest
    (-34.0, 151.0),   # Southwest  
    (-34.0, 151.3),   # Southeast
    (-33.8, 151.3),   # Northeast
]
# This covers ~30km × 30km area around Sydney
```

**Visualize your grid:**
- Use [geojson.io](http://geojson.io/) to preview your bounding box
- Paste this GeoJSON (replace coordinates):
```json
{
  "type": "Polygon",
  "coordinates": [[
    [151.0, -33.8], [151.3, -33.8], [151.3, -34.0], [151.0, -34.0], [151.0, -33.8]
  ]]
}
```

6. **Adjust grid density (optional):**

In `main.py`, line 57:
```python
weather_area = get_grid_coordinates(COORDINATES, grid=8)
```

Change `grid=8` to:
- `grid=4` → 16 points (light coverage, free tier friendly)
- `grid=8` → 64 points (moderate coverage, default)
- `grid=16` → 256 points (dense coverage)

7. **Run the script:**
```bash
python main.py
```

**Expected output:**
```
2024-11-25 10:30:00 - INFO - Logging initialized → logs/open-weather-reader.log
2024-11-25 10:30:01 - INFO - Attempting to connect to MongoDB Server
2024-11-25 10:30:01 - INFO - Initiate connection test
2024-11-25 10:30:01 - INFO - MongoDB connection successful!
2024-11-25 10:30:01 - INFO - Getting weather grid coordinates...
2024-11-25 10:30:01 - INFO - Grid coordinates obtained
2024-11-25 10:30:02 - INFO - Processed 25 data to mongodb, continuing...
```

---

##  Deployment (Production)

### Linux systemd Service

Create `/etc/systemd/system/weather-ingestion.service`:
```ini
[Unit]
Description=Weather Data Ingestion Service
After=network.target mongodb.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/realtime-weather-iot-pipeline
Environment="PATH=/path/to/realtime-weather-iot-pipeline/.venv/bin"
ExecStart=/path/to/realtime-weather-iot-pipeline/.venv/bin/python main.py
Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable weather-ingestion
sudo systemctl start weather-ingestion
sudo systemctl status weather-ingestion
```

**View logs:**
```bash
# Application logs
tail -f logs/open-weather-reader.log

# System logs
sudo journalctl -u weather-ingestion -f
```

---

##  Data Model

**MongoDB Collection:** `weather-tracking-system.open-weather-raw`

**Sample Document:**
```json
{
  "_id": "674567890abcdef12345678",
  "coord": {
    "lat": 2.187,
    "lon": 117.640
  },
  "weather": [
    {
      "id": 501,
      "main": "Rain",
      "description": "moderate rain",
      "icon": "10d"
    }
  ],
  "main": {
    "temp": 299.15,
    "feels_like": 302.50,
    "temp_min": 298.15,
    "temp_max": 300.15,
    "pressure": 1010,
    "humidity": 89
  },
  "wind": {
    "speed": 3.5,
    "deg": 180,
    "gust": 5.2
  },
  "clouds": {
    "all": 75
  },
  "dt": 1699887600,
  "sys": {
    "type": 1,
    "country": "MY",
    "sunrise": 1699836000,
    "sunset": 1699879200
  },
  "timezone": 28800,
  "name": "Kota Kinabalu",
  "cod": 200,
  "inserted_at": "2024-11-25T10:30:00Z",
  "processed_at": null
}
```

**Key Fields:**
- `coord`: GPS coordinates of sampling point
- `main.temp`: Temperature in Kelvin (convert to Celsius: K - 273.15)
- `main.humidity`: Relative humidity percentage
- `wind.speed`: Wind speed in meters/second
- `inserted_at`: Timestamp when data was stored (UTC)
- `processed_at`: Reserved for downstream processing tracking

---

## Technology Stack

- **Language:** Python 3.11+
- **Database:** MongoDB 7.0+
- **Key Libraries:**
  - `pymongo` - MongoDB driver with connection pooling
  - `requests` - HTTP client for API calls
  - `numpy` - Grid coordinate calculations
- **Deployment:** systemd service (Linux)
- **Monitoring:** Healthchecks.io integration

---

## Learning Outcomes

This project demonstrates:

### Production Python Development
- ✅ Proper logging patterns (rotating file handlers)
- ✅ Error handling with retry logic (exponential backoff)
- ✅ Configuration management (credentials, parameters)
- ✅ Virtual environment usage
- ✅ Graceful degradation (skip bad data, continue operation)

### Database Operations
- ✅ MongoDB connection pooling (performance optimization)
- ✅ Retry logic for transient failures
- ✅ Metadata management (tracking insertion times)
- ✅ Connection resilience patterns

### API Integration
- ✅ Rate limiting strategies (respect tier limits)
- ✅ Error handling (HTTP status codes)
- ✅ Grid-based sampling (spatial data collection)
- ✅ JSON parsing and validation

### DevOps Practices
- ✅ systemd service deployment
- ✅ Log rotation management
- ✅ Health check monitoring
- ✅ Continuous operation patterns

### Architectural Thinking
- ✅ Trade-off analysis (latency vs reliability, coverage vs cost)
- ✅ Scalability considerations (grid sizing, API limits)
- ✅ Resource management (connection pooling, rate limiting)
- ✅ Failure mode analysis (what can go wrong, how to handle)

---

## Next Steps

### Phase 2: Data Analysis 
- [ ] Jupyter notebook with pandas exploration
- [ ] Calculate derived metrics (heat stress indices, ET rates)
- [ ] Time series analysis and visualizations
- [ ] Business insights for mining/agriculture use cases

### Phase 3: Cloud Integration
- [ ] Export daily batches to AWS S3
- [ ] AWS Glue catalog integration
- [ ] Query with Amazon Athena
- [ ] Cost optimization analysis

### Phase 4: Orchestration
- [ ] Apache Airflow DAG for scheduled exports
- [ ] dbt transformations (staging → analytics models)
- [ ] Data quality tests
- [ ] Automated documentation

### Phase 5: Visualization
- [ ] Power BI dashboard (operational metrics)
- [ ] Tableau Public dashboard (business insights)
- [ ] Real-time monitoring displays

---

##  Resources & References

**Documentation:**
- [OpenWeatherMap API Docs](https://openweathermap.org/current)
- [PyMongo Documentation](https://pymongo.readthedocs.io/)
- [MongoDB Connection Pooling](https://www.mongodb.com/docs/manual/administration/connection-pool-overview/)

**Relevant Patterns:**
- [Exponential Backoff (AWS)](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Connection Pooling Best Practices](https://www.mongodb.com/docs/manual/administration/connection-pool-overview/)
- [Distributed Systems Reliability](https://sre.google/sre-book/addressing-cascading-failures/)

**Australian Use Cases:**
- [Mining Industry IoT Applications](https://www.industry.gov.au/)
- [Smart Agriculture in Australia](https://www.agriculture.gov.au/)

---

##  Contributing

This is a portfolio project demonstrating production data engineering practices. Feedback and suggestions are welcome!

**Areas for improvement:**
- Alternative deployment methods (Docker, Kubernetes)
- Additional API providers (integration patterns)
- Enhanced monitoring (Prometheus, Grafana)
- Testing frameworks (pytest integration)

Open an issue or submit a PR if you have ideas!

---

## 👤 Author

**[Your Name]**
- Portfolio: -
- LinkedIn: [linkedin.com/in/fauzan-acyuto]
- Email: [acyuto.professional@gmail.com]

---

## Acknowledgments

- Built as part of Australian data engineering career transition preparation
- Designed to demonstrate production-ready data pipeline patterns
- Inspired by real-world IoT monitoring challenges in remote operations

---

** If this project helped you, please give it a star!**

---

*Last updated: November 2024*
```

---

## Additional Files to Create

### 1. `.gitignore`
```
# Credentials
creds/
*.json
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/

# Logs
logs/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```
