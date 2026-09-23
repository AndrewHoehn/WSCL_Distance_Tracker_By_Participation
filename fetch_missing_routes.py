#!/usr/bin/env python3
"""
Fetch missing route polylines from Google Directions API for races that
were added after the original heatmap run. Adds them to route_cache.json.

Targets races with 0 cached routes; currently:
  - 2025-10-12 Loup Loup (Okanogan)
  - 2026-04-12 Riverside State Park (Spokane)
"""

import json
import os
import sys
import time

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "wscl_distance_data.json")
CACHE_FILE = os.path.join(SCRIPT_DIR, "route_cache.json")

def _find_api_key():
    k = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if k:
        return k
    # Fall back to the key used by generate_heatmaps.py on this machine (in .gitignore).
    heatmaps_path = os.path.join(SCRIPT_DIR, "generate_heatmaps.py")
    if os.path.exists(heatmaps_path):
        import re
        with open(heatmaps_path) as f:
            m = re.search(r"GOOGLE_MAPS_API_KEY['\"]?\s*:\s*['\"]([A-Za-z0-9_\-]+)['\"]", f.read())
            if m:
                return m.group(1)
    return ""


API_KEY = _find_api_key()
RATE_LIMIT = 0.1

TARGET_DATES = ["2025-10-12", "2026-04-12"]


def decode_polyline(s):
    coords, i, lat, lng = [], 0, 0, 0
    while i < len(s):
        res, shift = 0, 0
        while True:
            b = ord(s[i]) - 63; i += 1
            res |= (b & 0x1f) << shift; shift += 5
            if b < 0x20: break
        dlat = ~(res >> 1) if (res & 1) else (res >> 1)
        lat += dlat
        res, shift = 0, 0
        while True:
            b = ord(s[i]) - 63; i += 1
            res |= (b & 0x1f) << shift; shift += 5
            if b < 0x20: break
        dlng = ~(res >> 1) if (res & 1) else (res >> 1)
        lng += dlng
        coords.append([lat / 1e5, lng / 1e5])
    return coords


def fetch_route(olat, olng, dlat, dlng):
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/directions/json",
        params={
            "origin": f"{olat},{olng}",
            "destination": f"{dlat},{dlng}",
            "mode": "driving",
            "key": API_KEY,
        },
        timeout=20,
    )
    data = resp.json()
    if data.get("status") != "OK":
        print(f"    ERROR: {data.get('status')}: {data.get('error_message','')}")
        return None
    return decode_polyline(data["routes"][0]["overview_polyline"]["points"])


ROUTES_FILE = os.path.join(SCRIPT_DIR, "race_routes.json")
ROUTES_JS = os.path.join(SCRIPT_DIR, "race_routes.js")


def load_races():
    with open(ROUTES_FILE) as f:
        return json.load(f)["races"]


def save_races(races):
    """Write race_routes.json and the .js copy the dashboard loads."""
    body = json.dumps({"races": races}, separators=(",", ":"))
    with open(ROUTES_FILE, "w") as f:
        f.write(body)
    with open(ROUTES_JS, "w") as f:
        f.write(f"window.__WSCL_ROUTES__ = {body};\n")


def cached_points(cache, races, event, team, date, previous=None):
    """Route points for team -> event without an API call: the race's own
    previous entry (when rebuilding), route_cache, then the team's line from
    the latest earlier race at the same venue."""
    for trip in (previous or {}).get("trips", []):
        if trip["t"] == team:
            return trip["p"]
    pts = cache.get(f"{team}_{date}")
    if not isinstance(pts, list):
        pts = cache.get("routes", {}).get(f"{team}_{date}")
    if isinstance(pts, list):
        return pts
    for race in sorted(races, key=lambda r: r["date"], reverse=True):
        if race["date"] >= date:
            continue
        vl = race["vl"]
        if abs(vl[0] - event["lat"]) > 1e-3 or abs(vl[1] - event["lng"]) > 1e-3:
            continue
        for trip in race["trips"]:
            if trip["t"] == team:
                return trip["p"]
    return None


def build_race_entry(data, date, races, cache, previous=None):
    """race_routes.json entry for one race. Fetches only the routes that
    cached_points can't supply, and stores those in the cache.
    Returns (entry, api_calls)."""
    event = data["event_locations"][date]
    calls = 0
    trips = []
    for r in (r for r in data["travel_data"] if r["event_date"] == date):
        team = r["team"]
        home = data["team_locations"][team]
        pts = cached_points(cache, races, event, team, date, previous)
        if pts is None:
            print(f"  Fetching {team} -> {event['city']}...", end=" ", flush=True)
            pts = fetch_route(home["lat"], home["lng"], event["lat"], event["lng"])
            calls += 1
            time.sleep(RATE_LIMIT)
            if not pts:
                raise RuntimeError(f"Route fetch failed for {team} -> {date}")
            cache[f"{team}_{date}"] = pts
            print(f"{len(pts)} points")
        trips.append({
            "t": team,
            "h": [round(home["lat"], 5), round(home["lng"], 5)],
            "m": round(r["one_way_minutes"]),
            "d": round(r["one_way_miles"], 1),
            "r": r["riders"],
            "p": [[round(a, 5), round(b, 5)] for a, b in pts],
        })
    entry = {
        "date": date,
        "venue": event["venue"],
        "city": event["city"],
        "vl": [event["lat"], event["lng"]],
        "trips": trips,
    }
    return entry, calls


def main():
    if not API_KEY:
        print("ERROR: GOOGLE_MAPS_API_KEY env var is empty. "
              "Set it before running (export GOOGLE_MAPS_API_KEY=...).")
        sys.exit(1)

    with open(DATA_FILE) as f:
        data = json.load(f)
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
    else:
        cache = {}

    print(f"Route cache entries: {len(cache)}")
    api_calls = 0
    new_routes = 0

    for date in TARGET_DATES:
        event = data["event_locations"].get(date)
        if not event:
            print(f"SKIP {date}: no event location"); continue
        print(f"\n=== {date} {event['venue']} ({event['city']}) ===")
        records = [r for r in data["travel_data"] if r["event_date"] == date]
        print(f"  {len(records)} teams attended")
        for r in records:
            team = r["team"]
            key = f"{team}_{date}"
            if key in cache and isinstance(cache[key], list):
                continue
            team_loc = data["team_locations"].get(team)
            if not team_loc:
                print(f"  SKIP {team}: no team location"); continue
            print(f"  Fetching {team} -> {event['city']}...", end=" ", flush=True)
            pts = fetch_route(team_loc["lat"], team_loc["lng"], event["lat"], event["lng"])
            api_calls += 1
            time.sleep(RATE_LIMIT)
            if pts:
                cache[key] = pts
                new_routes += 1
                print(f"{len(pts)} points")
            else:
                print("FAILED")

    print(f"\nSaving cache ({len(cache)} entries)...")
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"API calls: {api_calls}, new routes added: {new_routes}")


if __name__ == "__main__":
    main()
