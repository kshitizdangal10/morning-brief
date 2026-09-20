"""
Daily Alert
-----------
Checks for exams/deadlines in the next few days and pops a Windows
notification if there's anything worth flagging - so you get a heads-up
even on days you don't open the dashboard. Meant to run once a day via
Task Scheduler (see CLAUDE.md for the setup command); safe to run by hand
too.

Setup:
    pip install -r requirements-windows.txt   # win11toast is Windows-only,
                                               # kept out of requirements.txt
                                               # so cloud deployment doesn't
                                               # try to install it on Linux
    python daily_alert.py             # test it manually
"""

from datetime import datetime, timedelta

from win11toast import toast

import brief_data

LOOKAHEAD_DAYS = 3
MAX_ITEMS_SHOWN = 5


def urgent_items():
    today = datetime.now()
    start = today - timedelta(days=1)  # events_between excludes start_date itself
    end = today + timedelta(days=LOOKAHEAD_DAYS)
    weekly = brief_data.load_weekly_schedule()

    items = []
    for course in weekly["classes"]:
        course_data = brief_data.load_course_events(course.get("schedule_file"))
        for e in brief_data.events_between(course_data, start, end):
            if e["type"] in ("exam", "deadline") or e.get("deadline"):
                items.append(f"{course['course']}: {e['topic']}")
    return items


def main():
    items = urgent_items()
    if not items:
        return

    body = "\n".join(items[:MAX_ITEMS_SHOWN])
    if len(items) > MAX_ITEMS_SHOWN:
        body += f"\n...and {len(items) - MAX_ITEMS_SHOWN} more"

    toast(f"Morning Brief - {LOOKAHEAD_DAYS} days ahead", body, duration="long")


if __name__ == "__main__":
    main()
