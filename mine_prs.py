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

HEADERS = {
	"Accept": "appliction/vnd.github+json",
	"Authorization": f"Bearer {os.getenv("GITHUB_TOKEN")}",
}
params = {
	"per_page": 100,
	"page": 1
}

def mine(page_limit, url):
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

	# Creates a 5 year window, as we're required to do a minimum of 5 years of mining...
		# so that minimum is what we shall meet. The default values are the intended time frame,
		# but they should be reduced to much smaller when testing for efficiency.  
	def __init__(self, page_limit=2147483648):
		self.prs = self.minePRs(page_limit, URL)
		self.comments = self.mineComments(page_limit, self.prs)


	def minePRs(self, page_limit, url):
		initial_PRs = mine(page_limit, url)
		relevant_PRs = [p for p in initial_PRs if p["draft"] == False]
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