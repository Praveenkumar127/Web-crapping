
import os
import time
import pandas as pd

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


# 1. Naukri job search URL
url = "https://www.naukri.com/data-engineer-jobs?k=data%20engineer&nignbevent_src=jobsearchDeskGNB"


# 2. CSV output location
folder_path = (
    r"C:\Users\Karpagam\OneDrive\Documents"
    r"\Web crapping\naukri"
)

file_path = os.path.join(folder_path, "naukri_jobs.csv")
os.makedirs(folder_path, exist_ok=True)


# 3. Configure Chrome
options = Options()
options.add_argument("--start-maximized")

# IMPORTANT:
# Replace this example with the ACTUAL path to
# your extracted chromedriver.exe file.
driver_path = r"C:\Users\Karpagam\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"

if not os.path.isfile(driver_path):
    raise FileNotFoundError(
        "ChromeDriver was not found at:\n"
        + driver_path
        + "\nPlease update driver_path to the actual "
          "location of chromedriver.exe."
    )

service = Service(driver_path)
driver = webdriver.Chrome(
    service=service,
    options=options
)


try:
    # 4. Open Naukri
    driver.get(url)

    # Allow the page time to load
    time.sleep(10)

    # 5. Read the rendered HTML
    soup = BeautifulSoup(
        driver.page_source,
        "html.parser"
    )

    # 6. Find job cards
    job_cards = soup.select(
        "div.srp-jobtuple-wrapper, "
        "div.cust-job-tuple, "
        "article.jobTuple"
    )

    print("Job cards found:", len(job_cards))

    jobs = []

    # 7. Extract job details
    for card in job_cards:

        title_tag = card.select_one(
            "a.title, a[class*='title']"
        )

        company_tag = card.select_one(
            "a.comp-name, "
            "a[class*='comp-name'], "
            "span[class*='comp-name']"
        )

        location_tag = card.select_one(
            "span.locWd, "
            "span[class*='locWd'], "
            "li[class*='location']"
        )

        experience_tag = card.select_one(
            "span.expwdth, "
            "span[class*='expwdth'], "
            "li[class*='experience']"
        )

        job_title = (
            title_tag.get_text(" ", strip=True)
            if title_tag else None
        )

        company_name = (
            company_tag.get_text(" ", strip=True)
            if company_tag else None
        )

        location = (
            location_tag.get_text(" ", strip=True)
            if location_tag else None
        )

        experience = (
            experience_tag.get_text(" ", strip=True)
            if experience_tag else None
        )

        if job_title:
            jobs.append({
                "Job Name": job_title,
                "Company Name": company_name,
                "Location": location,
                "Experience": experience
            })

    # 8. Create DataFrame
    columns = [
        "Job Name",
        "Company Name",
        "Location",
        "Experience"
    ]

    df = pd.DataFrame(jobs, columns=columns)

    # 9. Save as CSV
    df.to_csv(
        file_path,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nScraping completed.")
    print(df.head(10).to_string(index=False))
    print("\nTotal jobs extracted:", len(df))
    print("CSV file saved at:", file_path)

    if len(jobs) == 0:
        print(
            "\nNo job cards were detected. "
            "Naukri's HTML selectors may have changed, "
            "or the page may require verification."
        )

finally:
    driver.quit()
