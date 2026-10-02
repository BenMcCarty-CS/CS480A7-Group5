from mine import HEADERS, EARLIEST_TIME, LATEST_TIME, URL, mine, rateLimitChecker
from datetime import datetime as dt
import requests
from make_csv import makeCSV
import time



class PRData:


	# Page limit is for testing purposes only, hence why the default is unlimited. 
	def __init__(self, page_limit=2147483648):
		params = {
							"state": "closed",
							"per_page": 100,
							"page": 1
						}
		self.prs = self.minePRs(page_limit, URL, params)
		# Comments is a Dictionary, mapping PR number to a list of their associated comments json responses.
		print("Getting comments...")
		self.comments = self.mineExtraPRInformation(page_limit, self.prs, params, "review_comments_url")
		# Commits is a Dictionary, mapping PR number to a list of their associated comments json responses.
		print("Getting commits...")
		self.commits = self.mineExtraPRInformation(page_limit, self.prs, params, "commits_url")
		print("All comments, commits, and PRs of relevance have been obtained.")


	def minePRs(self, page_limit, url, params):
		initial_PRs = mine(page_limit, url, params)
		relevant_PRs = []
		for p in initial_PRs:
			time_created = dt.fromisoformat(p["created_at"])
			if (p["draft"] == False) and (time_created > EARLIEST_TIME) and (time_created < LATEST_TIME):
				relevant_PRs.append(p)
		prs = []
		for pr in relevant_PRs:
			print(f"Requesting PR:{pr["number"]}'s metadata")
			try:
				response = requests.get(url + f"/{pr["number"]}", headers=HEADERS)
				rateLimitChecker(response)
				pr = response.json()
				prs.append(pr)
			except requests.exceptions.ReadTimeout:
				print("Request timed out... retrying after a brief sleep.")
				time.sleep(5)
			except requests.exceptions.ConnectTimeout:
				print("Unable to connect to server! Likely an internet issue... going to sleep for a minute while it hopefully gets resolved.")
				time.sleep(60)
		return prs


	def mineExtraPRInformation(self, page_limit, prs, params, keyForURLOfInterest):
		extraPRInfo = {}
		for pr in prs:
			print(f"Getting extra PR information for PR {pr["number"]}")
			url = pr[keyForURLOfInterest]
			extraPRInfo_for_pr = mine(page_limit, url, params)
			extraPRInfo[pr["number"]] = extraPRInfo_for_pr
		return extraPRInfo
			

def main():
	print("In Main")
	makeCSV(PRData())
	print("Exiting Main")



if __name__ == "__main__":
    main()