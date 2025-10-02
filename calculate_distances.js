// WSCL Distance Calculator - Geocoding and Distance Calculation Script
// Run with Node.js: node calculate_distances.js

const fs = require("fs");
const Papa = require("papaparse");
const axios = require("axios");

// Configuration
const CONFIG = {
  GOOGLE_MAPS_API_KEY: "YOUR_GOOGLE_MAPS_API_KEY", // Replace with your API key
  RIDERS_PER_VEHICLE: 2,
  BOUNDS: {
    // Washington, Idaho, Oregon bounds
    southwest: { lat: 41.9, lng: -125.0 },
    northeast: { lat: 49.0, lng: -116.0 },
  },
  RATE_LIMIT_DELAY: 100, // ms between API calls
};

// Helper function to delay between API calls
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Read CSV files
function readCSV(filename) {
  const file = fs.readFileSync(filename, "utf8");
  return Papa.parse(file, {
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
  }).data;
}

// Geocode an address using Google Maps API
async function geocodeAddress(address, bounds) {
  try {
    const response = await axios.get(
      "https://maps.googleapis.com/maps/api/geocode/json",
      {
        params: {
          address: address,
          bounds: `${bounds.southwest.lat},${bounds.southwest.lng}|${bounds.northeast.lat},${bounds.northeast.lng}`,
          key: CONFIG.GOOGLE_MAPS_API_KEY,
        },
      },
    );

    if (response.data.status === "OK" && response.data.results.length > 0) {
      const result = response.data.results[0];
      return {
        lat: result.geometry.location.lat,
        lng: result.geometry.location.lng,
        formatted_address: result.formatted_address,
      };
    } else {
      console.warn(
        `Geocoding failed for: ${address} - Status: ${response.data.status}`,
      );
      return null;
    }
  } catch (error) {
    console.error(`Error geocoding ${address}:`, error.message);
    return null;
  }
}

// Get driving distance and time using Google Maps Distance Matrix API
async function getDrivingDistance(origin, destination) {
  try {
    const response = await axios.get(
      "https://maps.googleapis.com/maps/api/distancematrix/json",
      {
        params: {
          origins: `${origin.lat},${origin.lng}`,
          destinations: `${destination.lat},${destination.lng}`,
          mode: "driving",
          units: "imperial",
          key: CONFIG.GOOGLE_MAPS_API_KEY,
        },
      },
    );

    if (
      response.data.status === "OK" &&
      response.data.rows[0].elements[0].status === "OK"
    ) {
      const element = response.data.rows[0].elements[0];
      return {
        distance_miles: element.distance.value * 0.000621371, // meters to miles
        duration_minutes: element.duration.value / 60, // seconds to minutes
        distance_text: element.distance.text,
        duration_text: element.duration.text,
      };
    } else {
      console.warn(
        `Distance calculation failed - Status: ${response.data.status}`,
      );
      return null;
    }
  } catch (error) {
    console.error("Error calculating distance:", error.message);
    return null;
  }
}

// Main processing function
async function calculateAllDistances() {
  console.log("Starting WSCL Distance Calculator...\n");

  // Read data files
  const teams = readCSV("Team_Names_and_Locations.csv");
  const events = readCSV("Event_Names_and_IDs.csv");
  const attendance = readCSV("Team_Attendance_By_Date.csv");

  console.log(
    `Loaded ${teams.length} teams, ${events.length} events, ${attendance.length} attendance records\n`,
  );

  // Step 1: Geocode team home bases
  console.log("Step 1: Geocoding team locations...");
  const teamLocations = {};

  for (const team of teams) {
    // Skip "Independent" - we don't track travel for independent riders
    if (team.team === "Independent") {
      console.log(`  Skipping: ${team.team} (no fixed location)`);
      continue;
    }

    const address = `${team.city}, ${team.state} ${team.zip}`;
    console.log(`  Geocoding: ${team.team} - ${address}`);

    const location = await geocodeAddress(address, CONFIG.BOUNDS);
    if (location) {
      teamLocations[team.team] = {
        ...location,
        city: team.city,
        state: team.state,
        zip: team.zip,
      };
    }
    await delay(CONFIG.RATE_LIMIT_DELAY);
  }

  // Step 2: Geocode event venues
  console.log("\nStep 2: Geocoding event venues...");
  const eventLocations = {};

  for (const event of events) {
    const venueAddress = `${event.venue}, ${event.city}, ${event.state}`;
    const cityAddress = `${event.city}, ${event.state}`;

    console.log(`  Geocoding: ${event.venue} - ${event.city}, ${event.state}`);

    // Try venue first, fall back to city
    let location = await geocodeAddress(venueAddress, CONFIG.BOUNDS);
    if (!location) {
      console.log(`    Falling back to city-level geocoding...`);
      location = await geocodeAddress(cityAddress, CONFIG.BOUNDS);
    }

    if (location) {
      eventLocations[event.event_date] = {
        ...location,
        venue: event.venue,
        city: event.city,
        state: event.state,
        event_id: event.event_id,
      };
    }
    await delay(CONFIG.RATE_LIMIT_DELAY);
  }

  // Step 3: Calculate distances between all team-event pairs
  console.log("\nStep 3: Calculating distances...");
  const distances = {};
  const uniqueLocations = {};

  // First, identify unique venue locations (some events share venues)
  for (const [eventDate, eventLoc] of Object.entries(eventLocations)) {
    const locationKey = `${eventLoc.city}_${eventLoc.state}`;
    if (!uniqueLocations[locationKey]) {
      uniqueLocations[locationKey] = {
        ...eventLoc,
        dates: [eventDate],
      };
    } else {
      uniqueLocations[locationKey].dates.push(eventDate);
    }
  }

  console.log(
    `Found ${Object.keys(uniqueLocations).length} unique venue locations for ${Object.keys(eventLocations).length} events`,
  );

  // Calculate distances for each team to each unique location
  for (const [teamName, teamLoc] of Object.entries(teamLocations)) {
    distances[teamName] = {};

    for (const [locationKey, venueLoc] of Object.entries(uniqueLocations)) {
      console.log(
        `  ${teamName} → ${venueLoc.city} (${venueLoc.dates.length} event(s))`,
      );

      const distanceData = await getDrivingDistance(teamLoc, venueLoc);
      if (distanceData) {
        const distanceInfo = {
          one_way_miles: distanceData.distance_miles,
          one_way_minutes: distanceData.duration_minutes,
          round_trip_miles: distanceData.distance_miles * 2,
          round_trip_minutes: distanceData.duration_minutes * 2,
          distance_text: distanceData.distance_text,
          duration_text: distanceData.duration_text,
        };

        // Apply the same distance to all events at this location
        for (const eventDate of venueLoc.dates) {
          distances[teamName][eventDate] = distanceInfo;
        }
      }
      await delay(CONFIG.RATE_LIMIT_DELAY);
    }
  }

  // Step 4: Combine with attendance data and calculate actual travel
  console.log("\nStep 4: Calculating actual travel based on attendance...");
  const travelData = [];
  const independentData = [];
  const unmatchedAttendance = [];

  for (const record of attendance) {
    const teamName = record.team;
    const attendanceDate = record.race_date_iso;
    const riders = record.riders;

    // Handle Independent riders separately
    if (teamName === "Independent") {
      const matchedEventDate = findMatchingEventDate(
        attendanceDate,
        Object.keys(eventLocations),
      );
      if (matchedEventDate) {
        independentData.push({
          date: attendanceDate,
          event_date: matchedEventDate,
          riders: riders,
          venue: eventLocations[matchedEventDate]?.venue,
          city: eventLocations[matchedEventDate]?.city,
          season: getSeason(attendanceDate),
        });
      }
      continue;
    }

    // Try to find matching event within ±2 days
    const matchedEventDate = findMatchingEventDate(
      attendanceDate,
      Object.keys(eventLocations),
    );

    if (
      matchedEventDate &&
      distances[teamName] &&
      distances[teamName][matchedEventDate]
    ) {
      const dist = distances[teamName][matchedEventDate];
      const vehicles = Math.ceil(riders / CONFIG.RIDERS_PER_VEHICLE);

      travelData.push({
        team: teamName,
        date: attendanceDate, // Keep original attendance date
        event_date: matchedEventDate, // Store matched event date
        riders: riders,
        vehicles: vehicles,
        one_way_miles: dist.one_way_miles,
        round_trip_miles: dist.round_trip_miles,
        total_miles_traveled: dist.round_trip_miles * vehicles,
        one_way_minutes: dist.one_way_minutes,
        round_trip_minutes: dist.round_trip_minutes,
        total_minutes_traveled: dist.round_trip_minutes * vehicles,
        venue: eventLocations[matchedEventDate]?.venue,
        city: eventLocations[matchedEventDate]?.city,
        season: getSeason(attendanceDate),
      });

      if (attendanceDate !== matchedEventDate) {
        console.log(
          `  ℹ Matched attendance ${attendanceDate} → event ${matchedEventDate}`,
        );
      }
    } else {
      unmatchedAttendance.push({
        team: teamName,
        date: attendanceDate,
        riders: riders,
      });
    }
  }

  if (unmatchedAttendance.length > 0) {
    console.log(
      "\n⚠ Warning: Some attendance records could not be matched to events:",
    );
    unmatchedAttendance.forEach((r) => {
      console.log(`  ${r.date}: ${r.team} (${r.riders} riders)`);
    });
  }

  console.log(
    `\nℹ Independent riders tracked at ${independentData.length} events (no travel calculated)`,
  );

  // Step 5: Save all data to JSON
  console.log("\nStep 5: Saving data...");

  const output = {
    metadata: {
      generated_at: new Date().toISOString(),
      riders_per_vehicle: CONFIG.RIDERS_PER_VEHICLE,
      total_teams: Object.keys(teamLocations).length,
      total_events: Object.keys(eventLocations).length,
      total_attendance_records: travelData.length,
      independent_records: independentData.length,
    },
    team_locations: teamLocations,
    event_locations: eventLocations,
    distances: distances,
    travel_data: travelData,
    independent_data: independentData,
  };

  fs.writeFileSync("wscl_distance_data.json", JSON.stringify(output, null, 2));
  console.log("\n✓ Data saved to wscl_distance_data.json");

  // Generate summary statistics
  console.log("\n=== SUMMARY ===");
  console.log(`Teams geocoded: ${Object.keys(teamLocations).length}`);
  console.log(`Events geocoded: ${Object.keys(eventLocations).length}`);
  console.log(`Travel records: ${travelData.length}`);
  console.log(`Independent rider records: ${independentData.length}`);

  const totalMiles = travelData.reduce(
    (sum, r) => sum + r.total_miles_traveled,
    0,
  );
  const totalIndependentRiders = independentData.reduce(
    (sum, r) => sum + r.riders,
    0,
  );
  console.log(`Total miles traveled: ${totalMiles.toFixed(0)} miles`);
  console.log(`Total independent riders: ${totalIndependentRiders}`);
}

// Determine season from date
function getSeason(dateStr) {
  const date = new Date(dateStr);
  const month = date.getMonth() + 1; // 1-12
  const year = date.getFullYear();

  if (month >= 3 && month <= 6) {
    return `Spring ${year}`;
  } else if (month >= 9 && month <= 10) {
    return `Fall ${year}`;
  }
  return `Unknown ${year}`;
}

// Find matching event date within ±2 days
function findMatchingEventDate(attendanceDate, eventDates) {
  const attDate = new Date(attendanceDate);

  // First try exact match
  if (eventDates.includes(attendanceDate)) {
    return attendanceDate;
  }

  // Try within ±2 days
  for (let offset = -2; offset <= 2; offset++) {
    if (offset === 0) continue; // Already tried exact match

    const testDate = new Date(attDate);
    testDate.setDate(testDate.getDate() + offset);
    const testDateStr = testDate.toISOString().split("T")[0];

    if (eventDates.includes(testDateStr)) {
      return testDateStr;
    }
  }

  return null; // No match found
}

// Run the script
calculateAllDistances().catch(console.error);
