""" inject_data.py -------------- Reads data/students.json and injects it into index.html, replacing the STUDENTS constant so the site always has fresh data. """

import json, re, os, sys

HTML_FILE    = "index.html"
STUDENTS_JSON = "data/students.json"

def main():
    if not os.path.exists(STUDENTS_JSON):
        print(f"No {STUDENTS_JSON} found — nothing to inject.")
        sys.exit(0)

    if not os.path.exists(HTML_FILE):
        print(f"{HTML_FILE} not found.")
        sys.exit(1)

    with open(STUDENTS_JSON, encoding="utf-8") as f:
        students_raw = f.read().strip()

    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()

    # Replace const STUDENTS = {...}; block
    pattern = r"const STUDENTS = \{.*?\};"
    replacement = f"const STUDENTS = {students_raw};"

    new_html, count = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)
    if count == 0:
        print("ERROR: Could not find 'const STUDENTS = {...};' in index.html")
        sys.exit(1)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)

    # Parse count for summary
    data = json.loads(students_raw)
    print(f"Injected {len(data)} students into {HTML_FILE}")

if __name__ == "__main__":
    main()
