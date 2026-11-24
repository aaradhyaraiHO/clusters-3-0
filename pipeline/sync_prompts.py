"""Copy the EOS prompts from the "KW clusters 3.0 prompts" Google Doc into prompts/eos/, one file per tab.

The doc is the source of truth; the files here are what the pipeline sends. Re-run after the doc changes:
    python sync_prompts.py            # writes prompts/eos/*.md and prompts/eos/manifest.json
    python sync_prompts.py --check    # exits 1 if the doc differs from the files, writes nothing
Needs the gws CLI signed in to a Headout Google account.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DOC_ID = "11zGWxtkUWHOlmbfE2OkowshAXTGNTcrkQNRb1QXEzkg"
OUT = Path(__file__).resolve().parent / "prompts" / "eos"
# Tab title in the doc -> file name. A new tab in the doc fails the sync until it is named here, so a prompt
# never reaches the pipeline under a name no step reads.
TABS = {
    "Vendor seeds": "vendor_seeds.md",
    "Noise filtering": "vendor_noise_filter.md",
    "Seeds": "seeds.md",
    "clusters": "clusters.md",
    "Page mappingg": "page_mapping.md",
    "Separate page": "separate_page.md",
    "Page type": "page_type.md",
}


def fetch_doc():
    result = subprocess.run(
        ["gws", "docs", "documents", "get", "--params", json.dumps({"documentId": DOC_ID, "includeTabsContent": True})],
        capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def body_text(content):
    """Plain text of a tab. The prompts are written as plain paragraphs (no Docs bullets, tables or headings)."""
    parts = []
    for element in content:
        if "paragraph" in element:
            parts.append("".join(run.get("textRun", {}).get("content", "") for run in element["paragraph"]["elements"]))
        elif "table" in element:
            raise ValueError("a prompt tab holds a table; plain-text export would flatten it")
    return "".join(parts)


def all_tabs(tabs):
    for tab in tabs:
        yield tab
        yield from all_tabs(tab.get("childTabs", []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    doc = fetch_doc()
    found, links = {}, {}
    for tab in all_tabs(doc["tabs"]):
        title = tab["tabProperties"]["title"]
        if title not in TABS:
            sys.exit(f"Tab '{title}' is not mapped to a file in TABS")
        lines = body_text(tab["documentTab"]["body"]["content"]).splitlines(keepends=True)
        # The doc heads some tabs with the VectorShift pipeline that runs them; that link is metadata, not prompt.
        links[TABS[title]] = [line.split("-", 1)[1].strip() for line in lines if line.startswith("Pipeline link")]
        found[TABS[title]] = "".join(line for line in lines if not line.startswith("Pipeline link")).strip() + "\n"
    missing = set(TABS.values()) - set(found)
    if missing:
        sys.exit(f"Tabs missing from the doc: {sorted(missing)}")

    changed = [name for name, text in found.items() if not (OUT / name).exists() or (OUT / name).read_text() != text]
    if args.check:
        print("changed: " + ", ".join(changed) if changed else "prompts match the doc")
        sys.exit(1 if changed else 0)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in found.items():
        (OUT / name).write_text(text)
    manifest = {
        "doc_id": DOC_ID,
        "doc_title": doc.get("title"),
        "revision_id": doc.get("revisionId"),
        "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {name: {"sha256": hashlib.sha256(text.encode()).hexdigest()[:12], "vectorshift": links[name]}
                  for name, text in sorted(found.items())},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("written: " + (", ".join(changed) if changed else "no changes"))


if __name__ == "__main__":
    main()
