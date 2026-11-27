"""The date window every pull of the tool uses, in one place.

  CLUSTERS_WINDOW unset        the fixed window every CE in the tool was pulled with (30 Jul – 27 Oct 2026)
  CLUSTERS_WINDOW=rolling      the latest 90 days whose Google Ads data has settled (ending two days ago)
  CLUSTERS_WINDOW=2026-08-01:2026-10-29   any other window, start and end inclusive

Switch every CE at once: a CE pulled on another window than the rest shows numbers that do not compare. The
pipeline's own search-term pull (run_ce_pipeline.py) already reads the latest 90 days.

The SQL templates use the tokens below instead of dates. Their offsets are the ones the fixed window was written
with: Google Ads entity tables are read at the partition the day after the window ends, the gclid lookup starts six
days before it, weekly search terms run in whole Monday weeks, and the page ranking snapshot is the week after it.
"""
import os
from datetime import date, timedelta

FIXED = ("2026-07-30", "2026-10-27")
DAYS = 90


def window():
    v = os.environ.get("CLUSTERS_WINDOW", "").strip()
    if v == "rolling":
        end = date.today() - timedelta(days=2)
        return (end - timedelta(days=DAYS - 1)).isoformat(), end.isoformat()
    if ":" in v:
        start, end = v.split(":", 1)
        return start, end
    return FIXED


def tokens(start=None, end=None):
    start, end = (start, end) if start else window()
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    d = lambda x: x.isoformat()
    return {"__START__": d(s), "__END__": d(e), "__END_1__": d(e + timedelta(days=1)), "__END_2__": d(e + timedelta(days=2)),
            "__START_M1__": d(s - timedelta(days=1)), "__START_M6__": d(s - timedelta(days=6)), "__END_M1__": d(e - timedelta(days=1)),
            # Weekly search terms run in whole Monday weeks; the page ranking snapshot is the week after the window.
            "__WEEK_START__": d(s - timedelta(days=s.weekday())), "__WEEK_END__": d(e - timedelta(days=e.weekday())),
            "__END_7__": d(e + timedelta(days=7))}


def label(start, end):
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    return f"{s:%-d %b} – {e:%-d %b %Y}"
