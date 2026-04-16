# WSCL Tracker

A leaderboard for the unglamorous, pre-dawn, gas-station-coffee half of the Washington Student Cycling League: **the driving**.

🔗 **Live site:** [wscltracker.com](https://wscltracker.com)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-actively%20maintained-success.svg)
![Not Affiliated](https://img.shields.io/badge/officially%20affiliated-no-lightgrey.svg)

## Why this exists

A few of us were sitting around a campfire at a race weekend when somebody asked: so who actually drives the furthest to get to these? Everyone had a theory. Everyone had a candidate. Nobody had any numbers.

So here's the numbers.

We love WSCL. We love watching our kids ride bikes on real dirt, get braver, make friends, bonk, bonk again, come home exhausted and happy. The coaches and course crews are volunteers and they're saints. It is a genuinely great thing.

It is also a frankly absurd amount of driving. This is a small monument to that.

## What's in it

- **📊 Team Leaderboard** — total vehicle-miles by team, all-time or per season
- **🏁 Race Day** — pick a race, hit play, watch every team converge on the venue at real-drive-time proportions
- **📍 Venue Analysis** — which venues keep everyone closest, plus per-venue animated maps
- **👥 Team Deep Dive** — one team's whole story, with animated "travel journey" fanning out from their home
- **🏆 Awards** — Long Haul, Home Turf, Odyssey, Trailblazer
- **💰 Cost Analysis** — what a whole season of gas actually costs a family (don't look before payday)

## Running locally

**Easiest — open the file:**
Clone the repo and open `index.html` in any modern browser. No build, no server. Works from `file://`.

**With a local server:**
```bash
git clone https://github.com/AndrewHoehn/WSCL_Distance_Tracker_By_Participation.git
cd WSCL_Distance_Tracker_By_Participation
python3 -m http.server 8000
```
Then [http://localhost:8000/](http://localhost:8000/).

## Updating with a new race

After each race weekend:

### 1. Scrape the results
```bash
# A race already registered in race_events.json:
python3 scrape_race_results.py --date 2026-04-26

# Or a new race (grab event-id and key from the browser Network tab on the WSCL results page):
python3 scrape_race_results.py --date 2026-04-26 --event-id 412345 --key abc123 \
    --city "Cle Elum" --state WA --venue "Roslyn High School"

# Preview only, don't write:
python3 scrape_race_results.py --date 2026-04-26 --dry-run
```

### 2. Patch the distance data
```bash
export GOOGLE_MAPS_API_KEY="your-key-here"
python3 patch_distance_data.py
```
Only makes Google API calls for genuinely new team/venue pairs.

### 3. Refresh route polylines (optional, only if the race is new)
```bash
python3 fetch_missing_routes.py
```
Grabs driving-route polylines for any team/race pair not already in `route_cache.json`. These power the animated maps.

### 4. Rebuild the data files that the dashboard reads
The patch script regenerates `wscl_distance_data.json` and `.js`. If you ran step 3, re-run the routes builder (see the data-prep snippet in this repo's commit history, or just rerun `generate_heatmaps.py` if you want static PNGs too).

## Project files

| File | Purpose |
|---|---|
| `index.html` / `wscl_dashboard_v2.html` | The dashboard — a single-file React app using Babel-standalone |
| `wscl_distance_data.json` + `.js` | All computed distances and travel records |
| `race_routes.json` + `.js` | Route polylines powering the animated maps |
| `route_cache.json` | Google Directions polylines (gitignored, large) |
| `scrape_race_results.py` | Pulls race results from raceresult.com |
| `patch_distance_data.py` | Adds new distances/races without re-running the whole geocoder |
| `fetch_missing_routes.py` | Grabs route polylines for new races |
| `generate_heatmaps.py` | Older static-PNG heatmap generator (superseded by interactive maps, kept for reference) |
| `team_name_map.json` | Normalizes team names from raceresult.com to canonical names |
| `race_events.json` | Registry of event IDs for the scraper |
| `*.csv` | Source data: event IDs, team home locations, attendance |

## What this is *not*

- **Not official.** Completely unaffiliated with WSCL. They had nothing to do with this and don't owe anyone any of it.
- **Not precise.** "Inland NW drives 97,000 miles per season" is true in the aggregate sense; it is not true that Inland NW puts exactly 97,000 miles on exactly N cars. It's a model, with assumptions below.
- **Not a complaint.** The driving is the tax you pay to be part of this thing. The thing is worth it.

## Assumptions & rough edges

- All riders on a team travel from the team's home city. Real families are spread across a region; I can't know where each one lives.
- "Riders per vehicle" defaults to 2. The leaderboard slider lets you play with that.
- Distances are Google Maps driving routes — real roads, not crow-flies, but also not the exact route your family took.
- The cost is calculated at the IRS standard mileage rate ($0.725/mi for 2025). Your actual gas bill depends on your particular vehicle.
- Independent riders are counted in attendance totals but not in driving math (no team home to measure from).
- Future races use distances from the scheduled venue but attendance is unknown until race day.

## Data coverage

- **Teams:** 28 across Washington and Idaho
- **Seasons:** Spring 2023 → ongoing
- **Races tracked so far:** 22 and counting
- **Total miles driven:** 1.17M+ and counting — see the site for the current number

## Acknowledgments

- **WSCL** — for being worth all this driving. Coaches, course crews, volunteers: thank you.
- **Google Maps Platform** — geocoding and routing, without which this would have been vibes.
- **Leaflet + CartoDB** — powering the interactive maps, no API keys required.
- **React + Tailwind via CDN** — one-file-app hosting in the age of build tools.
- **Everyone who's ever eaten a gas-station breakfast burrito en route to a WSCL course** — this is for you.

---

Built by one WSCL parent. Open an issue if you spot something wrong — I've almost certainly got your team's commute backwards.

Also, if you liked this, check out [✈️ Will I Fly PUW](https://williflypuw.com/) — flight-cancellation predictions for the Moscow / Pullman airport, another hobby project born from wanting to know a number that nobody kept track of.
