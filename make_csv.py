from datetime import datetime as dt
import csv

def parseISODatetime(dateString):
	if not dateString:
		return None
	return dt.fromisoformat(dateString.replace("Z", "+00:00"))

def makeCSV(data):
	prs = data.prs

	processedRows = []

	for pr in prs:
		prNum = pr["number"]
		additions = pr["additions"]
		deletions = pr["deletions"]
		linesChanged = additions + deletions
		createdAt = parseISODatetime(pr["created_at"])
		completedAt = parseISODatetime(pr["merged_at"] or pr["closed_at"])

		duration = None
		if createdAt and completedAt:
			duration = completedAt - createdAt
		processedRows.append({
			"prNumber": prNum,
			"open/closed": pr["state"],
			"isMerged": pr.get("merged", False),
			"additions": additions,
			"deletions": deletions,
			"linesChanged": linesChanged,
			"createdAt": pr["created_at"],
			"completedAt": pr["merged_at"] or pr["closed_at"],
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