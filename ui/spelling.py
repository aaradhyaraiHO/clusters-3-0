"""Misspellings of a CE's own name in its keywords ("millford sound", "mild ford sound", "milord sound").

A misspelt keyword is never a cluster's focus keyword, and it belongs to the cluster that holds the right spelling: the
clustering prompt otherwise groups them into a cluster of their own ("Milford Sound Cruise" held eight spellings of
"milford sound"). Only the CE's place words count as misspellable; the rest of a CE's vocabulary holds real names (Khao
Phing Kan, the Phi Phi Sand Sea resort) that sit close to other words.
"""
import re
import unicodedata
from pathlib import Path

DICT_FILE = Path("/usr/share/dict/words")
DICT = {w.strip().lower() for w in DICT_FILE.open()} if DICT_FILE.exists() else set()
# Words in a CE's name that say what is sold, not where: "Milford Sound Cruises" is misspelt only as a place.
PRODUCT = {"cruise", "cruises", "tour", "tours", "ticket", "tickets", "trip", "trips", "day", "the", "and", "from", "to", "of",
           "experience", "experiences"}

fold = lambda t: unicodedata.normalize("NFKD", str(t).lower()).encode("ascii", "ignore").decode()
plain = lambda t: [w for w in re.split(r"[^a-z0-9]+", fold(t)) if len(w) > 1]


def lev(a, b, cap=3):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def speller(ce_name, volumes):
    """volumes: {keyword: Keyword Planner volume} for the CE. Returns fix(keyword, volume) -> the keyword spelled right,
    or None when it does not misspell the CE's name."""
    core = [w for w in plain(ce_name) if len(w) > 2 and w not in PRODUCT]
    cat = "".join(core)

    def fix(keyword, vol=None):
        ws = plain(keyword)
        # The name misspelt across word breaks too: "mild ford sound", "milfordsound".
        for n in (3, 2, 1):
            for i in range(len(ws) - n + 1):
                win = ws[i:i + n]
                if set(core) <= set(win):
                    continue
                joined = "".join(win)
                if len(cat) >= 8 and lev(joined, cat) <= 2 and joined.rstrip("s") != cat.rstrip("s"):
                    fixed = " ".join(ws[:i] + core + ws[i + n:])
                    # Real words ("milord", "mild ford") count only when Keyword Planner gives the right spelling the same
                    # volume: it pools a misspelling's searches with the word it misspells.
                    if any(w not in DICT and w not in core for w in win) or (vol is not None and volumes.get(fixed) == vol):
                        return fixed
        out = [next((c for c in core if len(c) >= 5 and w not in DICT and lev(w, c) <= (1 if len(c) < 7 else 2)
                     and w.rstrip("s") != c.rstrip("s")), w) for w in ws]
        return " ".join(out) if out != ws else None

    return fix
