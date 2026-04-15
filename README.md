# WSCL Travel Distance Tracker

An interactive dashboard that tracks how far Washington Student Cycling League teams drive to get to races — and what it costs them.

![Dashboard Preview](https://img.shields.io/badge/status-active-success.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Why This Exists

WSCL teams are spread across Washington and Idaho. Some families drive 20 minutes to a race; others drive 6 hours. This dashboard makes that visible — who's logging the most miles, which venues generate the most driving, and what a season of racing actually costs a family depending on where they live.

## How to View the Dashboard

**Option 1 — Just open the file:**
Download `wscl_dashboard_v2.html` and `wscl_distance_data.js` into the same folder. Open the HTML file in your browser. No server needed.

**Option 2 — Local server:**
```bash
git clone https://github.com/AndrewHoehn/WSCL_Distance_Tracker_By_Participation.git
cd WSCL_Distance_Tracker_By_Participation
python3 -m http.server 8000
```
Open `http://localhost:8000/wscl_dashboard_v2.html`

## Dashboard Tabs

**Team Leaderboard** — All teams ranked by total vehicle-miles driven. Filter by season, toggle between actual attendance and theoretical (every team at every race).

**Venue Analysis** — Which race venues keep everyone closest? Toggle between theoretical centrality and actual miles driven. Drill into individual venues for team-by-team breakdowns.

**Team Deep Dive** — Select a team to see race-by-race travel, per-family cost by season, and venue distance rankings. Upcoming scheduled races are shown with projected distances.

**Awards** — Per-race and season-long awards: Long Haul (farthest drive), Home Turf (shortest), Odyssey (most cumulative miles), Trailblazer (biggest single-race commitment).

**Cost Analysis** — What it costs one family to attend every race in a season, ranked by team. Uses the IRS mileage rate ($0.725/mile). Includes upcoming scheduled races as projections.

**Methodology** — How the data is collected, how miles are calculated, key assumptions.

## Adding New Race Data

After each race, update the dashboard with new results:

### 1. Scrape race results

```bash
# For a race already registered in race_events.json:
python3 scrape_race_results.py --date 2026-04-26

# For a new race (get event-id and key from browser Network tab):
python3 scrape_race_results.py --date 2026-04-26 --event-id 412345 --key abc123 \
    --city "Cle Elum" --state WA --venue "Roslyn High School"

# Dry run (preview without writing):
python3 scrape_race_results.py --date 2026-04-26 --dry-run
```

The scraper fetches results from the raceresult.com API, normalizes team names using `team_name_map.json`, and updates the CSV files.

### 2. Update distance data

```bash
# Set your Google Maps API key (only needed for new teams or venues):
export GOOGLE_MAPS_API_KEY="your-key-here"

# Patch the distance data (only makes API calls for truly new data):
python3 patch_distance_data.py
```

This updates `wscl_distance_data.json` and regenerates `wscl_distance_data.js`. For existing venues, distances are copied from prior races — no API calls needed.

### 3. Refresh the dashboard

Just reload the page. The dashboard reads from the JSON file.

## Project Files

| File | Purpose |
|------|---------|
| `wscl_dashboard_v2.html` | The dashboard (single-file React app) |
| `wscl_distance_data.json` | All computed distances and travel records |
| `wscl_distance_data.js` | JS wrapper for file:// access (same data) |
| `scrape_race_results.py` | Scrapes race results from WSCL website |
| `patch_distance_data.py` | Updates distance data with new races/teams |
| `team_name_map.json` | Maps raceresult.com team names to canonical names |
| `race_events.json` | Registry of known race event IDs for the scraper |
| `Event_Names_and_IDs.csv` | Race events with venues and dates |
| `Team_Names_and_Locations.csv` | Team home cities and ZIP codes |
| `Team_Attendance_By_Date.csv` | Rider counts per team per race |
| `calculate_distances.js` | Original full geocoding script (re-geocodes everything) |

## Data Coverage

- **Teams:** 28 (across Washington and Idaho)
- **Races:** 2023 Spring through 2026 Spring (ongoing)
- **Distances:** Google Maps driving routes (not straight lines)
- **Cost rate:** IRS standard mileage rate, $0.725/mile (2025)

## Key Assumptions

- All riders on a team travel from the team's home city
- Default carpooling: 2 riders per vehicle (adjustable in dashboard)
- Distances are Google Maps driving routes, not actual routes driven
- Independent riders are tracked for attendance but not travel
- Future/upcoming races use distances from prior events at the same venue

## Acknowledgments

- Washington Student Cycling League for running a great league
- Google Maps Platform for geocoding and distance APIs
- All the volunteer coaches and families who make WSCL possible

---

**Built by a WSCL parent who wanted to know what all that windshield time actually adds up to.**
