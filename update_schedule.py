
#!/usr/bin/env python3
"""Build an Israel Railways timetable index with GTFS diagnostics."""

import csv
import io
import json
import re
import urllib.request
import zipfile
import datetime
import pathlib
from zoneinfo import ZoneInfo

URL = "https://gtfs.mot.gov.il/gtfsfiles/israel-public-transportation.zip"
OUT = pathlib.Path(__file__).resolve().parent / "schedule.json"


def table(z, name):
    with z.open(name) as raw:
        return list(
            csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig")
            )
        )


def train_no(route):
    name = route.get("route_short_name", "").strip()
    match = re.search(r"(?:^|[-/])([0-9]{2,6})$", name)
    if match:
        return match.group(1)
    if re.fullmatch(r"\d{2,6}", name):
        return name
    return None


def main():
    print("Downloading GTFS data...", flush=True)

    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "RailShiftPlanner/1.0"}
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()

    print("Download size:", len(data), "bytes", flush=True)

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        routes = table(z, "routes.txt")
        stops = table(z, "stops.txt")

        railroutes = {
            r["route_id"]: r
            for r in routes
            if r.get("route_type") == "2"
        }

        print("Rail routes:", len(railroutes), flush=True)

        # Diagnose the actual GTFS route structure.
        print("\n=== RAIL ROUTE SAMPLES ===", flush=True)
        for route in list(railroutes.values())[:10]:
            print({
                key: route.get(key)
                for key in (
                    "route_id",
                    "route_short_name",
                    "route_long_name",
                    "route_desc"
                )
            }, flush=True)

        route_numbers = {
            route_id: train_no(route)
            for route_id, route in railroutes.items()
        }
        route_numbers = {
            key: value
            for key, value in route_numbers.items()
            if value
        }

        print(
            "Matched route numbers:",
            len(route_numbers),
            flush=True
        )

        trips = {}

        print("\n=== RAIL TRIP SAMPLES ===", flush=True)
        samples = 0
        rail_trip_count = 0

        for trip in table(z, "trips.txt"):
            route_id = trip.get("route_id")

            if route_id not in railroutes:
                continue

            rail_trip_count += 1

            if samples < 10:
                print({
                    key: trip.get(key)
                    for key in (
                        "route_id",
                        "trip_id",
                        "trip_short_name",
                        "trip_headsign",
                        "service_id"
                    )
                }, flush=True)
                samples += 1

            short = trip.get("trip_short_name", "").strip()

            number = (
                short
                if re.fullmatch(r"\d{2,6}", short)
                else route_numbers.get(route_id)
            )

            if number:
                trips[trip["trip_id"]] = {
                    "number": number,
                    "service": trip["service_id"]
                }

        print("Total rail trips:", rail_trip_count, flush=True)
        print("Matched trips:", len(trips), flush=True)

        stopnames = {
            row["stop_id"]: row.get("stop_name", "")
            for row in stops
        }

        calendars = (
            {
                row["service_id"]: row
                for row in table(z, "calendar.txt")
            }
            if "calendar.txt" in z.namelist()
            else {}
        )

        exceptions = {}

        if "calendar_dates.txt" in z.namelist():
            for row in table(z, "calendar_dates.txt"):
                exceptions.setdefault(
                    row["service_id"], {}
                )[row["date"]] = row["exception_type"]

        today = datetime.datetime.now(
            ZoneInfo("Asia/Jerusalem")
        ).date()

        days = [
            today + datetime.timedelta(days=i)
            for i in range(11)
        ]

        def runs(service, day):
            date = day.strftime("%Y%m%d")

            if date in exceptions.get(service, {}):
                return exceptions[service][date] == "1"

            calendar = calendars.get(service)

            return bool(
                calendar
                and calendar["start_date"] <= date
                and date <= calendar["end_date"]
                and calendar[day.strftime("%A").lower()] == "1"
            )

        active = {
            trip_id: {
                day.isoformat()
                for day in days
                if runs(meta["service"], day)
            }
            for trip_id, meta in trips.items()
        }

        active = {
            trip_id: dates
            for trip_id, dates in active.items()
            if dates
        }

        schedule = {}

        with z.open("stop_times.txt") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig")
            )

            for row in reader:
                trip_id = row.get("trip_id")

                if trip_id not in active:
                    continue

                schedule.setdefault(trip_id, []).append([
                    int(row["stop_sequence"]),
                    stopnames.get(
                        row["stop_id"], row["stop_id"]
                    ),
                    row.get("arrival_time", ""),
                    row.get("departure_time", "")
                ])

        indexed = {}

        for trip_id, stop_list in schedule.items():
            stop_list.sort(key=lambda item: item[0])
            number = trips[trip_id]["number"]

            for day in active[trip_id]:
                indexed.setdefault(day, {}).setdefault(
                    number, []
                ).append({
                    "stops": [
                        item[1:]
                        for item in stop_list
                    ]
                })

        payload = {
            "source": "משרד התחבורה — GTFS ציבורי",
            "updated": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "days": indexed,
            "warning": (
                "נתוני תכנון ציבוריים; ייתכנו פערים "
                "מול RAILAPP."
            )
        }

        OUT.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":")
            ),
            encoding="utf-8"
        )

        print("\n=== RESULTS ===", flush=True)
        print("Output:", OUT, flush=True)
        print("Output bytes:", OUT.stat().st_size, flush=True)
        print("Indexed days:", len(indexed), flush=True)
        print("Active trips:", len(active), flush=True)
        print(
            "Train 651:",
            any("651" in day for day in indexed.values()),
            flush=True
        )
        print(
            "Train 670:",
            any("670" in day for day in indexed.values()),
            flush=True
        )


if __name__ == "__main__":
    main()
