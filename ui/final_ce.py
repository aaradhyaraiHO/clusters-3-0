"""Point one CE's page at the clustering pipeline's output (run_ce_pipeline.py), in place of map_ce.py.

  python3 final_ce.py <clusters_3_0> 1695 [--prompt patched]

Reads <clusters_3_0>/snapshots/ce_<CE>[_patched]/final/: clusters.csv, keywords.csv, paid.csv and organic.csv. Writes what
prepare_ce.py and export_hybrid.py already read: a pipeline_local snapshot (the Google Ads and Search Console rows from the
30 Oct validation snapshot, as map_ce.py copies them, with the pipeline's clusters as cluster_keywords.csv) and three
"runs" whose assignments carry the pipeline's placements. ces.json then names that snapshot and those runs.

Cluster ids are derived from the CE and the cluster name, so a re-run that keeps a cluster's name keeps its id, and the
decisions saved against it in the browser.
"""
import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
LOCAL = HERE / "pipeline_local"
NS = uuid.UUID("8a6f0d0e-3c3b-4f39-9b0e-6c1d3c3a0f11")
norm = lambda s: " ".join(str(s).lower().split())


def cid_of(ce, name):
    return str(uuid.uuid5(NS, f"{ce}|{norm(name)}"))


def write_run(name, ce, df):
    out = LOCAL / "runs" / name / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / f"assignments_{ce}.csv", index=False)
    return name


def placed(df, ce, term_col):
    # export_hybrid.assign() reads the cluster id from D0.85 and treats how = jev as the pipeline's own placement.
    named = df["cluster"].fillna("").astype(str).str.strip()
    return df.assign(ce=int(ce), term=df[term_col], how="jev", probability=df.get("confidence"),
                     **{"D0.85": [cid_of(ce, c) if c else None for c in named], "D_name": named.where(named != "", None)})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("ce")
    p.add_argument("--prompt", choices=["original", "patched"], default="original")
    a = p.parse_args()
    root, ce = Path(a.root).resolve(), a.ce
    reg = json.loads((HERE / "ces.json").read_text())
    cfg = reg["ces"][ce]
    # A CE whose real id is not a number ("18 - Key West") is keyed here by a stand-in number; the pipeline knows it by
    # its real id.
    eos = cfg.get("eos_id", ce)
    final = root / "snapshots" / (f"ce_{eos}" + ("_patched" if a.prompt == "patched" else "")) / "final"
    if not (final / "clusters.csv").exists():
        raise SystemExit(f"No pipeline output at {final}; run run_ce_pipeline.py {ce} first.")
    sys.path.insert(0, str(HERE))
    from map_ce import SOURCE, build_snapshot
    from snapshot_ce import snapshot_dir

    snap_name = f"final_{cfg['slug']}" + ("_patched" if a.prompt == "patched" else "")
    frozen = pd.read_csv(root / "snapshots" / SOURCE / "ce_names.csv", dtype={"ce": str})["ce"]
    if eos in set(frozen):
        snap = build_snapshot(root, ce, snap_name)
    else:
        fresh = snapshot_dir(root, eos)
        if not (fresh / "ce_names.csv").exists():
            subprocess.run([sys.executable, str(HERE / "snapshot_ce.py"), str(root), eos], check=True)
        snap = build_snapshot(root, ce, snap_name, source=fresh, source_ce=eos)

    clusters = pd.read_csv(final / "clusters.csv")
    kws = pd.read_csv(final / "keywords.csv")
    kws = kws[kws["cluster"].notna() & (kws["cluster"].astype(str).str.strip() != "")]
    order = clusters.sort_values("volume", ascending=False).reset_index(drop=True)
    rank = {norm(n): i + 1 for i, n in enumerate(order["cluster"])}
    ctype = dict(zip(clusters["cluster"], clusters["type"]))
    ck = pd.DataFrame({"ce": int(ce), "cid": [cid_of(ce, c) for c in kws["cluster"]], "rank": [rank.get(norm(c)) for c in kws["cluster"]],
                       "t": [ctype.get(c, "TRANSACTIONAL") for c in kws["cluster"]], "name": kws["cluster"], "ids": "[]",
                       "kw": kws["keyword"], "vol": kws["volume"]})
    # A cluster whose keywords all went elsewhere still keeps its focus keyword, so it shows as a row.
    missing = clusters[~clusters["cluster"].isin(kws["cluster"])]
    if len(missing):
        ck = pd.concat([ck, pd.DataFrame({"ce": int(ce), "cid": [cid_of(ce, c) for c in missing["cluster"]], "rank": [rank.get(norm(c)) for c in missing["cluster"]],
                                          "t": missing["type"], "name": missing["cluster"], "ids": "[]", "kw": missing["focus_keyword"],
                                          "vol": missing["focus_volume"]})])
    # A cluster with no focus keyword in final/ is named by itself, so every cluster row has a keyword to embed.
    ck["kw"] = ck["kw"].where(ck["kw"].notna() & (ck["kw"].astype(str).str.strip() != ""), ck["name"])
    ck.to_csv(snap / "cluster_keywords.csv", index=False)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    paid = placed(pd.read_csv(final / "paid.csv"), ce, "search")
    organic = placed(pd.read_csv(final / "organic.csv"), ce, "search")
    # Ad keywords (the bid text) take the cluster of the same text among the placed keywords or searches.
    by_text = {norm(k): c for k, c in zip(kws["keyword"], kws["cluster"])}
    by_text.update({norm(s): c for s, c in zip(paid["search"], paid["cluster"]) if isinstance(c, str) and c.strip() and norm(s) not in by_text})
    ad = pd.read_csv(snap / "ad_keywords.csv")
    ad = placed(ad.assign(cluster=[by_text.get(norm(t)) for t in ad["term"]], confidence=None), ce, "term")
    runs = {"pairs": write_run(f"{stamp}_final_pairs_{ce}", ce, paid), "organic": write_run(f"{stamp}_final_organic_{ce}", ce, organic),
            "keywords": write_run(f"{stamp}_final_keywords_{ce}", ce, ad)}
    cfg.update({"snapshot": snap_name, "runs": runs, "clusters_from": f"{final.relative_to(root)} ({a.prompt} prompt)"})
    # The head cluster: the one named like the CE (only its name words), else the largest; prepare_ce.py anchors on it.
    words = set(cfg.get("name_words", []))
    named = [n for n in order["cluster"] if words and set(norm(n).split()) == words]
    if not any(norm(n) == norm(cfg.get("head", "")) for n in clusters["cluster"]):
        cfg["head"] = named[0] if named else order["cluster"].iloc[0]
    (HERE / "ces.json").write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    sc = json.loads((final / "scorecard.json").read_text()) if (final / "scorecard.json").exists() else {}
    print(f"CE {ce}: {len(clusters)} clusters, {len(ck)} keyword rows, {ad['D0.85'].notna().sum()} of {len(ad)} ad keywords placed; "
          f"paid clicks with no cluster {sc.get('paid_clicks_no_cluster')}; snapshot {snap_name}")


if __name__ == "__main__":
    main()
