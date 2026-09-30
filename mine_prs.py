from mine import HEADERS, EARLIEST_TIME, LATEST_TIME, URL, mine
from datetime import datetime as dt
import requests
from make_csv import makeCSV



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
		self.comments = self.mineComments(page_limit, self.prs, params)
		print("All comments and PRs of relevance have been obtained.")


	def minePRs(self, page_limit, url, params):
		initial_PRs = mine(page_limit, url, params)
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


	def mineComments(self, page_limit, prs, params):
		comments = {}
		for pr in prs:
			print(f"Getting comments for PR {pr["number"]}")
			url = pr["review_comments_url"]
			comments_for_pr = mine(page_limit, url, params)
			comments[pr["number"]] = comments_for_pr
		return comments
	
			

def main():
	print("In Main")
	makeCSV(PRData(1))
	print("Exiting Main")



if __name__ == "__main__":
    main()