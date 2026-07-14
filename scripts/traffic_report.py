#!/usr/bin/env python3
"""Weekly MDSynapse.org traffic report: queries GA4, emails a summary.

All secrets come from environment variables:
  GA_SERVICE_ACCOUNT_JSON  - full contents of the GCP service account key (JSON string)
  GMAIL_APP_PASSWORD       - Gmail app password for GMAIL_ADDRESS

Non-secret config also comes from env vars (set in the GitHub Actions workflow):
  GA_PROPERTY_ID, GMAIL_ADDRESS, RECIPIENT_EMAIL
"""
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import google.auth.transport.requests
import requests
from google.oauth2 import service_account

PROPERTY_ID = os.environ["GA_PROPERTY_ID"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
SITE_NAME = "MDSynapse.org"

CONTINENT_NAMES = {
    "Africa": "Africa",
    "Americas": "Americas",
    "Asia": "Asia",
    "Europe": "Europe",
    "Oceania": "Oceania",
    "(not set)": "Unknown",
}


def get_credentials():
    info = json.loads(os.environ["GA_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds


def run_reports(token):
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{PROPERTY_ID}:batchRunReports"
    body = {
        "requests": [
            # 0: 7-day totals
            {
                "dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}],
                "metrics": [{"name": "sessions"}, {"name": "screenPageViews"}],
            },
            # 1: 365-day totals
            {
                "dateRanges": [{"startDate": "365daysAgo", "endDate": "yesterday"}],
                "metrics": [{"name": "sessions"}, {"name": "screenPageViews"}],
            },
            # 2: 7-day by continent
            {
                "dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}],
                "dimensions": [{"name": "continent"}],
                "metrics": [{"name": "sessions"}],
                "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            },
            # 3: 365-day by continent
            {
                "dateRanges": [{"startDate": "365daysAgo", "endDate": "yesterday"}],
                "dimensions": [{"name": "continent"}],
                "metrics": [{"name": "sessions"}],
                "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            },
        ]
    }
    resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["reports"]


def totals_from_report(report):
    rows = report.get("rows", [])
    if not rows:
        return 0, 0
    values = rows[0]["metricValues"]
    return int(values[0]["value"]), int(values[1]["value"])


def continents_from_report(report):
    rows = report.get("rows", [])
    out = []
    for row in rows:
        continent = row["dimensionValues"][0]["value"] or "(not set)"
        sessions = int(row["metricValues"][0]["value"])
        out.append((CONTINENT_NAMES.get(continent, continent), sessions))
    return out


def format_continent_lines(continents):
    if not continents:
        return "<p style=\"color:#64748B;\">No session data yet.</p>"
    total = sum(s for _, s in continents)
    rows_html = ""
    for name, sessions in continents:
        pct = (sessions / total * 100) if total else 0
        rows_html += (
            f'<tr><td style="padding:4px 12px 4px 0;">{name}</td>'
            f'<td style="padding:4px 12px;text-align:right;">{sessions:,}</td>'
            f'<td style="padding:4px 0;text-align:right;color:#64748B;">{pct:.0f}%</td></tr>'
        )
    return f'<table style="border-collapse:collapse;font-size:14px;">{rows_html}</table>'


def build_email_html(week_sessions, week_views, year_sessions, year_views, week_continents, year_continents):
    return f"""\
<html><body style="font-family:-apple-system,Arial,sans-serif;color:#1E1B4B;max-width:560px;margin:0 auto;">
<h2 style="margin-bottom:0;">{SITE_NAME} — Weekly Traffic Report</h2>
<p style="color:#64748B;margin-top:4px;">Past 7 days and past 365 days, as of this Monday.</p>

<h3 style="border-bottom:2px solid #06B6D4;padding-bottom:4px;">Past 7 Days</h3>
<p><strong>{week_sessions:,}</strong> sessions &nbsp;|&nbsp; <strong>{week_views:,}</strong> pages viewed</p>
<p style="margin-bottom:4px;color:#64748B;">By continent:</p>
{format_continent_lines(week_continents)}

<h3 style="border-bottom:2px solid #8B5CF6;padding-bottom:4px;margin-top:24px;">Past 365 Days</h3>
<p><strong>{year_sessions:,}</strong> sessions &nbsp;|&nbsp; <strong>{year_views:,}</strong> pages viewed</p>
<p style="margin-bottom:4px;color:#64748B;">By continent:</p>
{format_continent_lines(year_continents)}

<p style="margin-top:32px;font-size:12px;color:#94A3B8;">Sent automatically every Monday by the mdsynapse.org GitHub Actions workflow.</p>
</body></html>
"""


def build_email_text(week_sessions, week_views, year_sessions, year_views, week_continents, year_continents):
    def cont_lines(continents):
        if not continents:
            return "  (no session data yet)"
        return "\n".join(f"  {name}: {sessions:,}" for name, sessions in continents)

    return f"""{SITE_NAME} — Weekly Traffic Report

PAST 7 DAYS
  Sessions: {week_sessions:,}
  Pages viewed: {week_views:,}
  By continent:
{cont_lines(week_continents)}

PAST 365 DAYS
  Sessions: {year_sessions:,}
  Pages viewed: {year_views:,}
  By continent:
{cont_lines(year_continents)}
"""


def send_email(subject, html_body, text_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [RECIPIENT_EMAIL], msg.as_string())


def main():
    creds = get_credentials()
    reports = run_reports(creds.token)

    week_sessions, week_views = totals_from_report(reports[0])
    year_sessions, year_views = totals_from_report(reports[1])
    week_continents = continents_from_report(reports[2])
    year_continents = continents_from_report(reports[3])

    html = build_email_html(week_sessions, week_views, year_sessions, year_views, week_continents, year_continents)
    text = build_email_text(week_sessions, week_views, year_sessions, year_views, week_continents, year_continents)

    send_email(f"{SITE_NAME} Traffic Report — {week_sessions:,} sessions this week", html, text)
    print(f"Sent report: week={week_sessions} sessions/{week_views} views, "
          f"year={year_sessions} sessions/{year_views} views")


if __name__ == "__main__":
    main()
