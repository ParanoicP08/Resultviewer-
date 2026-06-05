""" scrape_and_parse.py ------------------- 1. Checks Mumbai University results page for new BSc CS result PDFs 2. Downloads any new ones not already processed 3. Parses them and saves to data/students.json Run locally: python scripts/scrape_and_parse.py Run in CI: automatically via GitHub Actions """

import os, re, json, hashlib, subprocess
import requests
from bs4 import BeautifulSoup

# ── CONFIG ──────────────────────────────────────────────────────────────────
MU_RESULTS_URL = "https://exam.mu.ac.in/ExamResult/ResultInfo"  # adjust if MU changes URL
PDF_DIR        = "data/pdfs"
STUDENTS_JSON  = "data/students.json"
SEEN_FILE      = "data/seen_pdfs.json"  # tracks already-processed PDFs

# Keywords to identify relevant PDFs (case-insensitive)
TARGET_KEYWORDS = ["bachelor of science", "computer science", "semester"]

SUBJECTS = [
    "Python for Data Science",
    "Scala for DS",
    "Principles of Operating Systems",
    "Theory of Computation",
    "Data Structures",
    "Computer Science Practical 3",
    "Java Programming",
    "Environmental Management & Sustainable Development",
    "Hindi Bhasha Vyavharik Prayog",
    "Introduction to National Service Scheme",
    "Field Project",
]

# ── HELPERS ──────────────────────────────────────────────────────────────────
def ensure_dirs():
    os.makedirs(PDF_DIR, exist_ok=True)
    os.makedirs("data", exist_ok=True)

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f, indent=2)

def load_students():
    if os.path.exists(STUDENTS_JSON):
        with open(STUDENTS_JSON) as f:
            return json.load(f)
    return {}

def save_students(students):
    with open(STUDENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Saved {len(students)} students to {STUDENTS_JSON}")

def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

# ── SCRAPER ──────────────────────────────────────────────────────────────────
def find_pdf_links():
    """ Scrapes the MU results page and returns list of (name, url) for relevant PDFs. Adjust the selector/URL to match the actual MU website structure. """
    print(f"Fetching {MU_RESULTS_URL} ...")
    try:
        resp = requests.get(MU_RESULTS_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch results page: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        # Only grab PDFs that mention BSc CS
        if href.endswith(".pdf") and any(kw in text for kw in TARGET_KEYWORDS):
            full_url = href if href.startswith("http") else f"https://exam.mu.ac.in{href}"
            links.append((a.get_text(strip=True), full_url))
            print(f" Found: {a.get_text(strip=True)}")
    print(f"Found {len(links)} relevant PDFs")
    return links

def download_pdf(url, filename):
    path = os.path.join(PDF_DIR, filename)
    if os.path.exists(path):
        print(f" Already downloaded: {filename}")
        return path
    print(f" Downloading {filename} ...")
    resp = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
    print(f" Saved {len(resp.content)//1024} KB")
    return path

# ── PARSER ───────────────────────────────────────────────────────────────────
def parse_pdf(pdf_path):
    """ Parses a MU result register PDF and returns a dict of {seat_no: student_data}. Uses pdftotext for speed. """
    print(f"Parsing {os.path.basename(pdf_path)} ...")
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0:
        print(f" pdftotext failed: {result.stderr[:200]}")
        return {}

    lines = result.stdout.split("\n")
    students = {}
    current_college = "Unknown College"

    i = 0
    while i < len(lines):
        line = lines[i]

        # College header
        col_match = re.match(r"\s*(MU-\d+\s*:.+)", line)
        if col_match:
            current_college = col_match.group(1).strip()
            i += 1
            continue

        # Student row
        seat_match = re.match(r"\s*(\d{9,10})\s+([A-Z][A-Z\s]+?)\s+(Regular|Ex-Student|Repeat)", line)
        if seat_match:
            seat_no = seat_match.group(1)
            name = seat_match.group(2).strip().title()

            gender = ""
            ern = ""
            gm = re.search(r"(MALE|FEMALE)", line)
            if gm:
                gender = gm.group(1)
            em = re.search(r"\(?(MU\w+)\)?", line)
            if em:
                ern = em.group(1)

            tot_line = ""
            result_str = "PASSED"
            for j in range(i + 1, min(i + 12, len(lines))):
                l = lines[j]
                if re.match(r"\s*TOT\s+\d", l):
                    tot_line = l
                if "FAILED" in l:
                    result_str = "FAILED"

            subject_results = []
            if tot_line:
                toks = tot_line.split()
                try:
                    toks.remove("TOT")
                except ValueError:
                    pass

                ti, si = 0, 0
                while ti < len(toks) and si < len(SUBJECTS):
                    t = toks[ti]
                    if re.match(r"^\d+$", t) and 0 <= int(t) <= 55:
                        try:
                            total = int(t)
                            gp_tok = toks[ti + 1]
                            gp = float(gp_tok) if re.match(r"^\d+\.?\d*$", gp_tok) else 0
                            grade = toks[ti + 2]
                            subject_results.append({
                                "subject": SUBJECTS[si],
                                "marks": total,
                                "max": 50,
                                "grade": grade,
                                "gp": round(gp, 2),
                            })
                            si += 1
                            ti += 5
                        except (IndexError, ValueError):
                            ti += 1
                    else:
                        ti += 1

            # Compute SGPA from subjects
            if subject_results:
                total_marks = sum(s["marks"] for s in subject_results)
                total_gp = sum(s["gp"] for s in subject_results)
                sgpa = round(total_gp / len(subject_results), 4)
            else:
                total_marks = 0
                sgpa = 0.0

            students[seat_no] = {
                "name": name,
                "seat": seat_no,
                "ern": ern,
                "gender": gender,
                "college": current_college,
                "result": result_str,
                "totalMarks": total_marks,
                "sgpa": sgpa,
                "semesters": {"3": subject_results},
            }

        i += 1

    print(f" Parsed {len(students)} students")
    return students

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    ensure_dirs()
    seen   = load_seen()
    students = load_students()
    initial_count = len(students)

    pdf_links = find_pdf_links()

    if not pdf_links:
        print("No new PDFs found. Nothing to update.")
        # Still save existing data so inject step works
        save_students(students)
        return

    new_count = 0
    for name, url in pdf_links:
        # Use URL hash as unique ID so we don't reprocess the same file
        uid = hashlib.md5(url.encode()).hexdigest()[:12]
        if uid in seen:
            print(f" Skipping already-processed: {name}")
            continue

        safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())[:60] + f"_{uid}.pdf"
        try:
            path = download_pdf(url, safe_name)
            parsed = parse_pdf(path)
            students.update(parsed)  # merge, new data overwrites old for same seat
            seen.add(uid)
            new_count += len(parsed)
            print(f" Added/updated {len(parsed)} students from {name}")
        except Exception as e:
            print(f" Error processing {name}: {e}")

    save_students(students)
    save_seen(seen)
    print(f"\nDone. Total students: {len(students)} (+{len(students) - initial_count} new)")

if __name__ == "__main__":
    main()
