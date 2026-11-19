"""Inline one CE's data into template.html.

  python3 build.py [slug]              e.g. vatican (default), milford, parkguell: the CE's folder -> its page, per ces.json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = json.loads((HERE / "ces.json").read_text())["ces"]
slug = sys.argv[1] if len(sys.argv) > 1 else "vatican"
ce, cfg = next((k, v) for k, v in REG.items() if v["slug"] == slug)
folder, data, unclustered, out, title = cfg["out"], cfg["data"], f"unclustered_groups_{ce}.json", cfg["page"], cfg["title"]


def payload(name):
    return (HERE / folder / name).read_text().replace("</", "<\\/")


page = (HERE / "template.html").read_text().replace("<title>Vatican Clusters</title>", f"<title>{title}</title>", 1)
page = page.replace("__DATA__", payload(data), 1).replace("__IS__", payload("impression_share.json"), 1)
page = page.replace("__DRAWER__", payload("drawer.json"), 1)
page = page.replace("__UNC__", payload(unclustered), 1)
page = page.replace("__FACTS__", payload("page_facts.json"), 1)
# Every CE's page, for the header's CE switcher; the pages sit side by side, on localhost and on the deployed site.
ces = [{"id": k, "name": v["name"], "page": v["page"]} for k, v in REG.items() if (HERE / v["out"] / v["data"]).exists()]
page = page.replace("__CES__", json.dumps(ces, ensure_ascii=False).replace("</", "<\\/"), 1)
(HERE / out).write_text(page)
print(f"wrote {HERE / out}")
