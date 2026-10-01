import os
from dotenv import load_dotenv
from datetime import datetime as dt
import time
import requests

load_dotenv()

OWNER = "zephyrproject-rtos"
REPO = "zephyr"
URL = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"
EARLIEST_TIME = dt.fromisoformat("2021-09-29T23:59:59Z")
LATEST_TIME = dt.fromisoformat("2026-09-30T00:00:01Z")

HEADERS = {
	"Accept": "appliction/vnd.github+json",
	"Authorization": f"Bearer {os.getenv("GITHUB_TOKEN")}",
}


def mine(page_limit, url, params):
		data = []
		has_more_pages = True

		print("Fetching data across pages...")

		while has_more_pages:
			print(f" Requesting page {params['page']}...")
			response = requests.get(url, headers=HEADERS, params=params)
			response.raise_for_status()

			action = rateLimitChecker(response)
			
			if(action == "RESET"):
				continue
	
			page_data = response.json()
			
			if not page_data or params["page"] > page_limit:
				has_more_pages = False
				break

			data.extend(page_data)	
			params["page"] += 1
		params["page"] = 1
		return data


def rateLimitChecker(response):
	if response.status_code == 200:
		return "OK"
	
	elif response.status_code == 403 or response.status_code == 429:
		rateLimitHandler(response)
		return "RESET"
	
	else:
		print(f"A non-standard HTTP code has been received: {response.status_code}\nSleeping for 1 minute to see if it resolves the problem.")
		time.sleep(60)
		return "RESET"


def rateLimitHandler(response):
	reset_time = int(response.headers.get("x-ratelimit-reset", -1))

	if(reset_time == -1):
		retryAfterHandler(response)

	else:
		current_time = time.time()
		sleep_duration = reset_time - current_time

		print(f"Hourly rate limit encountered! Sleeping for {int(sleep_duration)} seconds before retrying")
		time.sleep(reset_time + 2)


def retryAfterHandler(response):
	retry_after = int(response.headers.get("retry-after", -1))

	if(retry_after == -1):
		print(f"A {response.status_code} occured without being a ratelimiter... might be a token issue?\nSleeping for 1 minute to see if it resolves the problem.")
		time.sleep(60)

	else:
		print(f"Short term rate limit encountered! Sleeping for {retry_after} seconds before retrying")
		time.sleep(retry_after + 2)