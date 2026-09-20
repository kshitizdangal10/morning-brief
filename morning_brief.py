"""
Morning Brief
-------------
Reads the class schedule data in schedule/ and prints what's happening
today and this week. This is the schedule piece of the bigger morning-brief
toolkit (gmail_agent.py for email, news_agent.py for science/tech news) -
see dashboard.py for a chat UI over all three instead of running each by
hand. Schedule-loading logic lives in brief_data.py, shared with dashboard.py.

Usage:
    python morning_brief.py                  # uses today's date
    python morning_brief.py --date 2026-09-20  # simulate a specific date (for demos/testing)
"""

import argparse
from datetime import datetime, timedelta

from brief_data import (
    load_weekly_schedule,
    load_course_events,
    events_on,
    events_between,
    format_event as _format_event,
    LOOKAHEAD_DAYS,
)


def format_event(event):
    # CLI wants extra indentation vs. the plain-text version in brief_data.
    line = "    " + _format_event(event)
    return line.replace(" -> ", "\n        -> ")


def print_today(today, weekly):
    weekday = today.strftime("%a")
    print(f"Good morning, {weekly['student'].split()[0]} - {today.strftime('%A, %B %d, %Y')}")
    print("=" * 60)
    print("\nTODAY'S CLASSES\n" + "-" * 60)

    todays_classes = [c for c in weekly["classes"] if c.get("days") and weekday in c["days"]]

    if not todays_classes:
        print("  No classes today (all 4 in-person courses meet Tue/Thu).")
    else:
        date_str = today.strftime("%Y-%m-%d")
        for course in todays_classes:
            course_data = load_course_events(course.get("schedule_file"))
            todays_events = events_on(course_data, date_str)
            header = f"  {course['course']}"
            if course.get("time"):
                header += f" - {course['time']}"
            if course.get("location"):
                header += f" ({course['location']})"
            print(header)
            if todays_events:
                for e in todays_events:
                    print(format_event(e))
            else:
                print("    [Class] (no specific topic on file for this date)")
            print()

    date_str = today.strftime("%Y-%m-%d")
    online_only = [c for c in weekly["classes"] if not c.get("days")]
    for course in online_only:
        course_data = load_course_events(course.get("schedule_file"))
        todays_events = events_on(course_data, date_str)
        print(f"  {course['course']} (online, asynchronous)")
        if todays_events:
            for e in todays_events:
                print(format_event(e))
        else:
            print("    Nothing due today.")
        print()


def print_week_ahead(today, weekly):
    end = today + timedelta(days=LOOKAHEAD_DAYS)
    print(f"THIS WEEK AHEAD ({today.strftime('%b %d')} - {end.strftime('%b %d')})\n" + "-" * 60)

    found_any = False
    for course in weekly["classes"]:
        course_data = load_course_events(course.get("schedule_file"))
        upcoming = events_between(course_data, today, end)
        notable = [
            e for e in upcoming
            if e["type"] in ("exam", "deadline", "holiday", "event") or e.get("deadline")
        ]
        if notable:
            found_any = True
            print(f"  {course['course']}:")
            for e in notable:
                weekday = datetime.strptime(e["date"], "%Y-%m-%d").strftime("%a %m/%d")
                print(f"    {weekday} - {format_event(e).strip()}")
            print()

    if not found_any:
        print("  Nothing exam/deadline-worthy in the next week.\n")


def print_other_sections():
    print("EMAIL SUMMARY\n" + "-" * 60)
    print("  Run separately: python gmail_agent.py")
    print("  Summarizes unread Gmail and drafts replies (draft-only - you")
    print("  review and send yourself) for the ones that need one.\n")

    print("SCIENCE & TECH NEWS\n" + "-" * 60)
    print("  Run separately: python news_agent.py")
    print("  Pulls headlines from curated RSS feeds (Ars Technica, MIT Tech")
    print("  Review, Nature, Wired, Hacker News) and picks out the stories")
    print("  actually worth knowing about.\n")


def main():
    parser = argparse.ArgumentParser(description="Print the morning brief.")
    parser.add_argument("--date", help="Simulate a specific date (YYYY-MM-DD) instead of today.")
    args = parser.parse_args()

    today = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()
    weekly = load_weekly_schedule()

    print_today(today, weekly)
    print()
    print_week_ahead(today, weekly)
    print()
    print_other_sections()


if __name__ == "__main__":
    main()
