"""Dawesville Weekend Bot.

Writes a short "how's the weekend looking" briefing for the family group chat:
the weather, what's on around Dawesville/Mandurah, and a rating out of 10.

GitHub runs this every Thursday afternoon (Perth time). It saves the message to
latest.json, and the iPhone Shortcut reads that file at 6:45pm and sends it.

Ways to run it yourself:
    python weekend_bot.py --facts-only   # weather + holiday facts only (free, no key needed)
    python weekend_bot.py --dry-run      # full message, printed but not saved (needs API key)
    python weekend_bot.py                # full message, saved to latest.json (needs API key)
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Settings you might want to change
# ---------------------------------------------------------------------------

MODEL = os.environ.get("BOT_MODEL", "claude-opus-5-5")
MAX_MESSAGE_CHARS = 520          # longer than this = too long for a group chat, so try again
MAX_WEB_SEARCHES = 10            # caps the cost of each run
MAX_PAGE_OPENS = 4               # event-listing pages Claude may open and read

LATITUDE, LONGITUDE = -32.632, 115.629   # Dawesville, WA
PERTH = timezone(timedelta(hours=8))     # Perth has no daylight saving, so this is always right

HERE = Path(__file__).parent
LATEST_FILE = HERE / "latest.json"
HISTORY_FILE = HERE / "history.jsonl"

# WA public holidays (source: wa.gov.au). Add the next years before the end of 2027.
WA_PUBLIC_HOLIDAYS = {
    "2026-01-01": "New Year's Day", "2026-01-26": "Australia Day", "2026-03-02": "Labour Day",
    "2026-04-03": "Good Friday", "2026-04-05": "Easter Sunday", "2026-04-06": "Easter Monday",
    "2026-04-25": "Anzac Day", "2026-04-27": "Anzac Day (extra day)", "2026-06-01": "WA Day",
    "2026-09-28": "King's Birthday", "2026-12-25": "Christmas Day", "2026-12-26": "Boxing Day",
    "2026-12-28": "Boxing Day (extra day)",
    "2027-01-01": "New Year's Day", "2027-01-26": "Australia Day", "2027-03-01": "Labour Day",
    "2027-03-26": "Good Friday", "2027-03-28": "Easter Sunday", "2027-03-29": "Easter Monday",
    "2027-04-25": "Anzac Day", "2027-04-26": "Anzac Day (extra day)", "2027-06-07": "WA Day",
    "2027-09-27": "King's Birthday", "2027-12-25": "Christmas Day", "2027-12-26": "Boxing Day",
    "2027-12-27": "Christmas Day (extra day)", "2027-12-28": "Boxing Day (extra day)",
}

# WA public school holidays, first and last day (source: education.wa.edu.au).
WA_SCHOOL_HOLIDAYS = [
    ("2025-12-19", "2026-02-01"), ("2026-04-03", "2026-04-19"), ("2026-07-04", "2026-07-19"),
    ("2026-09-26", "2026-10-11"), ("2026-12-18", "2027-01-31"), ("2027-04-10", "2027-04-25"),
    ("2027-07-03", "2027-07-18"), ("2027-09-25", "2027-10-10"), ("2027-12-17", "2028-01-31"),
]
CALENDAR_KNOWN_UNTIL = date(2027, 12, 31)

# Open-Meteo weather codes -> plain words
WEATHER_WORDS = {
    0: "clear skies", 1: "mostly sunny", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 80: "light showers", 81: "showers",
    82: "heavy showers", 95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


# ---------------------------------------------------------------------------
# Step 1: work out which days count as "the weekend"
# ---------------------------------------------------------------------------

def weekend_days(today: date) -> list[date]:
    """The coming Fri, Sat, Sun, plus Monday if it's a public holiday (long weekend)."""
    friday = today + timedelta(days=(4 - today.weekday()) % 7)
    days = [friday, friday + timedelta(days=1), friday + timedelta(days=2)]
    monday = friday + timedelta(days=3)
    if monday.isoformat() in WA_PUBLIC_HOLIDAYS:
        days.append(monday)
    return days


def calendar_facts(days: list[date]) -> str:
    if days[-1] > CALENDAR_KNOWN_UNTIL:
        return ("Holiday calendar not loaded for these dates - check yourself whether this is a "
                "WA long weekend or WA school holidays.")
    lines = []
    holidays = [f"{WA_PUBLIC_HOLIDAYS[d.isoformat()]} ({d:%A})" for d in days
                if d.isoformat() in WA_PUBLIC_HOLIDAYS]
    if holidays:
        lines.append("WA public holiday(s) this weekend: " + ", ".join(holidays)
                     + ". It's a LONG WEEKEND.")
    else:
        lines.append("Not a long weekend (no WA public holidays Fri-Mon).")
    in_school_hols = any(start <= d.isoformat() <= end
                         for d in days for start, end in WA_SCHOOL_HOLIDAYS)
    lines.append("WA school holidays: YES, kids are off school." if in_school_hols
                 else "WA school holidays: no, it's school term.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 2: get the weather forecast (Open-Meteo, free, no key)
# ---------------------------------------------------------------------------

def weather_facts(days: list[date]) -> str:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
        "precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,uv_index_max"
        f"&timezone=Australia%2FPerth&start_date={days[0]}&end_date={days[-1]}"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            daily = json.load(resp)["daily"]
    except Exception as exc:  # the bot can still look the weather up itself
        print(f"WARNING: weather download failed ({exc})", file=sys.stderr)
        return ("Forecast download failed - search for the BOM forecast for Mandurah "
                "for these days instead.")

    lines = []
    for i, day in enumerate(daily["time"]):
        code = daily["weather_code"][i]
        wind_dir = COMPASS[round(daily["wind_direction_10m_dominant"][i] / 22.5) % 16]
        lines.append(
            f"{date.fromisoformat(day):%A %d %b}: {WEATHER_WORDS.get(code, f'weather code {code}')}, "
            f"{daily['temperature_2m_min'][i]:.0f}-{daily['temperature_2m_max'][i]:.0f}C, "
            f"rain chance {daily['precipitation_probability_max'][i]}% "
            f"({daily['precipitation_sum'][i]:.1f}mm), "
            f"wind up to {daily['wind_speed_10m_max'][i]:.0f}km/h {wind_dir}, "
            f"UV {daily['uv_index_max'][i]:.0f}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 3: ask Claude to find what's on and write the message
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You write the weekly "Dawesville weekend report" text for a family group chat in \
Dawesville, Western Australia (just south of Mandurah, in the Peel region). It goes out on \
Thursday evening.

Your job:
1. Research properly before writing - run several searches, and open event-listing pages where \
useful. Cover all of these for the weekend dates given, in Dawesville and nearby (Mandurah, \
Halls Head, Falcon, Pinjarra, the Peel region):
   - events and festivals: check the Visit Mandurah (visitmandurah.com) and City of Mandurah \
(mandurah.wa.gov.au) what's-on listings for these dates
   - markets: the Saturday Peel Produce Market at Dawesville Foreshore, Mandurah's Sunday markets
   - shows at the Mandurah Performing Arts Centre
   - local sport (e.g. Peel Thunder) and big sport the family would care about \
(AFL/Eagles/Dockers, NRL, cricket, Perth Scorchers, Wildcats, etc.)
   - seasonal things (crabbing and fishing rules, whale watching, beach conditions), if you've \
checked them
2. Pick the one to three things most worth knowing. Only mention events you have confirmed are on \
these exact dates. Never make things up; if it's genuinely a quiet weekend, say so.
3. Rate the weekend out of 10. Weather matters most (warm, sunny, light winds = high; rain, \
storms, howling wind = low). A long weekend, school holidays or a great event bump it up. Use \
the whole scale honestly - don't default to 7.

Style: a polished weekend briefing, like a local radio presenter - clear, well-written and a \
little formal, with one light touch of dry humour (family-friendly). Exactly three sentences: \
the weather, what's on, and a closing remark or suggestion. Then the rating line. No slang \
overload, no hashtags, no links, no sources, at most one emoji. Keep the whole thing under 450 \
characters. Use the forecast numbers you're given, not ones from search results.

Finish your reply with the final message inside <message></message> tags, with the rating as \
the last line in the form "Dawesville weekend: 7/10". Nothing after the closing tag."""


def build_request(today: date, days: list[date], weather: str, calendar: str) -> str:
    return (
        f"Today is {today:%A %d %B %Y}. The weekend is "
        f"{days[0]:%A %d %B} to {days[-1]:%A %d %B %Y}.\n\n"
        f"Forecast for Dawesville:\n{weather}\n\n"
        f"Calendar:\n{calendar}\n\n"
        "Find what's on and write this week's message."
    )


def ask_claude(request_text: str) -> str:
    """Runs one Claude request (with web search) and returns all the text it wrote."""
    import anthropic  # imported here so --facts-only works without it installed

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    tools = [{
        "type": "web_search_20260209",
        "name": "web_search",
        "max_uses": MAX_WEB_SEARCHES,
        "user_location": {"type": "approximate", "city": "Mandurah", "region": "Western Australia",
                          "country": "AU", "timezone": "Australia/Perth"},
    }, {
        "type": "web_fetch_20260209",
        "name": "web_fetch",
        "max_uses": MAX_PAGE_OPENS,
        "max_content_tokens": 15000,  # stops one huge page from blowing up the cost
    }]
    messages = [{"role": "user", "content": request_text}]
    text_parts = []

    for _ in range(5):  # a long search can "pause"; resume it up to a few times
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
            output_config={"effort": "high"},  # more thorough event research than "medium"
            # If Claude declines for safety reasons, the API retries on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        text_parts += [block.text for block in response.content if block.type == "text"]
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined the request: {response.stop_details}")
        if response.stop_reason != "pause_turn":
            u = response.usage
            print(f"(tokens in/out: {u.input_tokens}/{u.output_tokens}, "
                  f"stop: {response.stop_reason})", file=sys.stderr)
            return "".join(text_parts)
        messages.append({"role": "assistant", "content": response.content})

    raise RuntimeError("Claude kept pausing and never finished.")


def extract_message(raw_text: str) -> tuple[str, float]:
    """Pulls the final message out of Claude's reply and checks it looks right."""
    found = re.findall(r"<message>(.*?)</message>", raw_text, flags=re.DOTALL)
    if not found:
        raise ValueError("no <message> tags in the reply")
    lines = [" ".join(line.split()) for line in found[-1].strip().splitlines()]
    message = "\n".join(line for line in lines if line)
    rating = re.search(r"(\d{1,2}(?:\.\d)?)\s*/\s*10", message)
    if not rating or not 0 <= float(rating.group(1)) <= 10:
        raise ValueError("no rating out of 10")
    if len(message) > MAX_MESSAGE_CHARS:
        raise ValueError(f"message too long ({len(message)} characters)")
    return message, float(rating.group(1))


def write_message(request_text: str) -> tuple[str, float]:
    last_error = None
    for attempt in range(1, 3):
        raw = ask_claude(request_text)
        try:
            return extract_message(raw)
        except ValueError as exc:
            last_error = exc
            print(f"Attempt {attempt} unusable ({exc}). Reply was:\n{raw}\n", file=sys.stderr)
    raise RuntimeError(f"Couldn't get a usable message: {last_error}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--facts-only", action="store_true",
                        help="print the weather and holiday facts, skip Claude (free)")
    parser.add_argument("--dry-run", action="store_true",
                        help="write the message but don't save it")
    parser.add_argument("--force", action="store_true",
                        help="write a new message even if today's is already saved")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # so emojis print on Windows too

    now = datetime.now(PERTH)
    today = now.date()

    if not (args.force or args.dry_run or args.facts_only) and LATEST_FILE.exists():
        if json.loads(LATEST_FILE.read_text(encoding="utf-8")).get("for_date") == today.isoformat():
            print("Today's message is already saved - nothing to do.")
            return

    days = weekend_days(today)
    request_text = build_request(today, days, weather_facts(days), calendar_facts(days))
    print(request_text, end="\n\n")
    if args.facts_only:
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY isn't set - see README step 2.")

    message, rating = write_message(request_text)
    print("=" * 60 + f"\n{message}\n" + "=" * 60)
    if args.dry_run:
        return

    record = {
        "for_date": today.isoformat(),  # the Shortcut only sends if this is today's date
        "message": message,
        "rating": rating,
        "generated_at": now.isoformat(timespec="seconds"),
        "model": MODEL,
    }
    LATEST_FILE.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Saved to {LATEST_FILE.name}")


if __name__ == "__main__":
    main()
