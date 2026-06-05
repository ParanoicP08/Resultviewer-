import json, re, os, sys

HTML_FILE = "index.html"
STUDENTS_JSON = "data/students.json"

def main():
    if not os.path.exists(STUDENTS_JSON):
        print("No students.json found — skipping inject.")
        sys.exit(0)  # exit 0 = success, not failure

    if not os.path.exists(HTML_FILE):
        print(f"index.html not found. Files here: {os.listdir('.')}")
        sys.exit(0)  # exit 0 so workflow doesn't fail

    with open(STUDENTS_JSON, encoding="utf-8") as f:
        students_raw = f.read().strip()

    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()

    pattern = r"const STUDENTS = \{.*?\};"
    replacement = f"const STUDENTS = {students_raw};"
    new_html, count = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)

    if count == 0:
        print("Could not find STUDENTS block — skipping.")
        sys.exit(0)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"Injected {len(json.loads(students_raw))} students.")

if __name__ == "__main__":
    main()
