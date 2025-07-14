#!/usr/bin/env python3
"""
build_calendar.py ― Convert the UCI-Derm didactics Excel workbook into
an HTML calendar that matches your exams.html site layout.

Key features
------------
✓ Displays all sessions from the 1st of the current month
  through the *same day next month* (e.g., run on 13 Jul 2025 → 1 Jul – 13 Aug 2025).
✓ Date bar shows IN-PERSON / VIRTUAL badge **only when at least one
  session that day has a listed lecturer**.
✓ Topic cell keeps its Excel background colour; Time and Lecturer stay white.
✓ Break / holiday rows collapse into a single centred cell.
✓ Output page includes the same sidebar, fonts, and basic styling
  as your exams.html template.
Usage
-----
$ python build_calendar.py "Didactics _ UCI Derm 2017-Present (2).xlsx"  didactics_calendar.html
Requires: pip install openpyxl
"""

import argparse, calendar, datetime as dt, html, re, sys
from pathlib import Path

import openpyxl


# ────────────────────────── helpers ──────────────────────────────────────────
def format_time(val) -> str:
    """Return clean '8–9 AM' style strings, coping with Excel quirks."""
    if val is None:
        return ""
    if isinstance(val, str):
        s = re.sub(r"\s*[-–]\s*", "–", val.strip())
        if not re.search(r"\b(?:am|pm)\b", s, flags=re.I):
            s += " AM"
        return s
    if isinstance(val, (dt.datetime, dt.date)):            # mis-parsed “8-9” date
        return f"{val.month}–{val.day} AM"
    if isinstance(val, (float, int)):                      # Excel serial time
        return f"{int(round(val * 24))} AM"
    return str(val)


def cell_hex(cell) -> str | None:
    """Return '#RRGGBB' from a cell’s fill, or None if uncoloured/white/black."""
    rgb = getattr(cell.fill.start_color, "rgb", None)
    if rgb and rgb[-6:].lower() not in ("ffffff", "000000"):
        return f"#{rgb[-6:]}"
    return None


def badge_class(setting: str) -> str:
    return "virtual" if setting.strip().lower().startswith("v") else "in-person"


def next_month_same_day(date: dt.date) -> dt.date:
    """Return the same day next month (or last valid day if that month is shorter)."""
    year = date.year + (date.month // 12)
    month = (date.month % 12) + 1
    last_day = calendar.monthrange(year, month)[1]
    return dt.date(year, month, min(date.day, last_day))


# ────────────────────────── workbook loader ─────────────────────────────────
def load_events(xlsx_path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[wb.sheetnames[0]]  # first sheet = current academic year

    events = []
    for row in ws.iter_rows(min_row=2, values_only=False):
        d_cell, t_cell, subj_cell, lect_cell, set_cell = row[:5]

        if not isinstance(d_cell.value, (dt.datetime, dt.date)):
            continue  # skip header/spacer rows

        date = d_cell.value.date() if isinstance(d_cell.value, dt.datetime) else d_cell.value
        events.append(
            {
                "date": date,
                "time": format_time(t_cell.value),
                "subject": (subj_cell.value or "").strip(),
                "lecturer": (lect_cell.value or "").strip(),
                "setting": (set_cell.value or "").strip(),
                "row_hex": cell_hex(subj_cell),
            }
        )
    return events


# ────────────────────────── renderer ────────────────────────────────────────
TEMPLATE_HEAD = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8" /><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Didactics Calendar – UCI Dermatology</title>
<style>
body{font-family:Arial,Helvetica,sans-serif;margin:0;display:flex}
nav{width:200px;background:#f7f7f7;padding:20px;box-shadow:2px 0 5px rgba(0,0,0,.1)}
nav img{max-width:100%;border-radius:4px;margin-bottom:1rem}
nav a{display:block;margin-bottom:1rem;text-decoration:none;color:#036;font-weight:bold}
main{flex:1;padding:20px}
h1{margin-top:0;font-size:20px}
table{width:100%;border-collapse:collapse;margin-bottom:1rem}
td{border:1px solid #ccc;padding:4px 6px;font-size:.9rem}
.date-bar{background:#333;color:#fff;padding:6px 10px;font-weight:bold;
          display:inline-block;margin-bottom:.3rem;border-radius:4px}
.status{margin-left:8px;padding:2px 6px;border-radius:4px;font-size:.75rem}
.in-person{background:#32cd32}.virtual{background:#1e90ff}
.break-row{font-style:italic;text-align:center;background:#f4f4f4}
</style></head><body>
<nav><img src="https://sidharthchand.github.io/uci-pages/anteaterzotzot.jpeg" alt="Anteater"/>
<a href="index.html">Home</a></nav><main><h1>Didactics Calendar</h1>"""

TEMPLATE_FOOT = "</main></body></html>"


def render(events: list[dict], outfile: Path) -> None:
    out = [TEMPLATE_HEAD]
    current_date = None

    for i, ev in enumerate(events):
        if ev["date"] != current_date:                         # new date section
            current_date = ev["date"]
            pretty = current_date.strftime("%A, %B %-d %Y")

            # Badge only if at least one session with lecturer on that day
            same_day_events = [e for e in events if e["date"] == current_date]
            has_lecturer = any(e["lecturer"] for e in same_day_events)
            if has_lecturer:
                badge = badge_class(same_day_events[0]["setting"])
                badge_txt = "VIRTUAL" if badge == "virtual" else "IN PERSON"
                out.append(
                    f'<span class="date-bar">{pretty}'
                    f'<span class="status {badge}">{badge_txt}</span></span>'
                )
            else:
                out.append(f'<span class="date-bar">{pretty}</span>')

            out.append("<table>")

        # Row creation
        subj_style = f' style="background:{ev["row_hex"]};"' if ev["row_hex"] else ""
        if not ev["lecturer"]:                                 # break/holiday row
            out.append(
                f'<tr><td class="break-row" colspan="3"{subj_style}>'
                f'{html.escape(ev["subject"])}</td></tr>'
            )
        else:                                                  # normal session row
            out.append(
                f'<tr><td>{html.escape(ev["time"])}</td>'
                f'<td{subj_style}>{html.escape(ev["subject"])}</td>'
                f'<td>{html.escape(ev["lecturer"])}</td></tr>'
            )

        # Close table when next event is a different date
        nxt_date = events[i + 1]["date"] if i + 1 < len(events) else None
        if nxt_date != current_date:
            out.append("</table>")

    out.append(TEMPLATE_FOOT)
    outfile.write_text("\n".join(out), encoding="utf-8")
    print(f"✓ Wrote {outfile}")


# ────────────────────────── CLI ──────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Excel → styled didactics calendar")
    ap.add_argument("excel", help="Path to didactics workbook (.xlsx)")
    ap.add_argument(
        "output_html", nargs="?", default="didactics_calendar.html",
        help="Filename for generated HTML (default: didactics_calendar.html)",
    )
    args = ap.parse_args()

    events = load_events(Path(args.excel))

    today = dt.date.today()
    month_start = today.replace(day=1)            # always start at 1st of this month
    month_end   = next_month_same_day(today)      # same day next month (inclusive)

    events = [e for e in events if month_start <= e["date"] <= month_end]
    if not events:
        sys.exit("No events found in this 1-month window.")

    # Sort by date then by (approx) starting hour extracted from time string
    def sort_key(e):
        m = re.match(r"(\d+)", e["time"])
        hour = int(m.group(1)) if m else 0
        return (e["date"], hour)

    events.sort(key=sort_key)
    render(events, Path(args.output_html))


if __name__ == "__main__":
    main()
