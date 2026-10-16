
import os
import logging
from urllib.parse import urljoin

import boto3
import requests
import pandas as pd
from bs4 import BeautifulSoup

# Configure CloudWatch logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Lambda temporary storage
OUTPUT_DIR = "/tmp/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# AWS clients
ssm = boto3.client("ssm")
s3_client = boto3.client("s3")
sns_client = boto3.client("sns")


def get_ssm_parameter(parameter_name):
    """Retrieve a value from SSM Parameter Store."""
    response = ssm.get_parameter(
        Name=parameter_name
    )
    return response["Parameter"]["Value"]


def send_notification(topic_arn, subject, message):
    """Send an email using SNS."""
    sns_client.publish(
        TopicArn=topic_arn,
        Subject=subject,
        Message=message
    )
    logger.info("SNS notification sent: %s", subject)


def scrape_python_jobs(url):
    logger.info("Starting Python job scraper")

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )
    response.raise_for_status()

    logger.info("HTTP status: %s", response.status_code)

    soup = BeautifulSoup(response.text, "html.parser")
    job_cards = soup.select("ol.list-recent-jobs > li")

    logger.info("Job cards found: %s", len(job_cards))

    jobs = []

    for card in job_cards:
        title_tag = card.select_one("h2 a")
        company_tag = card.select_one(".listing-company-name")
        location_tag = card.select_one(".listing-location")
        date_tag = card.select_one(".listing-posted")

        job_url = None

        if title_tag and title_tag.get("href"):
            job_url = urljoin(url, title_tag["href"])

        jobs.append({
            "Job Title": (
                title_tag.get_text(" ", strip=True)
                if title_tag else None
            ),
            "Job URL": job_url,
            "Company": (
                company_tag.get_text(" ", strip=True)
                if company_tag else None
            ),
            "Location": (
                location_tag.get_text(" ", strip=True)
                if location_tag else None
            ),
            "Posted Date": (
                date_tag.get_text(" ", strip=True)
                if date_tag else None
            )
        })

    if not jobs:
        raise RuntimeError(
            "No jobs found. Check the website structure."
        )

    logger.info("Total jobs extracted: %s", len(jobs))
    return jobs


def lambda_handler(event, context):
    failure_arn = None

    try:
        # Read SNS failure ARN first so it may be used
        # if another SSM parameter or processing step fails.
        failure_arn = get_ssm_parameter(
            "/data/errorarn/webcrap"
        )

        # Read configuration from SSM
        url = get_ssm_parameter(
            "/data/url/webcrap"
        )

        s3_bucket = get_ssm_parameter(
            "/job-scraper/s3_bucket"
        )

        success_arn = get_ssm_parameter(
            "/data/successarn/webcrap"
        )

        logger.info("SSM parameters loaded successfully")

        # Scrape jobs
        jobs = scrape_python_jobs(url)

        # Create Excel file
        file_path = os.path.join(
            OUTPUT_DIR,
            "jobs.xlsx"
        )

        columns = [
            "Job Title",
            "Job URL",
            "Company",
            "Location",
            "Posted Date"
        ]

        df = pd.DataFrame(jobs, columns=columns)
        df.to_excel(file_path, index=False)

        logger.info("Excel file created successfully")

        # Upload to S3
        s3_key = "python_jobs/jobs.xlsx"

        s3_client.upload_file(
            file_path,
            s3_bucket,
            s3_key
        )

        logger.info("Excel file uploaded to S3 successfully")

        # Send success email
        send_notification(
            success_arn,
            "Python Job Scraper - SUCCESS",
            (
                "Job scraping completed successfully.\n"
                f"Total jobs found: {len(jobs)}\n"
                "Excel file uploaded to the configured S3 location."
            )
        )

        return {
            "statusCode": 200,
            "body": "Scraping and S3 upload completed successfully.",
            "job_count": len(jobs)
        }

    except Exception as error:
        logger.exception("Python job scraper failed")

        # Send failure email when the failure ARN is available
        if failure_arn:
            try:
                send_notification(
                    failure_arn,
                    "Python Job Scraper - FAILURE",
                    (
                        "Job scraping failed.\n"
                        f"Error type: {type(error).__name__}\n"
                        f"Error: {str(error)[:1000]}\n"
                        f"Request ID: {context.aws_request_id}"
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to send SNS failure notification"
                )

        # Mark the invocation as failed in Lambda
        raise
