from mine import EARLIEST_TIME, LATEST_TIME, URL, mine, request
from datetime import datetime as dt
from make_csv import makeCSV
import json
import os

# Each PR and its extra information is saved here as <PR number>.json as soon as it's mined.
RAW_DATA_DIR = "raw_data"


def extraInfoURLs(pr):
	return {
		"issue_comments": pr["comments_url"],         # Main conversation thread
		"review_comments": pr["review_comments_url"], # Inline comments on lines of code
		"reviews": f"{pr["url"]}/reviews",            # Review bodies and their approve/request changes states
		"commits": pr["commits_url"],                 # GitHub caps this at 250 commits per PR
	}


class PRData:


	# Page limit is for testing purposes only, hence why the default is unlimited.
	# PRs already in output_dir are skipped, so a crashed or stopped run picks up where it left off.
	def __init__(self, page_limit=2147483648, output_dir=RAW_DATA_DIR):
		self.output_dir = output_dir
		os.makedirs(output_dir, exist_ok=True)
		params = {
							"state": "closed",
							"sort": "created",
							"direction": "desc",
							"per_page": 100,
						}
		relevant_PRs = self.findRelevantPRs(page_limit, URL, params)
		remaining_PRs = [p for p in relevant_PRs if not os.path.exists(self.recordPath(p["number"]))]
		print(f"{len(relevant_PRs)} relevant PRs found, {len(relevant_PRs) - len(remaining_PRs)} already mined.")

		for i, pr in enumerate(remaining_PRs, 1):
			print(f"[{i}/{len(remaining_PRs)}] Mining PR {pr["number"]}")
			record = self.minePR(page_limit, pr["number"])
			if record is not None:
				self.saveRecord(record)
		print("All comments, commits, and PRs of relevance have been obtained.")


	def findRelevantPRs(self, page_limit, url, params):
		# PRs come newest first, so once a page reaches past EARLIEST_TIME every page after it will too.
		def isPastEarliestTime(page_data):
			return dt.fromisoformat(page_data[-1]["created_at"]) < EARLIEST_TIME

		initial_PRs = mine(page_limit, url, params, stop_when=isPastEarliestTime)
		relevant_PRs = []
		for p in initial_PRs:
			time_created = dt.fromisoformat(p["created_at"])
			if (p["draft"] == False) and (time_created > EARLIEST_TIME) and (time_created < LATEST_TIME):
				relevant_PRs.append(p)
		return relevant_PRs


	# The list endpoint leaves out fields like additions/deletions, so the full PR is requested on its own.
	def minePR(self, page_limit, number):
		print(f"Requesting PR:{number}'s metadata")
		pr = request(f"{URL}/{number}")
		if pr is None:
			return None

		record = {"pr": pr}
		for name, url in extraInfoURLs(pr).items():
			print(f"Getting {name} for PR {number}")
			record[name] = mine(page_limit, url, {"per_page": 100})
		return record


	def recordPath(self, number):
		return os.path.join(self.output_dir, f"{number}.json")


	def saveRecord(self, record):
		path = self.recordPath(record["pr"]["number"])
		temp_path = path + ".tmp"
		with open(temp_path, "w", encoding="utf-8") as f:
			json.dump(record, f)
		# Replacing is atomic, so a run killed mid-write never leaves a half written file behind.
		os.replace(temp_path, path)


def main():
	print("In Main")
	PRData()
	makeCSV(RAW_DATA_DIR)
	print("Exiting Main")



if __name__ == "__main__":
    main()
