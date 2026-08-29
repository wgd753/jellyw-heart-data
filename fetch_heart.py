#!/usr/bin/env python3
"""Fetch latest heart rate from Google Health API v4 and write heart.json.

Runs in GitHub Actions. Credentials come from environment variables
(GitHub Actions secrets: GH_CLIENT_ID / GH_CLIENT_SECRET / GH_REFRESH_TOKEN).
Timezone is set via TZ=Asia/Shanghai in the workflow (Python localtime follows it).
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from urllib.parse import quote

API_BASE = "https://health.googleapis.com/v4"


def get_access_token(creds):
    data = {
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token",
    }
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.loads(resp.read().decode())
    return token["access_token"]


def gh_get(path, access_token):
    req = urllib.request.Request(
        f"{API_BASE}/{path}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def build_filter(d):
    # Google Health API v4: sample filter prefix uses snake_case (heart_rate), NOT kebab-case
    fp = "heart_rate"
    tomorrow = (d + timedelta(days=1)).strftime("%Y-%m-%d")
    return (
        f'{fp}.sample_time.civil_time >= "{d.strftime("%Y-%m-%d")}" '
        f'AND {fp}.sample_time.civil_time < "{tomorrow}"'
    )


def main():
    creds = {
        "client_id": os.environ["GH_CLIENT_ID"],
        "client_secret": os.environ["GH_CLIENT_SECRET"],
        "refresh_token": os.environ["GH_REFRESH_TOKEN"],
    }
    token = get_access_token(creds)

    today = datetime.now()
    filt = build_filter(today)
    path = f"users/me/dataTypes/heart-rate/dataPoints?filter={quote(filt)}&pageSize=1000"
    data = gh_get(path, token)

    if data and data.get("dataPoints"):
        latest = max(
            data["dataPoints"],
            key=lambda p: (
                p.get("heartRate", {})
                .get("sampleTime", {})
                .get("civilTime", {})
                .get("time", {})
                .get("hours", 0)
                * 3600
                + p.get("heartRate", {})
                .get("sampleTime", {})
                .get("civilTime", {})
                .get("time", {})
                .get("minutes", 0)
                * 60
                + p.get("heartRate", {})
                .get("sampleTime", {})
                .get("civilTime", {})
                .get("time", {})
                .get("seconds", 0)
            ),
        )
        bpm = int(latest["heartRate"]["beatsPerMinute"])
        ct = latest["heartRate"]["sampleTime"]["civilTime"]["time"]
        t = f"{ct['hours']:02d}:{ct['minutes']:02d}:{ct['seconds']:02d}"
        date_str = today.strftime("%Y-%m-%d")

        # Preserve stale flag from previous file if we had one
        old = {}
        if os.path.exists("heart.json"):
            try:
                old = json.load(open("heart.json"))
            except Exception:
                pass

        out = {
            "bpm": bpm,
            "date": date_str,
            "time": t,
            "updated_at": today.astimezone().isoformat(),
        }
        json.dump(out, open("heart.json", "w"), indent=2)
        print(f"heart.json <- {bpm} bpm ({date_str} {t})")
    else:
        print(f"❌ No heart rate data for {today.strftime('%Y-%m-%d')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
