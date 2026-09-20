"""
Shared schedule-data helpers, used by both morning_brief.py (CLI) and
dashboard.py (chat UI) so the logic lives in one place.
"""

import json
import os
from datetime import datetime, timedelta

SCHEDULE_DIR = os.path.join(os.path.dirname(__file__), "schedule")
PROJECTS_FILE = os.path.join(SCHEDULE_DIR, "projects.json")
LOOKAHEAD_DAYS = 7

TYPE_LABEL = {
    "exam": "EXAM",
    "deadline": "DEADLINE",
    "holiday": "No class (holiday)",
    "event": "Event",
    "class": "Class",
}


def load_weekly_schedule():
    with open(os.path.join(SCHEDULE_DIR, "weekly_schedule.json"), encoding="utf-8") as f:
        return json.load(f)


def load_course_events(schedule_file):
    if not schedule_file:
        return None
    path = os.path.join(SCHEDULE_DIR, schedule_file)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def events_on(course_data, date_str):
    if not course_data:
        return []
    return [e for e in course_data["events"] if e["date"] == date_str]


def events_between(course_data, start_date, end_date):
    if not course_data:
        return []
    return [
        e for e in course_data["events"]
        if start_date < datetime.strptime(e["date"], "%Y-%m-%d") <= end_date
    ]


def format_event(event):
    label = TYPE_LABEL.get(event["type"], event["type"])
    line = f"[{label}] {event['topic']}"
    if event.get("time"):
        line += f" @ {event['time']}"
    if event.get("deadline"):
        line += f" -> {event['deadline']}"
    return line


def get_today_brief(today=None):
    """Plain-text summary of today's classes and anything due today."""
    today = today or datetime.now()
    weekly = load_weekly_schedule()
    weekday = today.strftime("%a")
    date_str = today.strftime("%Y-%m-%d")
    lines = [today.strftime("%A, %B %d, %Y")]

    todays_classes = [c for c in weekly["classes"] if c.get("days") and weekday in c["days"]]
    online_only = [c for c in weekly["classes"] if not c.get("days")]

    if not todays_classes:
        lines.append("No in-person classes today.")
    for course in todays_classes:
        course_data = load_course_events(course.get("schedule_file"))
        todays_events = events_on(course_data, date_str)
        header = course["course"]
        if course.get("time"):
            header += f" ({course['time']})"
        lines.append(header)
        if todays_events:
            for e in todays_events:
                lines.append("  " + format_event(e))
        else:
            lines.append("  Regular class, no specific topic on file for this date.")

    for course in online_only:
        course_data = load_course_events(course.get("schedule_file"))
        todays_events = events_on(course_data, date_str)
        if todays_events:
            lines.append(f"{course['course']} (online):")
            for e in todays_events:
                lines.append("  " + format_event(e))

    return "\n".join(lines)


def get_week_ahead_brief(today=None):
    """Plain-text summary of exams/deadlines/holidays in the next 7 days."""
    today = today or datetime.now()
    end = today + timedelta(days=LOOKAHEAD_DAYS)
    weekly = load_weekly_schedule()
    lines = []

    for course in weekly["classes"]:
        course_data = load_course_events(course.get("schedule_file"))
        upcoming = events_between(course_data, today, end)
        notable = [
            e for e in upcoming
            if e["type"] in ("exam", "deadline", "holiday", "event") or e.get("deadline")
        ]
        if notable:
            lines.append(f"{course['course']}:")
            for e in notable:
                weekday = datetime.strptime(e["date"], "%Y-%m-%d").strftime("%a %m/%d")
                lines.append(f"  {weekday} - {format_event(e)}")

    if not lines:
        return "Nothing exam/deadline-worthy in the next 7 days."
    return "\n".join(lines)


def load_projects():
    if not os.path.exists(PROJECTS_FILE):
        return {"projects": []}
    with open(PROJECTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_projects(data):
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def toggle_project_item(project_id, item_id):
    """Flip an item's done state and persist it. Returns the new state."""
    data = load_projects()
    for project in data["projects"]:
        if project["id"] == project_id:
            for item in project["items"]:
                if item["id"] == item_id:
                    item["done"] = not item["done"]
                    save_projects(data)
                    return item["done"]
    raise KeyError(f"No item {item_id} in project {project_id}")


def get_projects_brief():
    """Plain-text summary of project checklists and their completion."""
    data = load_projects()
    if not data["projects"]:
        return "No multi-part projects tracked."
    lines = []
    for p in data["projects"]:
        done = sum(1 for i in p["items"] if i["done"])
        total = len(p["items"])
        lines.append(f"{p['name']} ({p['course']}) - due {p['due']} - {done}/{total} checklist items done")
        for i in p["items"]:
            mark = "x" if i["done"] else " "
            lines.append(f"  [{mark}] {i['label']}")
    return "\n".join(lines)
