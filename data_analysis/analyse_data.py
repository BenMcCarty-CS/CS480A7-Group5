import csv
import math

def calculate_PR_difficulty(row): #This calculates review difficulty

    commits = int(row.get('num_commits', 0))
    comments = int(row.get('num_comments_total', 0))
    hours_open = float(row.get('time_spent_open_hours', 0))
    lines_changed = int(row.get('lines_changed', 0))

    prDifficulty = (.4 * math.log1p(commits)) + (.25 * math.log1p(comments)) + (.2 * math.log1p(hours_open)) + (.15 * math.log1p(lines_changed))

    return prDifficulty

def analyse_data(cleanedDataFileName: str, outputFileName: str):

    prsDict = {}
    with open(cleanedDataFileName, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) + ['PR_Difficulty']
        with open(outputFileName, mode='w', newline='', encoding='utf-8') as out_f:
            writer = csv.DictWriter(out_f, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                row['PR_Difficulty'] = calculate_PR_difficulty(row)
                writer.writerow(row)

    pass

def main():
    print("Analysing data...")   
    analyse_data("clean_data/PR_Summary_Metrics.csv", "clean_data/analyzed_data.csv")
    print("Finished analysing!")



if __name__ == "__main__":
    main()