"""Re-run the list checks (eos_base.sql) and the Ads overlap check (ads_overlap.sql) on the fixed list from eos_fix.sql.
Writes clusters_3_0_list_checks_fixed, clusters_3_0_ads_overlap_terms_fixed, clusters_3_0_ads_overlap_fixed and
clusters_3_0_list_verdict_fixed. Prints the composed script with --print instead of running it.
Usage (CLOUDSDK_CONFIG set as for bq): python bq/run_fixed_checks.py
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
RENAME = [("clusters_3_0_eos_keywords_clean", "clusters_3_0_eos_keywords_fixed"),
          ("clusters_3_0_list_checks`", "clusters_3_0_list_checks_fixed`"),
          ("clusters_3_0_ads_overlap_terms`", "clusters_3_0_ads_overlap_terms_fixed`"),
          ("clusters_3_0_ads_overlap`", "clusters_3_0_ads_overlap_fixed`"),
          ("clusters_3_0_list_verdict`", "clusters_3_0_list_verdict_fixed`")]

base = (HERE / "eos_base.sql").read_text()
overlap = (HERE / "ads_overlap.sql").read_text()
functions = base[base.index("CREATE TEMP FUNCTION"):base.index("CREATE OR REPLACE TABLE")]
checks = base[base.index("CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_list_checks`"):]
declare = re.search(r"DECLARE .*?\);\n", overlap, re.S).group(0)
overlap_body = overlap[overlap.index("CREATE OR REPLACE TABLE"):]
script = declare + "\n" + functions + checks + "\n" + overlap_body
for old, new in RENAME:
    script = script.replace(old, new)
if "--print" in sys.argv:
    print(script)
else:
    subprocess.run(["bq", "query", "--use_legacy_sql=false", "--location=EU", "--project_id=headout-dev"], input=script, text=True, check=True)
