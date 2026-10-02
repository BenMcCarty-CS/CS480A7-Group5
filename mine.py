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
# Seconds to wait on a request before giving up and retrying, without this a stalled connection hangs forever.
TIMEOUT = 30
# Codes that will never succeed no matter how many times they're retried.
PERMANENT_ERRORS = (404, 410, 422)

HEADERS = {
	"Accept": "application/vnd.github+json",
	"Authorization": f"Bearer {os.getenv("GITHUB_TOKEN")}",
}


def mine(page_limit, url, params, stop_when=None):
	data = []
	params = dict(params)
	params["page"] = 1

	print("Fetching data across pages...")

	while params["page"] <= page_limit:
		print(f" Requesting page {params['page']}...")
		page_data = request(url, params)

		if not page_data:
			break

		data.extend(page_data)
		params["page"] += 1

		# A page shorter than per_page is the last one, so don't spend a request on the empty page after it.
		if len(page_data) < params.get("per_page", 30):
			break

		if stop_when is not None and stop_when(page_data):
			break
	return data


# Retries until the request succeeds. Returns the json response, or None if it permanently failed.
def request(url, params=None):
	while True:
		try:
			response = requests.get(url, headers=HEADERS, params=params, timeout=TIMEOUT)
		except (requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError):
			print("Request timed out... retrying after a brief sleep.")
			time.sleep(5)
			continue
		except requests.exceptions.ConnectionError:
			print("Unable to connect to server! Likely an internet issue... going to sleep for a minute while it hopefully gets resolved.")
			time.sleep(60)
			continue

		action = rateLimitChecker(response)

		if action == "OK":
			return response.json()
		elif action == "SKIP":
			return None


def rateLimitChecker(response):
	if response.status_code == 200:
		return "OK"

	elif response.status_code == 401:
		raise RuntimeError("Received a 401 Unauthorized, check that GITHUB_TOKEN in .env is valid.")

	elif response.status_code == 403 or response.status_code == 429:
		rateLimitHandler(response)
		return "RESET"

	elif response.status_code in PERMANENT_ERRORS:
		print(f"Received a {response.status_code} for {response.url}, skipping it.")
		return "SKIP"

	else:
		print(f"A non-standard HTTP code has been received: {response.status_code}\nSleeping for 1 minute to see if it resolves the problem.")
		time.sleep(60)
		return "RESET"


# Follows GitHub's guidance: retry-after takes priority, then the hourly reset if it's been used up, otherwise wait a minute.
def rateLimitHandler(response):
	retry_after = response.headers.get("retry-after")
	remaining = response.headers.get("x-ratelimit-remaining")
	reset_time = response.headers.get("x-ratelimit-reset")

	if retry_after is not None:
		print(f"Short term rate limit encountered! Sleeping for {retry_after} seconds before retrying")
		time.sleep(int(retry_after) + 2)

	elif remaining == "0" and reset_time is not None:
		sleep_duration = max(int(reset_time) - time.time(), 0)
		print(f"Hourly rate limit encountered! Sleeping for {int(sleep_duration)} seconds before retrying")
		time.sleep(sleep_duration + 2)

	else:
		print(f"A {response.status_code} occured without being a ratelimiter... might be a token issue?\nSleeping for 1 minute to see if it resolves the problem.")
		time.sleep(60)
