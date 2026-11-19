"""Map the published microbrand pages to the hybrid clusters with the clusters_3_0 page mapper (cluster_table.build:
page focus keyword -> PolyFuzz -> embeddings), and write hybrid/pages_189.csv next to this file.

Usage: <clusters_3_0>/.env-clusters/venv/bin/python map_hybrid_pages.py   (run from the clusters_3_0 dir)
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import cluster_table  # noqa: E402
import runlib  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

HERE = Path(__file__).resolve().parent
SNAPSHOT = "20261029_hybrid_sources"
MAPPING_RUN = "20261029-153231_mapping_20261029_hybrid_sources"


class ScratchRun:
    """The slice of runlib.Run that cluster_table.build uses, writing to a temp dir instead of a new run."""
    out = Path(tempfile.mkdtemp())

    def input(self, name):
        return runlib.SNAPSHOTS / SNAPSHOT / name

    def upstream(self, run_id, name):
        return runlib.RUNS / run_id / "outputs" / name

    def record(self, *_):
        pass


model = SentenceTransformer(".env-clusters/models/paraphrase-multilingual-MiniLM-L12-v2")
_, pages, _, _ = cluster_table.build(ScratchRun(), "189", MAPPING_RUN, model)
pages.to_csv(HERE / "hybrid" / "pages_189.csv", index=False)
print(f"{pages['cid'].notna().sum()} of {len(pages)} pages mapped")
