# WSCL Travel Distance Tracker

An interactive web dashboard for tracking and analyzing travel distances for Washington Student Cycling League (WSCL) teams traveling to races throughout Washington state.

![Dashboard Preview](https://img.shields.io/badge/status-active-success.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 🎯 Overview

The WSCL Travel Distance Tracker calculates and visualizes the environmental and logistical impact of student cycling teams traveling to races. It uses Google Maps APIs to calculate precise driving distances and times, then combines this with actual attendance data to provide comprehensive insights.

**Key Metrics:**
- Total miles traveled by each team
- Average distance per race entry
- Travel time calculations
- Vehicle requirements based on carpooling
- Season-by-season comparisons

## 🤷 Why?

We spend a lot of our time driving back and forth to races every spring and fall, and thought to ourselves, "I'll bet our team drives more than these other teams." But I'll be we're not the only parents who thinik tha. So, we made a tool to answer that quesiton. 

## ✨ Features

### 📊 Four Interactive Views

1. **Team Leaderboard**
   - Rank teams by total or average travel distance
   - Filter by season (Spring/Fall) or view all-time stats
   - Toggle between actual attendance and theoretical comparisons
   - Adjust riders-per-vehicle assumptions

2. **Venue Analysis**
   - See travel distances from all teams to each venue
   - Compare theoretical vs. actual travel for specific events
   - Identify which venues are most/least accessible

3. **Team Deep Dive**
   - Comprehensive statistics for individual teams
   - Race-by-race breakdown with visual charts
   - Venue rankings by distance from team home base
   - Cumulative totals and averages

4. **Methodology**
   - Detailed explanation of all calculations
   - Data sources and processing methods
   - Transparency in assumptions and limitations

### 🔧 Advanced Features

- **Smart Date Matching**: Automatically matches attendance records to events within a ±2 day window
- **Efficient Geocoding**: Calculates distances once per team-venue pair, even for recurring events
- **Independent Rider Tracking**: Tracks unaffiliated riders separately (no travel calculations)
- **Configurable Settings**: Adjust riders-per-vehicle to see how carpooling impacts totals
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## 🚀 Quick Start

### Prerequisites

- Node.js (v14 or higher)
- Google Maps API key with:
  - Geocoding API enabled
  - Distance Matrix API enabled
- Python 3 (for running local web server)

### 1. Clone the Repository

```bash
git clone https://github.com/AndrewHoehn/wscl-travel-tracker.git
cd wscl-travel-tracker
```

### 2. Install Dependencies

```bash
npm install papaparse axios
```

### 3. Prepare Your Data

Place these three CSV files in the project directory:

- `Team_Names_and_Locations.csv`
- `Event_Names_and_IDs.csv`
- `Team_Attendance_By_Date.csv`

### 4. Configure API Key

Edit `calculate_distances.js` and replace `YOUR_API_KEY_HERE` with your Google Maps API key:

```javascript
const CONFIG = {
  GOOGLE_MAPS_API_KEY: 'your-actual-api-key-here',
  // ...
};
```

### 5. Generate Distance Data

```bash
node calculate_distances.js
```

This will create `wscl_distance_data.json` (takes 5-10 minutes).

### 6. Launch Dashboard

```bash
python3 -m http.server 8000
```

Open your browser to: `http://localhost:8000/wscl_dashboard.html`

Or host it somewhere on the internet. 

## 📦 Installation

### Detailed Setup

1. **Install Node.js packages:**

```bash
npm install papaparse axios
```

2. **Set up Google Maps API:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or use existing)
   - Enable "Geocoding API" and "Distance Matrix API"
   - Create credentials → API Key
   - Copy your API key

3. **Configure the geocoding script:**

```javascript
// In calculate_distances.js
const CONFIG = {
  GOOGLE_MAPS_API_KEY: 'YOUR_API_KEY',
  RIDERS_PER_VEHICLE: 2,
  BOUNDS: {
    southwest: { lat: 41.9, lng: -125.0 },
    northeast: { lat: 49.0, lng: -116.0 }
  }
};
```

## 📖 Usage

### Running the Geocoding Script

The script processes data in five steps:

```bash
node calculate_distances.js
```

**What it does:**
1. Geocodes all team home locations (skips "Independent")
2. Geocodes all event venues
3. Calculates distances between teams and venues
4. Combines with attendance data
5. Generates `wscl_distance_data.json`

**Output:**
```
✓ Data saved to wscl_distance_data.json

=== SUMMARY ===
Teams geocoded: 27
Events geocoded: 20
Travel records: 450
Independent rider records: 15
Total miles traveled: 125,432 miles
```

### Updating Data

When you get new race attendance or add new events:

1. Update the appropriate CSV file(s)
2. Re-run the geocoding script
3. Refresh the dashboard

The script will recalculate everything with the new data.

### Dashboard Controls

**Season Filter:**
- All Time (Since 2023)
- Spring [Year] (March-June)
- Fall [Year] (September-October)

**View Modes:**
- **Actual**: Based on riders who actually attended
- **Theoretical**: Assumes each team sent 1 vehicle to every race

**Metric Modes:**
- **Total Miles**: Sum of all miles traveled
- **Avg per Entry**: Distance per individual race entry

**Riders per Vehicle:**
- Adjustable (1-10)
- Only affects "Total Miles" calculations
- Disabled for "Avg per Entry" view

## 📊 Data Structure

### Input Files

#### Team_Names_and_Locations.csv
```csv
team,city,state,zip
Anacortes Composite,Anacortes,WA,98221
Bainbridge Island,Bainbridge Island,WA,98110
```

#### Event_Names_and_IDs.csv
```csv
location_key,city,state,venue,event_date,event_id
GigHarbor,Gig Harbor,WA,360 Trails,2023-04-16,2023-04-16_GigHarbor_360Trails
```

#### Team_Attendance_By_Date.csv
```csv
race_date_iso,team,riders
2023-04-16,Anacortes Composite,30
2023-04-16,Bainbridge Island,21
```

### Output File

The script generates `wscl_distance_data.json`:

```json
{
  "metadata": {
    "generated_at": "2025-10-02T10:30:00.000Z",
    "riders_per_vehicle": 2,
    "total_teams": 27,
    "total_events": 20
  },
  "team_locations": { /* geocoded coordinates */ },
  "event_locations": { /* geocoded coordinates */ },
  "distances": { /* calculated distances */ },
  "travel_data": [ /* actual attendance with distances */ ],
  "independent_data": [ /* independent rider counts */ ]
}
```

## 🧮 Methodology

### Distance Calculations

**One-Way Distance:**
```
Google Maps Distance Matrix API
Mode: Driving
From: Team home base (city, state, zip)
To: Event venue or city
```

**Round-Trip Distance:**
```
Round-trip = One-way × 2
```

**Total Miles (Actual Mode):**
```
Vehicles = ROUNDUP(Race Entries ÷ Riders per Vehicle)
Total Miles = Round-trip Distance × Vehicles
```

**Average Miles per Entry:**
```
Each race entry = Round-trip Distance
(Regardless of carpooling, each rider travels the full distance)
```

### Season Definitions

- **Spring**: March 1 - June 30
- **Fall**: September 1 - October 31

### Geographic Scope

All geocoding is bounded to:
- **Southwest**: 41.9°N, -125.0°W
- **Northeast**: 49.0°N, -116.0°W

This covers Washington, Idaho, and northern Oregon.

### Key Assumptions

1. All riders travel from their team's home base
2. Carpooling efficiency is consistent across teams
3. Routes follow Google Maps driving directions
4. Independent riders have no fixed location (not tracked for travel)

### Limitations

- Distances assume direct routes via Google Maps
- Travel times are estimates without real-time traffic
- Does not account for riders living far from team home base
- Carpooling rates may vary by race and team
- Does not include racers who attend a race, but do not race
- Does not include data from the coaches race, or the Cle Elum relay 

## 🔄 Updating for New Seasons

### Adding New Races

1. **Update Event_Names_and_IDs.csv:**
   ```csv
   NewVenue,City,WA,Venue Name,2026-04-15,2026-04-15_City_VenueName
   ```

2. **Run geocoding script:**
   ```bash
   node calculate_distances.js
   ```

3. **Dashboard automatically shows new races** as "theoretical" until attendance is added

### Adding Attendance Data

1. **Update Team_Attendance_By_Date.csv:**
   ```csv
   2026-04-15,Team Name,25
   ```

2. **Re-run geocoding script**

3. **Dashboard updates with actual travel data**

## 🛠️ Customization

### Adjusting Geographic Bounds

Edit `calculate_distances.js`:

```javascript
BOUNDS: {
  southwest: { lat: YOUR_LAT, lng: YOUR_LNG },
  northeast: { lat: YOUR_LAT, lng: YOUR_LNG }
}
```

### Changing Default Riders per Vehicle

```javascript
RIDERS_PER_VEHICLE: 3, // Change from 2 to 3
```

### Adjusting API Rate Limits

```javascript
RATE_LIMIT_DELAY: 200, // Increase delay between API calls (ms)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Code Style

- Use meaningful variable names
- Comment complex calculations
- Follow existing formatting patterns
- Test with real data before submitting

## 🙏 Acknowledgments

- Washington Student Cycling League for the race data (and for running a great cycling league)
- Google Maps Platform for geocoding and distance APIs
- All the volunteer coaches and families who make WSCL possible

### Known Issues

- Date matching requires ±2 day window (minor discrepancies in date recording)
- Very large datasets (100+ teams, 50+ events) may slow down initial geocoding

---

**Built with ❤️ for the Washington Student Cycling League**
