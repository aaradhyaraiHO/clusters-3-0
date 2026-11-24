"""Keyword Planner ideas for a list of seeds, for research_ce.py.

  echo '["seed one", "seed two"]' | <google-ads venv python> planner_ideas.py <.env with GOOGLE_ADS_*> <client account>

English, every location, Google Search; 20 seeds per request. Prints {idea: average monthly searches} as JSON.
"""
import json
import sys

from google.ads.googleads.client import GoogleAdsClient


def main():
    env_file, account = sys.argv[1], sys.argv[2]
    env = dict(line.strip().split("=", 1) for line in open(env_file) if "=" in line and not line.startswith("#"))
    client = GoogleAdsClient.load_from_dict({
        "developer_token": env["GOOGLE_ADS_DEVELOPER_TOKEN"], "client_id": env["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": env["GOOGLE_ADS_CLIENT_SECRET"], "refresh_token": env["GOOGLE_ADS_REFRESH_TOKEN"],
        "login_customer_id": env["GOOGLE_ADS_CUSTOMER_ID"].replace("-", ""), "use_proto_plus": True})
    service = client.get_service("KeywordPlanIdeaService")
    seeds, found = json.load(sys.stdin), {}
    for i in range(0, len(seeds), 20):
        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = account
        request.language = "languageConstants/1000"
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        request.include_adult_keywords = False
        request.keyword_seed.keywords.extend(seeds[i:i + 20])
        for idea in service.generate_keyword_ideas(request=request):
            term = idea.text.strip().lower()
            found[term] = max(found.get(term, 0), int(idea.keyword_idea_metrics.avg_monthly_searches or 0))
    json.dump(found, sys.stdout)


if __name__ == "__main__":
    main()
