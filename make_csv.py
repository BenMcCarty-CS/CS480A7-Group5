from datetime import datetime as dt
import csv
import json


def parseISODatetime(dateString):
    if not dateString:
        return None
    return dt.fromisoformat(dateString.replace("Z", "+00:00"))



def makeCSV(data):

    prs = data.prs

    fields = list(prs[0].keys())

    processesdRows = []

    for pr in prs:
        row = {}
        for key in fields:
            value = pr.get(key)

            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value)
            elif value is None:
                row[key] = ""
            else:
                row[key] = value
        processesdRows.append(row)

    outputFileName = "RawData.csv"
    with open(outputFileName, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(processesdRows)