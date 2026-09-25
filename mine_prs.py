import os
from dotenv import load_dotenv
from datetime import datetime as dt
from zoneinfo import ZoneInfo
import requests
import csv
import json

load_dotenv()

OWNER = "zephyrproject-rtos"
REPO = "zephyr"
URL = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"
EARLIEST_TIME = dt.fromisoformat("2021-09-24T23:59:59Z")
LATEST_TIME = dt.fromisoformat("2026-09-25T00:00:01Z")

HEADERS = {
	"Accept": "appliction/vnd.github+json",
	"Authorization": f"Bearer {os.getenv("GITHUB_TOKEN")}",
}


def mine(page_limit, url):
		params = {
					"state": "closed",
					"per_page": 100,
					"page": 1
				}
		data = []
		has_more_pages = True

		print("Fetching data across pages...")

		while has_more_pages:
			print(f" Requesting page {params['page']}...")
			response = requests.get(url, headers=HEADERS, params=params)
			response.raise_for_status()

			if response.status_code != 200:
				raise PermissionError(f"Oh brother, Github's down again (or my token expired or I bricked the code). Error code is {response.status_code}")
			page_data = response.json()
			
			if not page_data or params["page"] > page_limit:
				has_more_pages = False
				break

			data.extend(page_data)
			params["page"] += 1
		params["page"] = 1
		return data


class PRData:


	# Page limit is for testing purposes only, hence why the default is unlimited. 
	def __init__(self, page_limit=2147483648):
		self.prs = self.minePRs(page_limit, URL)
		self.comments = self.mineComments(page_limit, self.prs)
		print("All comments and PRs of relevance have been obtained.")


	def minePRs(self, page_limit, url):
		initial_PRs = mine(page_limit, url)
		relevant_PRs = []
		for p in initial_PRs:
			time_created = dt.fromisoformat(p["created_at"])
			if (p["draft"] == False) and (p["merged_at"] is not None) and (time_created > EARLIEST_TIME) and (time_created < LATEST_TIME):
				relevant_PRs.append(p)
		prs = []
		for pr in relevant_PRs:
			print(f"Requesting PR:{pr["number"]}'s metadata")
			response = requests.get(url + f"/{pr["number"]}", headers=HEADERS)
			response.raise_for_status()

			if response.status_code != 200:
					raise PermissionError(f"Oh brother, Github's down again (or my token expired or I bricked the code). Error code is {response.status_code}")

			pr = response.json()
			prs.append(pr)
		return prs


	def mineComments(self, page_limit, prs):
		comments = {}
		for pr in prs:
			print(f"Getting comments for PR {pr["number"]}")
			url = pr["review_comments_url"]
			comments_for_pr = mine(page_limit, url)
			comments[pr["number"]] = comments_for_pr
		return comments


def main():
	dataObject = PRData(1)
	print(dataObject.prs[0])
	for key in dataObject.comments.keys():
		print(dataObject.comments[key])



if __name__ == "__main__":
    main()