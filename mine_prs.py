import os
from dotenv import load_dotenv
from datetime import datetime as dt
from zoneinfo import ZoneInfo
import requests
import csv
import numpy as np
import json

load_dotenv()

OWNER = "zephyrproject-rtos"
REPO = "zepyhr"

CUURENT_TIME = dt.now(tz=ZoneInfo("UTC")).isoformat()

# TODO: add end of URL
URL = f"https://api.github.com/repos/{OWNER}/{REPO}/"


HEADERS = {
	"Accept": "appliction/vnd.github+json",
	"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN)}",
}

PARAMS = {
	"per_page": 100,
}
