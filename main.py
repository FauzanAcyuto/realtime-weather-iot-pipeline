import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import sleep

import numpy as np
import requests
from pymongo import MongoClient, errors

with open("creds/creds.json", "r") as file:
    creds = json.load(file)
    APIKEY = creds["openweatherapikey"]
    MONGODB_URI = creds["mongodb-uri"]
    HEALTHCHECK_URL = creds["healthcheck-url"]
BASEURL = "https://api.openweathermap.org/data/2.5/weather"

# Coordinates for data gathering
lat = 2.133485
lon = 117.596245
COORDINATES = [
    (2.187184, 117.639600),
    (2.066438, 117.639600),
    (2.066438, 117.560116),
    (2.187184, 117.560116),
]

# logging parameters
LOG_LEVEL = logging.INFO
LOG_FILE_PATH = "logs/open-weather-reader.log"
LOG_SIZE_MB = 1
LOG_FILES_TO_KEEP = 5

# Connection Pool Config
CONN_POOL_CONFIG = {
    "maxPoolSize": 5,
    "minPoolSize": 1,
    "maxIdleTimeMS": 60000,
    "connectTimeoutMS": 60000,
    "serverSelectionTimeoutMS": 30000,
    "retryWrites": True,
    "retryReads": True,
}
MONGODB_MAX_RETRIES = 5


def main():
    logger = logging.getLogger(__name__)
    processed_data = 0
    weather_area = get_grid_coordinates(COORDINATES, grid=8)

    logger.info("Attempting to connect to MongoDB Server")
    with MongoClient(MONGODB_URI, **CONN_POOL_CONFIG) as client:
        # Test mongoDB connection
        try:
            logger.info("Initiate connection test")
            client.admin.command("ping")
            logger.info("MongoDB connection successful!")
        except Exception:
            logger.exception("MongoDB Connection Failure!")

        while True:
            for lat, lon in weather_area:
                data = get_current_weather(BASEURL, APIKEY, lat, lon)
                if data == {}:
                    logger.error(
                        "Attempted to insert data of length 0 to mongoDB, skipping"
                    )
                    continue
                else:
                    data_length = len(data)
                    logger.debug(
                        f"Api request finished for data of length {data_length}"
                    )

                insert_data_to_mongodb(
                    client,
                    database="weather-tracking-system",
                    collection="open-weather-raw",
                    data=data,
                    max_retries=5,
                )

                processed_data += 1

                if processed_data % 25 == 0:
                    logger.info(
                        f"Processed {processed_data} data to mongodb, continuing..."
                    )
                    healthcheck(HEALTHCHECK_URL)

                sleep(1.5)  # read interval


def get_grid_coordinates(corners, grid=8):
    logger = logging.getLogger(__name__)
    logger.info("Getting weather grid coordinates...")

    lat = [x for x, y in corners]
    lon = [y for x, y in corners]

    lat_points = np.linspace(min(lat), max(lat), grid)
    lon_points = np.linspace(min(lon), max(lon), grid)

    grid_coords = [(lat, lon) for lat in lat_points for lon in lon_points]
    logger.info("Grid coordinates obtained")
    return grid_coords


def setup_logger(loglevel, log_file, logsize, files_to_keep):
    """
    loglevel(obj) = log level object (logging.INFO)
    log_file(str) = path to log file (../log/etl.log)
    logsize(int) = size of log files before rotated (in MB)
    files_to_keep = number of rotated files to keep
    """
    # Create log directory
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Setup logging
    logging.basicConfig(
        handlers=[
            RotatingFileHandler(
                log_file,
                maxBytes=logsize * 1024 * 1024,
                backupCount=files_to_keep,
            ),
            logging.StreamHandler(),
        ],
        level=loglevel,
        format="%(asctime)s - %(levelname)s - %(message)s",
        force=True,  # Override any existing config
    )

    logger = logging.getLogger()
    logger.info(f"Logging initialized → {log_file}")
    return logger


def get_current_weather(url, appid, lat, lon, query_dict={}):
    logger = logging.getLogger(__name__)
    logger.debug(f"Getting weather api data for {lat},{lon}")
    requiredparams = {"appid": APIKEY, "lat": lat, "lon": lon}
    getparams = {**requiredparams, **query_dict}
    response = requests.get(BASEURL, params=getparams)
    status_code = response.status_code
    resp_dict = json.loads(response.text)

    if status_code == 200:
        logger.debug("Api call successful!")
        return resp_dict
    else:
        errmsg = resp_dict["message"]
        logger.error(f"API Error with with message :{errmsg} code {status_code}")
        return {}


def insert_data_to_mongodb(client, database, collection, data, max_retries):
    logger = logging.getLogger(__name__)

    # Add processing metadata
    data["processed_at"] = None
    data["inserted_at"] = datetime.now(UTC)

    db = client[database]
    coll = db[collection]

    for attempt in range(max_retries + 1):
        try:
            result = coll.insert_one(data)
            print(result.inserted_id)
            return result
        except errors.AutoReconnect:
            if attempt + 1 == max_retries:
                logger.error("Max retries exceeded, mongodb reconnection has failed")
                raise
            retry_pause = (attempt + 1) ** 2
            logger.warning(
                f"Mongo Connection Issues, currently on retry {attempt + 1}, pausing for {retry_pause} seconds before next try."
            )
            sleep(retry_pause)


def healthcheck(hcurl):
    logger = logging.getLogger()

    try:
        requests.get(hcurl, timeout=10)
    except requests.RequestException:
        logger.exception("Health check ping failure")


if __name__ == "__main__":
    setup_logger(LOG_LEVEL, LOG_FILE_PATH, LOG_SIZE_MB, LOG_FILES_TO_KEEP)
    main()
