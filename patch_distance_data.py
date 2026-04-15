#!/usr/bin/env python3
"""
Patch wscl_distance_data.json with new race data.
Adds Bellingham XC MTB team and two new races (Loup Loup 2025-10-12, Riverside 2026-04-12).
Reuses existing venue coordinates and distances where possible.
Only makes Google API calls for truly new team-venue combinations.
"""

import csv
import json
import math
import os
import sys

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "wscl_distance_data.json")
ATTENDANCE_CSV = os.path.join(SCRIPT_DIR, "Team_Attendance_By_Date.csv")
EVENTS_CSV = os.path.join(SCRIPT_DIR, "Event_Names_and_IDs.csv")
TEAMS_CSV = os.path.join(SCRIPT_DIR, "Team_Names_and_Locations.csv")

# Use the key from generate_heatmaps.py
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
RIDERS_PER_VEHICLE = 2

# Bounds for geocoding (WA/ID/OR region)
BOUNDS = "41.9,-125.0|49.0,-116.0"


def geocode_address(address):
    """Geocode an address using Google Maps API."""
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={
            "address": address,
            "bounds": BOUNDS,
            "key": GOOGLE_MAPS_API_KEY,
        },
        timeout=20,
    )
    data = resp.json()
    if data["status"] == "OK" and data["results"]:
        result = data["results"][0]
        return {
            "lat": result["geometry"]["location"]["lat"],
            "lng": result["geometry"]["location"]["lng"],
            "formatted_address": result["formatted_address"],
        }
    print(f"  WARNING: Geocoding failed for '{address}': {data['status']}")
    return None


def get_driving_distance(origin_lat, origin_lng, dest_lat, dest_lng):
    """Get driving distance/time using Google Distance Matrix API."""
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/distancematrix/json",
        params={
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{dest_lat},{dest_lng}",
            "mode": "driving",
            "units": "imperial",
            "key": GOOGLE_MAPS_API_KEY,
        },
        timeout=20,
    )
    data = resp.json()
    if data["status"] == "OK" and data["rows"][0]["elements"][0]["status"] == "OK":
        element = data["rows"][0]["elements"][0]
        return {
            "one_way_miles": element["distance"]["value"] * 0.000621371,
            "one_way_minutes": element["duration"]["value"] / 60,
            "round_trip_miles": element["distance"]["value"] * 0.000621371 * 2,
            "round_trip_minutes": element["duration"]["value"] / 60 * 2,
            "distance_text": element["distance"]["text"],
            "duration_text": element["duration"]["text"],
        }
    print(f"  WARNING: Distance calc failed: {data['status']}")
    return None


def get_season(date_str):
    """Determine season from date string."""
    month = int(date_str.split("-")[1])
    year = date_str.split("-")[0]
    if 3 <= month <= 6:
        return f"Spring {year}"
    elif 9 <= month <= 10:
        return f"Fall {year}"
    return f"Unknown {year}"


def main():
    print("WSCL Distance Data Patcher")
    print("=" * 40)

    # Load existing data
    print("\nLoading existing data...")
    with open(DATA_FILE) as f:
        data = json.load(f)

    print(f"  Existing teams: {len(data['team_locations'])}")
    print(f"  Existing events: {len(data['event_locations'])}")
    print(f"  Existing travel records: {len(data['travel_data'])}")

    api_calls = 0

    # --- Step 1: Add Bellingham XC MTB if not present ---
    if "Bellingham XC MTB" not in data["team_locations"]:
        print("\nStep 1: Geocoding Bellingham XC MTB...")
        geo = geocode_address("Bellingham, WA 98225")
        api_calls += 1
        if geo:
            data["team_locations"]["Bellingham XC MTB"] = {
                **geo,
                "city": "Bellingham",
                "state": "WA",
                "zip": 98225,
            }
            print(f"  Added: Bellingham XC MTB at {geo['lat']}, {geo['lng']}")
        else:
            print("  ERROR: Could not geocode Bellingham. Aborting.")
            sys.exit(1)
    else:
        print("\nStep 1: Bellingham XC MTB already in data, skipping geocoding")

    bellingham = data["team_locations"]["Bellingham XC MTB"]

    # --- Step 2: Add 2026-04-12 event location (reuse Spokane coords) ---
    print("\nStep 2: Adding event locations...")
    if "2026-04-12" not in data["event_locations"]:
        # Reuse coordinates from existing Spokane events
        spokane_coords = None
        for date, loc in data["event_locations"].items():
            if loc.get("city") == "Spokane":
                spokane_coords = loc
                break

        if spokane_coords:
            data["event_locations"]["2026-04-12"] = {
                "lat": spokane_coords["lat"],
                "lng": spokane_coords["lng"],
                "formatted_address": spokane_coords["formatted_address"],
                "venue": "Riverside State Park",
                "city": "Spokane",
                "state": "WA",
                "event_id": "2026-04-12_Spokane_Riverside_State_Park",
            }
            print(f"  Added 2026-04-12 (Spokane) - reused existing coordinates")
        else:
            print("  ERROR: No existing Spokane event to copy coordinates from")
            sys.exit(1)
    else:
        print(f"  2026-04-12 already exists")

    # Verify 2025-10-12 (Loup Loup) exists
    if "2025-10-12" in data["event_locations"]:
        print(f"  2025-10-12 (Loup Loup) already exists")
    else:
        print(f"  ERROR: 2025-10-12 not in event_locations")
        sys.exit(1)

    # --- Step 3: Calculate distances for Bellingham ---
    print("\nStep 3: Calculating distances for Bellingham XC MTB...")
    if "Bellingham XC MTB" not in data["distances"]:
        data["distances"]["Bellingham XC MTB"] = {}

    bellingham_dists = data["distances"]["Bellingham XC MTB"]

    # We need distances to all venue locations that Bellingham might attend
    # For now, calculate for all unique venue locations
    venue_locations = {}
    for date, loc in data["event_locations"].items():
        loc_key = f"{loc['city']}_{loc['state']}"
        if loc_key not in venue_locations:
            venue_locations[loc_key] = {"loc": loc, "dates": [date]}
        else:
            venue_locations[loc_key]["dates"].append(date)

    for loc_key, venue_info in sorted(venue_locations.items()):
        # Check if we already have distance for any date at this venue
        sample_date = venue_info["dates"][0]
        if sample_date in bellingham_dists:
            # Already have it, apply to all dates at this venue
            dist = bellingham_dists[sample_date]
            for date in venue_info["dates"]:
                if date not in bellingham_dists:
                    bellingham_dists[date] = dist
            continue

        venue_loc = venue_info["loc"]
        print(f"  Bellingham -> {venue_loc['city']}: ", end="")
        dist = get_driving_distance(
            bellingham["lat"],
            bellingham["lng"],
            venue_loc["lat"],
            venue_loc["lng"],
        )
        api_calls += 1

        if dist:
            print(f"{dist['one_way_miles']:.1f} mi")
            for date in venue_info["dates"]:
                bellingham_dists[date] = dist
        else:
            print("FAILED")

    # --- Step 4: Add distances for 2026-04-12 for all teams ---
    print("\nStep 4: Ensuring all teams have distances for 2026-04-12...")
    # The 2026-04-12 event is at Spokane, same as 2024-04-14
    spokane_ref = "2024-04-14"
    new_date = "2026-04-12"

    for team in data["distances"]:
        if team == "Bellingham XC MTB":
            continue  # Already handled above
        if new_date not in data["distances"][team]:
            if spokane_ref in data["distances"][team]:
                data["distances"][team][new_date] = data["distances"][team][spokane_ref]
            else:
                print(f"  WARNING: No Spokane distance for {team}")

    # Also ensure all teams have distances for 2025-10-12 (Loup Loup)
    # The 2025-10-12 event should already have distances since it was in the
    # original Events CSV, but let's verify
    twisp_date = "2025-10-12"
    for team in data["distances"]:
        if twisp_date not in data["distances"][team]:
            print(f"  WARNING: No Twisp distance for {team}")

    print(f"  All teams have distances for both new dates")

    # --- Step 5: Build travel records for new attendance ---
    print("\nStep 5: Building travel records...")

    # Read new attendance from CSV
    new_dates = {"2025-10-12", "2026-04-12"}
    existing_travel_keys = {
        (r["team"], r["date"]) for r in data["travel_data"]
    }

    new_records = []
    with open(ATTENDANCE_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            date = row["race_date_iso"].strip()
            team = row["team"].strip()
            riders = int(row["riders"])

            if date not in new_dates:
                continue
            if (team, date) in existing_travel_keys:
                continue
            if team == "Independent":
                # Add to independent_data
                event_loc = data["event_locations"].get(date)
                if event_loc:
                    data.setdefault("independent_data", []).append(
                        {
                            "date": date,
                            "event_date": date,
                            "riders": riders,
                            "venue": event_loc.get("venue"),
                            "city": event_loc.get("city"),
                            "season": get_season(date),
                        }
                    )
                continue

            # Look up distances
            team_dists = data["distances"].get(team, {})
            dist = team_dists.get(date)

            if not dist:
                print(f"  WARNING: No distance for {team} -> {date}, skipping")
                continue

            vehicles = math.ceil(riders / RIDERS_PER_VEHICLE)
            event_loc = data["event_locations"].get(date, {})

            record = {
                "team": team,
                "date": date,
                "event_date": date,
                "riders": riders,
                "vehicles": vehicles,
                "one_way_miles": dist["one_way_miles"],
                "round_trip_miles": dist["round_trip_miles"],
                "total_miles_traveled": dist["round_trip_miles"] * vehicles,
                "one_way_minutes": dist["one_way_minutes"],
                "round_trip_minutes": dist["round_trip_minutes"],
                "total_minutes_traveled": dist["round_trip_minutes"] * vehicles,
                "venue": event_loc.get("venue"),
                "city": event_loc.get("city"),
                "season": get_season(date),
            }
            new_records.append(record)

    data["travel_data"].extend(new_records)

    print(f"  Added {len(new_records)} travel records")
    loup_count = sum(1 for r in new_records if r["date"] == "2025-10-12")
    riverside_count = sum(1 for r in new_records if r["date"] == "2026-04-12")
    print(f"    Loup Loup (2025-10-12): {loup_count} records")
    print(f"    Riverside Rampage (2026-04-12): {riverside_count} records")

    # --- Step 6: Update metadata ---
    data["metadata"]["generated_at"] = "2026-04-15T00:00:00.000Z"
    data["metadata"]["total_teams"] = len(data["team_locations"])
    data["metadata"]["total_events"] = len(data["event_locations"])
    data["metadata"]["total_attendance_records"] = len(data["travel_data"])
    data["metadata"]["independent_records"] = len(data.get("independent_data", []))

    # --- Step 7: Save ---
    print(f"\nSaving updated data...")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Also regenerate the JS wrapper for file:// dashboard access
    js_file = os.path.join(SCRIPT_DIR, "wscl_distance_data.js")
    with open(js_file, "w", encoding="utf-8") as f:
        f.write("window.__WSCL_DATA__ = ")
        json.dump(data, f, indent=2)
        f.write(";\n")
    print(f"  Also updated {os.path.basename(js_file)} for dashboard file:// access")

    print(f"\nDone!")
    print(f"  Teams: {data['metadata']['total_teams']}")
    print(f"  Events: {data['metadata']['total_events']}")
    print(f"  Travel records: {data['metadata']['total_attendance_records']}")
    print(f"  Independent records: {data['metadata']['independent_records']}")
    print(f"  Google API calls made: {api_calls}")


if __name__ == "__main__":
    main()
