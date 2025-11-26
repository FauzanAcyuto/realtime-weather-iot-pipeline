# Real-Time Weather Data Ingestion System

A production-grade Python application that continuously collects weather data from OpenWeatherMap API and stores it in MongoDB for analysis. Designed for IoT and environmental monitoring use cases in remote locations.

## 🎯 Project Overview

**Business Context:** Mining and agriculture operations in remote Australian regions require real-time weather monitoring for operational safety and efficiency. This system demonstrates scalable data ingestion for environmental sensor networks.

**Key Features:**
- Grid-based geographical sampling (64 collection points)
- Automatic reconnection and retry logic
- Production logging with rotation
- MongoDB connection pooling
- Rate-limited API calls (respects free tier limits)
- Graceful shutdown handling

## 🏗️ Architecture
```
OpenWeatherMap API (8x8 grid)
         ↓
   Python Ingestion Script
   • Retry logic
   • Error handling
   • Logging
         ↓
   MongoDB (raw data store)
   • Connection pooling
   • Metadata tagging
         ↓
   [Next: Pandas analysis]
```

## 📊 Data Model

**Collection:** `open-weather-raw`

**Sample Document:**
```json
{
  "coord": {"lat": 2.187, "lon": 117.640},
  "weather": [{"main": "Rain", "description": "light rain"}],
  "main": {
    "temp": 299.15,
    "humidity": 89,
    "pressure": 1010
  },
  "wind": {"speed": 3.5, "deg": 180},
  "inserted_at": "2024-11-25T10:30:00Z",
  "processed_at": null
}
```

## 🛠️ Technology Stack

- **Language:** Python 3.11+
- **Database:** MongoDB 7.0
- **Package Manager:** uv
- **Key Libraries:** 
  - pymongo (MongoDB driver)
  - requests (API calls)
  - numpy (grid calculations)

## 🚀 Setup Instructions

### Prerequisites
- Python 3.11+
- MongoDB instance (local or cloud)
- OpenWeatherMap API key (free tier)

### Installation

1. **Clone repository:**
```bash
git clone https://github.com/yourusername/weather-ingestion.git
cd weather-ingestion
```

2. **Create virtual environment:**
```bash
uv venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows
```

3. **Install dependencies:**
```bash
uv pip install -r requirements.txt
```

4. **Configure credentials:**
```bash
# Create .env file
cp .env.example .env

# Edit .env with your credentials:
# OPENWEATHER_API_KEY=your_api_key_here
# MONGODB_URI=mongodb://localhost:27017/
```

5. **Run the script:**
```bash
python main.py
```

### Deployment (Linux systemd)

See `deployment/` folder for systemd service configuration.

## 📈 Data Collection Statistics

**Coverage Area:** ~100 km² grid in Borneo
**Collection Points:** 64 locations
**Sampling Rate:** ~1.5 seconds per point
**Daily Volume:** ~35,000 records/day
**Storage:** ~5-7 MB/day (JSON documents)

## 🎓 Learning Outcomes

This project demonstrates:

1. **Production Python Development:**
   - Proper logging and monitoring
   - Error handling and retries
   - Configuration management
   - Virtual environment usage

2. **Database Operations:**
   - MongoDB connection pooling
   - Document insertion
   - Metadata management
   - Connection resilience

3. **API Integration:**
   - Rate limiting
   - Error handling
   - Grid-based sampling
   - Retry logic

4. **DevOps Practices:**
   - systemd service deployment
   - Log rotation
   - Health monitoring
   - Graceful shutdown

## 🔜 Next Steps

- [ ] Pandas analysis notebook (data exploration)
- [ ] AWS S3 export (cloud data lake)
- [ ] Airflow orchestration (scheduled exports)
- [ ] dbt transformations (analytics models)
- [ ] Power BI/Tableau dashboards

## 📝 Use Cases

**Mining Operations:**
- Heat stress monitoring (safety alerts at >35°C)
- Dust suppression planning (humidity + wind analysis)
- Equipment efficiency optimization

**Agriculture:**
- Irrigation scheduling (evapotranspiration calculation)
- Frost risk alerts
- Spray window prediction

## 🤝 Contributing

This is a portfolio project, but feedback is welcome! Open an issue or submit a PR.

## 📄 License

MIT License - see LICENSE file

## 👤 Author

[Your Name]
- LinkedIn: [your-profile]
- GitHub: [your-username]
- Portfolio: [your-website]

---

**Built as part of Australian data career transition preparation.**