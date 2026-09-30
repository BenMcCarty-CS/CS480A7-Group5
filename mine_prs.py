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
	"Accept": "application/vnd.github+json",
	"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
}

def mine(params, url):
		print(params)
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
			
			if not page_data:
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
	def __init__(self, since_date = "2021-07-04T23:59:59Z", until_date = "2026-12-31T23:59:59Z"):
		print(until_date)
		params = {
					"per_page": 100,
					"state": "all",
					"since": since_date,
					"until": until_date,
					"page": 1
				}
		self.prs = self.minePRs(params, URL)
		self.comments = self.mineComments(params, self.prs)


	def minePRs(self, params, url):
		initial_PRs = mine(params, url)
		relevant_PRs = [p for p in initial_PRs if p["draft"] == False]
		prs = []
		for pr in relevant_PRs:
			print("mining PRs")
			print(f"Requesting PR:{pr['number']}'s metadata")
			response = requests.get(url + f"/{pr['number']}", headers=HEADERS)
			response.raise_for_status()

			if response.status_code != 200:
					raise PermissionError(f"Oh brother, Github's down again (or my token expired or I bricked the code). Error code is {response.status_code}")

			pr = response.json()
			prs.append(pr)
		return prs


	def mineComments(self, params, prs):
		comments = {}
		for pr in prs:
			print("mining commits")
			print(f"Getting comments for PR {pr['number']}")
			url = pr["review_comments_url"]
			comments_for_pr = mine(params, url)
			comments[pr["number"]] = comments_for_pr
		return comments

def parseISODatetime(dateString):
	if not dateString:
		return None
	return dt.fromisoformat(dateString.replace("Z", "+00:00"))

def makeCSV():
	data = PRData()

	since= parseISODatetime("2021-07-04T23:59:59Z")
	until = parseISODatetime("2026-12-31T23:59:59Z")
	prs = data.prs

	processedRows = []

	for pr in prs:
		createdAt = parseISODatetime(pr.get("created_at"))

		if createdAt and (since <= createdAt <= until):
			prNum = pr.get("number")
			additions = pr.get("additions", 0)
			deletions = pr.get("deletions", 0)
			linesChanged = additions + deletions
			createdAt = parseISODatetime(pr.get("created_at"))
			completedAt = parseISODatetime(pr.get("merged_at") or pr.get("closed_at"))

			duration = None
			if createdAt and completedAt:
				duration = completedAt - createdAt
			processedRows.append({
				"prNumber": prNum,
				"open/closed": pr.get("state"),
				"isMerged": pr.get("merged", False),
				"additions": additions,
				"deletions": deletions,
				"linesChanged": linesChanged,
				"createdAt": pr.get("created_at"),
				"completedAt": pr.get("merged_at") or pr.get("closed_at"),
				"completionTime": duration if duration is not None else "NA"
			})

	fields = [
		"prNumber",
		"open/closed",
		"isMerged",
		"additions",
		"deletions",
		"linesChanged",
		"createdAt",
		"completedAt",
		"completionTime"
	]

	outputFileName = "MinedPRsData.csv"
	with open(outputFileName, "w", newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=fields)
		writer.writeheader()
		writer.writerows(processedRows)
			

def main():
	print("In Main")
	makeCSV()
	print("Exiting Main")
	#print(os.getenv("GITHUB_TOKEN"))
	#dataObject = PRData("2021-07-05T23:59:59Z", "2021-07-05T23:59:59Z")
	#print(dataObject.prs)
	#print(dataObject.comments)



if __name__ == "__main__":
    main()