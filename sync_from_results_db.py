#!/usr/bin/env python3
"""
Add new races to the tracker from the WSCL results database.

Finds main races in wscl.sqlite dated after the tracker's latest race and adds
each one end to end: attendance rows, race_events.json, event location,
distances, travel_data, independent_data, route lines, and metadata.

Riders per team = competitive finishers at that race:
    SELECT team, count(*) FROM results
    WHERE date = ? AND non_competitive = 0 GROUP BY team

The database is opened read-only. Races already in the tracker are left alone
unless named with --rebuild (recount from the database) or --drop (remove).

Google is called only for team-venue pairs with nothing cached. The script
prints how many calls it needs and asks before making any (--yes skips the
question).

Usage (after running update.py in wscl_results):
    .venv/bin/python sync_from_results_db.py            # add new races
    .venv/bin/python sync_from_results_db.py --dry-run  # show what would change
    .venv/bin/python sync_from_results_db.py --date 2026-09-20
    .venv/bin/python sync_from_results_db.py --rebuild 2024-06-02 --drop 2025-05-03

A new venue needs a row in Event_Names_and_IDs.csv first; the script stops
and says so.
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

import fetch_missing_routes as routes
import patch_distance_data as patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(
    os.path.dirname(SCRIPT_DIR), "Palouse_Composite_MTB", "Scripts", "wscl_results"
)
DEFAULT_DB = os.path.join(RESULTS_DIR, "data", "wscl.sqlite")
DB_EVENTS_JSON = os.path.join(RESULTS_DIR, "data", "events.json")
RACE_EVENTS_JSON = os.path.join(SCRIPT_DIR, "race_events.json")
ROUTE_CACHE = routes.CACHE_FILE

RIDER_COUNT_SQL = """
    SELECT team, count(*) AS riders
    FROM results
    WHERE date = ? AND non_competitive = 0
    GROUP BY team
"""


def read_attendance():
    with open(patch.ATTENDANCE_CSV, newline="", encoding="utf-8") as f:
        return [
            (r["race_date_iso"].strip(), r["team"].strip(), int(r["riders"]))
            for r in csv.DictReader(f)
        ]


def write_attendance(rows):
    with open(patch.ATTENDANCE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["race_date_iso", "team", "riders"])
        w.writerows(sorted(rows, key=lambda r: (r[0], r[1])))


def remove_venue_rows(dates):
    """Drop rows for these dates from Event_Names_and_IDs.csv, keeping its format."""
    with open(patch.EVENTS_CSV, encoding="utf-8") as f:
        lines = f.read().split("\n")
    keep = [ln for ln in lines if not any(f",{d},{d}_" in ln for d in dates)]
    with open(patch.EVENTS_CSV, "w", encoding="utf-8") as f:
        f.write("\n".join(keep))


def venues_by_date():
    with open(patch.EVENTS_CSV, newline="", encoding="utf-8") as f:
        return {row["event_date"].strip(): row for row in csv.DictReader(f)}


def db_races(con):
    """Main races that have competitive results, keyed by date."""
    rows = con.execute(
        """SELECT e.date, e.name, e.event_id FROM events e
           WHERE e.kind = 'race' AND EXISTS (
               SELECT 1 FROM results r WHERE r.date = e.date AND r.non_competitive = 0)
           ORDER BY e.date"""
    ).fetchall()
    return {d: {"name": n, "event_id": str(eid)} for d, n, eid in rows}


def raceresult_keys():
    """event_id -> raceresult key, for race_events.json."""
    if not os.path.exists(DB_EVENTS_JSON):
        return {}
    with open(DB_EVENTS_JSON) as f:
        return {str(e["event_id"]): e.get("key") for e in json.load(f)}


def plan_race(data, date, venue, counts, races, cache, previous=None):
    """Count the Google calls one race needs, without making any."""
    calls = {"geocode": 0, "distance": 0, "route": 0}
    event = data["event_locations"].get(date)
    if not event:
        geo = patch.find_venue_coords(data, venue["city"], venue["venue"])
        if not geo:
            # Unknown venue: every distance and route is new.
            teams = set(data["distances"]) | set(counts)
            calls["geocode"] = 1
            calls["distance"] = len(teams - {"Independent"})
            calls["route"] = len(set(counts) - {"Independent"})
            return calls
        event = {**geo, "city": venue["city"], "venue": venue["venue"]}
    probe = {**data, "event_locations": {**data["event_locations"], date: event}}
    for team in set(data["distances"]) | (set(counts) - {"Independent"}):
        if not patch.known_distance(probe, team, date):
            calls["distance"] += 1
    for team in counts:
        if team == "Independent":
            continue
        if routes.cached_points(cache, races, event, team, date, previous) is None:
            calls["route"] += 1
    return calls


def race_totals(data, date):
    recs = [r for r in data["travel_data"] if r["date"] == date]
    ind = sum(r["riders"] for r in data.get("independent_data", []) if r["date"] == date)
    return len(recs), sum(r["riders"] for r in recs), ind, sum(r["total_miles_traveled"] for r in recs)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--date", action="append", help="add this new race date (repeatable)")
    ap.add_argument("--rebuild", action="append", default=[], metavar="DATE",
                    help="recount a race already in the tracker from the database")
    ap.add_argument("--drop", action="append", default=[], metavar="DATE",
                    help="remove a race from the tracker")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    ap.add_argument("--yes", action="store_true", help="make Google calls without asking")
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    races_db = db_races(con)
    attendance = read_attendance()
    have = {r[0] for r in attendance}
    latest = max(have)

    for d in args.rebuild + args.drop:
        if d not in have:
            sys.exit(f"{d} is not in the tracker.")
    for d in args.rebuild:
        if d not in races_db:
            sys.exit(f"{d} has no main race with results in the database; use --drop instead.")
    if set(args.rebuild) & set(args.drop):
        sys.exit("A date can't be both rebuilt and dropped.")

    if args.date:
        new_dates = sorted(args.date)
        for d in new_dates:
            if d in have:
                sys.exit(f"{d} is already in the tracker. Use --rebuild to recount it.")
            if d not in races_db:
                sys.exit(f"{d} has no main race with results in the database.")
    else:
        new_dates = [d for d in races_db if d > latest]

    dates = sorted(set(new_dates) | set(args.rebuild))
    if not dates and not args.drop:
        print(f"Tracker is up to date (latest race {latest}).")
        return

    with open(patch.DATA_FILE) as f:
        data = json.load(f)
    races = routes.load_races()
    cache = {}
    if os.path.exists(ROUTE_CACHE):
        with open(ROUTE_CACHE) as f:
            cache = json.load(f)
    venues = venues_by_date()

    # Snapshot the races being replaced or removed, then take them out.
    replaced = set(args.rebuild) | set(args.drop)
    before = {d: race_totals(data, d) for d in replaced}
    previous = {r["date"]: r for r in races if r["date"] in args.rebuild}
    data["travel_data"] = [r for r in data["travel_data"] if r["date"] not in replaced]
    data["independent_data"] = [
        r for r in data.get("independent_data", []) if r["date"] not in replaced
    ]
    races = [r for r in races if r["date"] not in replaced]
    for d in args.drop:
        data["event_locations"].pop(d, None)
        for team_dists in data["distances"].values():
            team_dists.pop(d, None)
    attendance = [r for r in attendance if r[0] not in replaced]

    # --- Check and plan ---
    problems, plan = [], []
    for date in dates:
        counts = dict(con.execute(RIDER_COUNT_SQL, (date,)).fetchall())
        venue = venues.get(date)
        if not venue:
            problems.append(
                f"{date} {races_db[date]['name']}: no venue. Add a row to "
                f"Event_Names_and_IDs.csv (location_key,city,state,venue,event_date,event_id)."
            )
            continue
        unknown = [t for t in counts if t != "Independent" and t not in data["team_locations"]]
        if unknown:
            problems.append(
                f"{date}: teams not in the tracker: {', '.join(unknown)}. Add them to "
                f"Team_Names_and_Locations.csv and team_locations first."
            )
            continue
        calls = plan_race(data, date, venue, counts, races, cache, previous.get(date))
        plan.append((date, venue, counts, calls))

    if args.drop:
        print("Races to remove:")
        for d in sorted(args.drop):
            n, riders, ind, miles = before[d]
            print(f"  {d}: {n} teams, {riders} riders, {ind} independent, {miles:,.0f} miles")
    if plan:
        print("Races to add or rebuild:")
    for date, venue, counts, calls in plan:
        teams = len([t for t in counts if t != "Independent"])
        riders = sum(v for t, v in counts.items() if t != "Independent")
        was = ""
        if date in before:
            n, r0, i0, _ = before[date]
            was = f" (was {n} teams, {r0} riders, {i0} independent)"
        print(
            f"  {date}  {races_db[date]['name']} ({venue['venue']}, {venue['city']}): "
            f"{teams} teams, {riders} riders, {counts.get('Independent', 0)} independent{was}; "
            f"Google calls: {calls['geocode']} geocode, {calls['distance']} distance, "
            f"{calls['route']} route"
        )
    if problems:
        print("\nNeeds attention before these can be added:")
        for p in problems:
            print(f"  {p}")
        sys.exit(1)

    total_calls = sum(sum(c.values()) for *_, c in plan)
    print(f"\nTotal Google calls needed: {total_calls}")
    if args.dry_run:
        return
    if total_calls and not args.yes:
        if not sys.stdin.isatty() or input("Make these calls? [y/N] ").strip().lower() != "y":
            sys.exit("Stopped before calling Google. Nothing was changed.")

    # --- Apply ---
    keys = raceresult_keys()
    with open(RACE_EVENTS_JSON) as f:
        race_events = json.load(f)

    made = 0
    for date, venue, counts, _ in plan:
        made += patch.add_event_location(
            data, date, venue["city"], venue["state"], venue["venue"], venue["event_id"]
        )
        for team in sorted(set(data["distances"]) | (set(counts) - {"Independent"})):
            made += patch.ensure_distance(data, team, date)
        for team in sorted(counts):
            attendance.append((date, team, counts[team]))
            if team == "Independent":
                data["independent_data"].append(
                    patch.build_independent_record(data, date, counts[team])
                )
            else:
                data["travel_data"].append(
                    patch.build_travel_record(data, team, date, counts[team])
                )
        if date not in args.rebuild:
            eid = races_db[date]["event_id"]
            race_events[date] = {
                "event_id": eid,
                "key": keys.get(eid),
                "name": races_db[date]["name"],
                "city": venue["city"],
                "state": venue["state"],
                "venue": venue["venue"],
            }
    data["travel_data"].sort(key=lambda r: (r["date"], r["team"]))
    data["independent_data"].sort(key=lambda r: r["date"])

    route_calls = 0
    for date, *_ in plan:
        entry, n = routes.build_race_entry(data, date, races, cache, previous.get(date))
        route_calls += n
        races.append(entry)
    races.sort(key=lambda r: r["date"])

    write_attendance(attendance)
    if args.drop:
        remove_venue_rows(args.drop)
    with open(RACE_EVENTS_JSON, "w") as f:
        json.dump(dict(sorted(race_events.items())), f, indent=2)
        f.write("\n")
    patch.update_metadata(
        data, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    )
    patch.save_data(data)
    routes.save_races(races)
    if route_calls:
        with open(ROUTE_CACHE, "w") as f:
            json.dump(cache, f, indent=2)

    print(
        f"\nAdded or rebuilt {len(plan)} race(s), removed {len(args.drop)}. "
        f"Google calls made: {made + route_calls}"
    )
    print(f"  Travel records: {data['metadata']['total_attendance_records']}")
    print(f"  Independent records: {data['metadata']['independent_records']}")
    print("Next: python3 generate_og_image.py, check the dashboard, then deploy.")


if __name__ == "__main__":
    main()
