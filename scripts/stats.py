#!/usr/bin/env python3
"""Print site traffic from Cloudflare Web Analytics and Google Search Console.

Usage:
  python scripts/stats.py [--days 7] [--top 10]

Cloudflare: page views and visits (bots excluded) per host, per day, top paths, countries and referrers over the
last --days days. Needs CF_ANALYTICS_TOKEN (Account Analytics Read) and R2_ACCOUNT_ID.
Google: clicks, impressions, CTR and position per day, top queries and pages. Needs GSC_CLIENT_ID,
GSC_CLIENT_SECRET and GSC_REFRESH_TOKEN (create with scripts/gsc-auth.py). Search Console data lags ~3 days.
Variables are read from the process environment, then from the Windows user environment. Setup in CLAUDE.md.
"""
import argparse
import datetime
import os
import sys
import urllib.parse

import requests

CF_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
GSC_SITE = "sc-domain:sleepytelescope.com"
GSC_BASE = "https://searchconsole.googleapis.com/webmasters/v3"


def env(name):
    value = os.environ.get(name)
    if not value and sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value = winreg.QueryValueEx(key, name)[0]
        except OSError:
            value = None
    if not value:
        sys.exit(f"Missing environment variable {name}")
    return value


def table(rows, headers):
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    for r in rows:
        print("  " + "  ".join(c.ljust(w) for c, w in zip(r, widths)))
    if not rows:
        print("  (no data)")


def cloudflare(days, top):
    end = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    start = end - datetime.timedelta(days=days)
    groups = {"hosts": "requestHost", "paths": "requestPath", "countries": "countryName", "referrers": "refererHost"}
    parts = [f"{alias}: rumPageloadEventsAdaptiveGroups(limit: {top}, filter: $f, orderBy: [count_DESC]) "
             f"{{ count sum {{ visits }} dimensions {{ {dim} }} }}" for alias, dim in groups.items()]
    parts.append("days: rumPageloadEventsAdaptiveGroups(limit: 100, filter: $f, orderBy: [date_ASC]) "
                 "{ count sum { visits } dimensions { date } }")
    query = ("query($acc: String!, $f: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject!) "
             "{ viewer { accounts(filter: {accountTag: $acc}) { " + " ".join(parts) + " } } }")
    flt = {"datetime_geq": start.isoformat().replace("+00:00", "Z"),
           "datetime_lt": end.isoformat().replace("+00:00", "Z"), "bot": 0}
    r = requests.post(CF_GRAPHQL, headers={"Authorization": "Bearer " + env("CF_ANALYTICS_TOKEN")},
                      json={"query": query, "variables": {"acc": env("R2_ACCOUNT_ID"), "f": flt}}, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        sys.exit(f"Cloudflare error: {body['errors']}")
    acc = body["data"]["viewer"]["accounts"][0]

    print(f"== Cloudflare Web Analytics, {start:%d/%m/%Y %H:%M} - {end:%d/%m/%Y %H:%M} UTC, bots excluded ==")
    views = sum(g["count"] for g in acc["hosts"])
    visits = sum(g["sum"]["visits"] for g in acc["hosts"])
    print(f"Total: {views} page views, {visits} visits (visit = page view arriving from another site)\n")
    for alias, dim in groups.items():
        print(alias.capitalize() + ":")
        table([[g["dimensions"][dim] or "(none)", g["count"], g["sum"]["visits"]] for g in acc[alias]],
              [dim, "views", "visits"])
        print()
    print("By day (UTC):")
    table([[datetime.date.fromisoformat(g["dimensions"]["date"]).strftime("%d/%m/%Y"), g["count"],
            g["sum"]["visits"]] for g in acc["days"]], ["date", "views", "visits"])
    print()


def google(days, top):
    tok = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env("GSC_CLIENT_ID"), "client_secret": env("GSC_CLIENT_SECRET"),
        "refresh_token": env("GSC_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30).json()
    if "access_token" not in tok:
        sys.exit(f"Google token refresh failed: {tok.get('error')} {tok.get('error_description')} "
                 "(run scripts/gsc-auth.py again)")
    headers = {"Authorization": "Bearer " + tok["access_token"]}
    url = f"{GSC_BASE}/sites/{urllib.parse.quote(GSC_SITE, safe='')}/searchAnalytics/query"
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)

    def query(dims, limit):
        r = requests.post(url, headers=headers, json={"startDate": str(start), "endDate": str(end),
                                                      "dimensions": dims, "rowLimit": limit}, timeout=30)
        r.raise_for_status()
        return r.json().get("rows", [])

    def fmt(row, keys):
        return keys + [row["clicks"], row["impressions"], f"{row['ctr'] * 100:.1f} %", f"{row['position']:.1f}"]

    print(f"== Google Search Console {GSC_SITE}, {start:%d/%m/%Y} - {end:%d/%m/%Y} (data lags ~3 days) ==")
    total = query([], 1)
    if total:
        t = total[0]
        print(f"Total: {t['clicks']} clicks, {t['impressions']} impressions, CTR {t['ctr'] * 100:.1f} %, "
              f"avg position {t['position']:.1f}\n")
    cols = ["clicks", "impr.", "CTR", "pos."]
    print("By day:")
    table([fmt(r, [datetime.date.fromisoformat(r["keys"][0]).strftime("%d/%m/%Y")]) for r in query(["date"], 100)],
          ["date"] + cols)
    for dim, label in (("query", "queries"), ("page", "pages")):
        rows = sorted(query([dim], 1000), key=lambda r: (-r["clicks"], -r["impressions"]))[:top]
        print(f"\nTop {label}:")
        table([fmt(r, [r["keys"][0]]) for r in rows], [dim] + cols)
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    cloudflare(args.days, args.top)
    google(args.days, args.top)


if __name__ == "__main__":
    main()
