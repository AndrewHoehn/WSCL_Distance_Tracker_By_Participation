#!/usr/bin/env python3
"""
WSCL Race Results Scraper
Fetches race results from the raceresult.com API and updates local CSV files.

Usage:
  # Using a pre-registered event from race_events.json:
  python scrape_race_results.py --date 2025-10-12

  # Using explicit API params for a new/unregistered race:
  python scrape_race_results.py --date 2026-09-27 --event-id 412345 --key abc123def456 \
      --city Lakewood --state WA --venue "Fort Steilacoom"

  # Dry run (fetch and display only, don't write CSVs):
  python scrape_race_results.py --date 2025-10-12 --dry-run
"""

import argparse
import csv
import json
import os
import re
import sys
from urllib.parse import urlencode

import requests

# File paths (relative to script directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEAM_NAME_MAP_FILE = os.path.join(SCRIPT_DIR, "team_name_map.json")
RACE_EVENTS_FILE = os.path.join(SCRIPT_DIR, "race_events.json")
TEAMS_CSV = os.path.join(SCRIPT_DIR, "Team_Names_and_Locations.csv")
EVENTS_CSV = os.path.join(SCRIPT_DIR, "Event_Names_and_IDs.csv")
ATTENDANCE_CSV = os.path.join(SCRIPT_DIR, "Team_Attendance_By_Date.csv")

API_BASE = "https://my-us-1.raceresult.com"
LIST_NAME = "Result Lists-Individual|Individual Results - By Team"


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved {path}")


def load_canonical_teams(path):
    """Load existing team names from Team_Names_and_Locations.csv."""
    teams = {}
    if not os.path.exists(path):
        return teams
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("team") or "").strip()
            if name:
                teams[name] = row
    return teams


def load_existing_events(path):
    """Load existing event dates from Event_Names_and_IDs.csv."""
    events = {}
    if not os.path.exists(path):
        return events
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = (row.get("event_date") or "").strip()
            if date:
                events[date] = row
    return events


def load_existing_attendance(path, date):
    """Check if attendance data already exists for a given date."""
    if not os.path.exists(path):
        return []
    existing = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("race_date_iso") or "").strip() == date:
                existing.append(row)
    return existing


def fetch_race_results(event_id, key):
    """Fetch race results from the raceresult.com API."""
    params = {
        "key": key,
        "listname": LIST_NAME,
        "page": "results",
        "contest": "0",
        "r": "all",
        "l": "0",
        "openedGroups": "{}",
        "term": "",
    }
    url = f"{API_BASE}/{event_id}/results/list?{urlencode(params)}"

    print(f"  Fetching: {API_BASE}/{event_id}/results/list")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_team_counts(api_data):
    """Extract team names and rider counts from API response."""
    headline = api_data.get("list", {}).get("HeadLine1", "Unknown Race")
    data = api_data.get("data", {})

    teams = {}
    for key, riders in data.items():
        # Keys are formatted as "#N_TeamName"
        team_name = re.sub(r"^#\d+_", "", key)
        teams[team_name] = len(riders)

    return headline, teams


def normalize_team_names(raw_teams, name_map, canonical_teams):
    """
    Map raw team names to canonical names.
    Returns (mapped_teams, unrecognized_teams, new_aliases).
    """
    mapped = {}  # canonical_name -> riders
    unrecognized = {}  # raw_name -> riders
    aliases_used = {}  # raw_name -> canonical_name (for display)

    for raw_name, riders in raw_teams.items():
        if raw_name in name_map:
            canonical = name_map[raw_name]
            mapped[canonical] = riders
            aliases_used[raw_name] = canonical
        elif raw_name in canonical_teams:
            mapped[raw_name] = riders
        else:
            unrecognized[raw_name] = riders

    return mapped, unrecognized, aliases_used


def prompt_for_unrecognized(unrecognized, canonical_teams, name_map):
    """
    Interactively resolve unrecognized team names.
    Returns (resolved_teams, new_aliases, new_teams_to_add).
    """
    resolved = {}
    new_aliases = {}
    new_teams = []

    if not unrecognized:
        return resolved, new_aliases, new_teams

    print("\n--- Unrecognized Teams ---")
    print("For each team, enter:")
    print("  - A canonical name to map to")
    print("  - 'add' to add as a new team")
    print("  - Press Enter to skip\n")

    # Show existing team names for reference
    existing = sorted(canonical_teams.keys())
    print(f"Existing teams ({len(existing)}):")
    for i, t in enumerate(existing):
        print(f"  {i+1:2d}. {t}")
    print()

    for raw_name, riders in sorted(unrecognized.items()):
        while True:
            answer = input(
                f"Unknown: '{raw_name}' ({riders} riders)\n"
                f"  Enter canonical name, team # from list above, 'add', or Enter to skip: "
            ).strip()

            if not answer:
                print(f"  Skipping '{raw_name}'")
                break

            if answer.lower() == "add":
                city = input(f"  City for '{raw_name}': ").strip()
                state = input(f"  State (e.g., WA): ").strip() or "WA"
                zip_code = input(f"  ZIP code: ").strip()
                new_teams.append(
                    {"team": raw_name, "city": city, "state": state, "zip": zip_code}
                )
                resolved[raw_name] = riders
                print(f"  Will add '{raw_name}' as new team")
                break

            # Check if they entered a number (team index)
            if answer.isdigit():
                idx = int(answer) - 1
                if 0 <= idx < len(existing):
                    canonical = existing[idx]
                    new_aliases[raw_name] = canonical
                    resolved[canonical] = riders
                    print(f"  Mapped '{raw_name}' -> '{canonical}'")
                    break
                else:
                    print(f"  Invalid number. Try again.")
                    continue

            # They typed a name directly
            if answer in canonical_teams:
                new_aliases[raw_name] = answer
                resolved[answer] = riders
                print(f"  Mapped '{raw_name}' -> '{answer}'")
                break
            else:
                confirm = input(
                    f"  '{answer}' is not an existing team. "
                    f"Create as new team? (y/n): "
                ).strip()
                if confirm.lower() == "y":
                    city = input(f"  City for '{answer}': ").strip()
                    state = input(f"  State (e.g., WA): ").strip() or "WA"
                    zip_code = input(f"  ZIP code: ").strip()
                    new_teams.append(
                        {
                            "team": answer,
                            "city": city,
                            "state": state,
                            "zip": zip_code,
                        }
                    )
                    new_aliases[raw_name] = answer
                    resolved[answer] = riders
                    print(f"  Will add '{answer}' as new team, mapped from '{raw_name}'")
                    break

    return resolved, new_aliases, new_teams


def display_summary(headline, mapped_teams, aliases_used, date):
    """Display a summary table of the results."""
    print(f"\n{'=' * 60}")
    print(f"Race: {headline}")
    print(f"Date: {date}")
    print(f"{'=' * 60}")
    print(f"{'Team':<35} {'Riders':>7}  {'Note'}")
    print(f"{'-' * 35} {'-' * 7}  {'-' * 20}")

    total = 0
    for team in sorted(mapped_teams.keys()):
        riders = mapped_teams[team]
        total += riders
        # Find if this was aliased
        alias_note = ""
        for raw, canonical in aliases_used.items():
            if canonical == team:
                alias_note = f"(from: {raw})"
                break
        print(f"{team:<35} {riders:>7}  {alias_note}")

    print(f"{'-' * 35} {'-' * 7}")
    print(f"{'TOTAL':<35} {total:>7}")
    print(f"{'Teams':<35} {len(mapped_teams):>7}")
    return total


def append_attendance(path, date, team_riders):
    """Append attendance rows to Team_Attendance_By_Date.csv."""
    rows_to_add = []
    for team in sorted(team_riders.keys()):
        rows_to_add.append(
            {
                "race_date_iso": date,
                "team": team,
                "riders": team_riders[team],
            }
        )

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["race_date_iso", "team", "riders"])
        for row in rows_to_add:
            writer.writerow(row)

    print(f"  Appended {len(rows_to_add)} rows to {os.path.basename(path)}")


def append_event(path, date, city, state, venue):
    """Append a new event row to Event_Names_and_IDs.csv."""
    location_key = f"{city}, {venue}"
    event_id = f"{date}_{city.replace(' ', '_')}_{venue.replace(' ', '_')}"

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "location_key",
                "city",
                "state",
                "venue",
                "event_date",
                "event_id",
            ],
        )
        writer.writerow(
            {
                "location_key": location_key,
                "city": city,
                "state": state,
                "venue": venue,
                "event_date": date,
                "event_id": event_id,
            }
        )

    print(f"  Added event: {location_key} ({date}) to {os.path.basename(path)}")


def append_team(path, team_info):
    """Append a new team row to Team_Names_and_Locations.csv."""
    # Find the next index
    max_idx = -1
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            try:
                max_idx = max(max_idx, int(row[0]))
            except (ValueError, IndexError):
                pass

    new_idx = max_idx + 1

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                new_idx,
                team_info["team"],
                team_info["city"],
                team_info["state"],
                team_info["zip"],
                "",
                "",
            ]
        )

    print(
        f"  Added team: {team_info['team']} ({team_info['city']}, {team_info['state']}) "
        f"to {os.path.basename(path)}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Scrape WSCL race results and update CSV files"
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Race date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--event-id",
        help="raceresult.com event ID (if not in race_events.json)",
    )
    parser.add_argument(
        "--key",
        help="raceresult.com API key (if not in race_events.json)",
    )
    parser.add_argument("--city", help="Event city (for new events)")
    parser.add_argument("--state", help="Event state (for new events)")
    parser.add_argument("--venue", help="Event venue name (for new events)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and display results without writing to CSVs",
    )

    args = parser.parse_args()
    race_date = args.date

    print(f"\nWSCL Race Results Scraper")
    print(f"========================\n")

    # Load config files
    name_map = load_json(TEAM_NAME_MAP_FILE)
    race_events = load_json(RACE_EVENTS_FILE)
    canonical_teams = load_canonical_teams(TEAMS_CSV)
    existing_events = load_existing_events(EVENTS_CSV)

    # Resolve event ID and key
    event_id = args.event_id
    api_key = args.key
    city = args.city
    state = args.state
    venue = args.venue

    if race_date in race_events:
        event_info = race_events[race_date]
        event_id = event_id or event_info["event_id"]
        api_key = api_key or event_info["key"]
        city = city or event_info.get("city")
        state = state or event_info.get("state")
        venue = venue or event_info.get("venue")
        print(f"  Found event in registry: {event_info.get('name', race_date)}")
    elif not event_id or not api_key:
        print(f"  Error: Race date {race_date} not found in {RACE_EVENTS_FILE}")
        print(f"  Provide --event-id and --key explicitly, or add to race_events.json")
        sys.exit(1)

    # Check for existing attendance data
    existing_attendance = load_existing_attendance(ATTENDANCE_CSV, race_date)
    if existing_attendance:
        print(f"\n  WARNING: {len(existing_attendance)} attendance records already "
              f"exist for {race_date}")
        if not args.dry_run:
            answer = input("  Continue and add duplicates? (y/n): ").strip()
            if answer.lower() != "y":
                print("  Aborted.")
                sys.exit(0)

    # Fetch results from API
    print(f"\nFetching results for {race_date}...")
    api_data = fetch_race_results(event_id, api_key)
    headline, raw_teams = extract_team_counts(api_data)
    print(f"  Race: {headline}")
    print(f"  Raw teams found: {len(raw_teams)}")
    print(f"  Total riders: {sum(raw_teams.values())}")

    # Normalize team names
    print(f"\nNormalizing team names...")
    mapped, unrecognized, aliases_used = normalize_team_names(
        raw_teams, name_map, canonical_teams
    )

    if aliases_used:
        print(f"  Aliases resolved: {len(aliases_used)}")
        for raw, canonical in sorted(aliases_used.items()):
            print(f"    {raw} -> {canonical}")

    # Handle unrecognized teams
    new_aliases = {}
    new_teams = []
    if unrecognized:
        if args.dry_run:
            print(f"\n  Unrecognized teams (would prompt in non-dry-run mode):")
            for name, riders in sorted(unrecognized.items()):
                print(f"    {name}: {riders} riders")
        else:
            resolved, new_aliases, new_teams = prompt_for_unrecognized(
                unrecognized, canonical_teams, name_map
            )
            mapped.update(resolved)

    # Display summary
    total = display_summary(headline, mapped, aliases_used, race_date)

    if args.dry_run:
        print(f"\n  DRY RUN - no files modified")
        return

    # Confirm before writing
    print()
    confirm = input("Write this data to CSV files? (y/n): ").strip()
    if confirm.lower() != "y":
        print("Aborted.")
        return

    # Write data
    print(f"\nWriting data...")

    # 1. Append attendance
    append_attendance(ATTENDANCE_CSV, race_date, mapped)

    # 2. Add event if needed
    if race_date not in existing_events:
        if city and venue:
            append_event(EVENTS_CSV, race_date, city, state or "WA", venue)
        else:
            print(f"\n  Event {race_date} not in Events CSV.")
            city = city or input("  City: ").strip()
            state = state or input("  State (e.g., WA): ").strip() or "WA"
            venue = venue or input("  Venue name: ").strip()
            if city and venue:
                append_event(EVENTS_CSV, race_date, city, state, venue)

        # Also add to race_events.json for future reference
        if race_date not in race_events:
            race_events[race_date] = {
                "event_id": event_id,
                "key": api_key,
                "name": headline,
                "city": city,
                "state": state,
                "venue": venue,
            }
            save_json(RACE_EVENTS_FILE, race_events)
    else:
        print(f"  Event {race_date} already in Events CSV - skipping")

    # 3. Add new teams
    for team_info in new_teams:
        append_team(TEAMS_CSV, team_info)

    # 4. Save new aliases to name map
    if new_aliases:
        name_map.update(new_aliases)
        save_json(TEAM_NAME_MAP_FILE, name_map)
        print(f"  Added {len(new_aliases)} new alias(es) to team_name_map.json")

    print(f"\nDone! {len(mapped)} attendance records written for {race_date}")
    print(f"Total riders: {total}")


if __name__ == "__main__":
    main()
