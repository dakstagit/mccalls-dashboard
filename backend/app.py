from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import json
import calendar

app = Flask(__name__)
CORS(app)

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
AD_ACCOUNT_ID = "act_3178253445534981"

GOOGLE_DEV_TOKEN = os.getenv("GOOGLE_DEV_TOKEN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
GOOGLE_LOGIN_CUSTOMER_ID = os.getenv("GOOGLE_LOGIN_CUSTOMER_ID")
GOOGLE_CUSTOMER_ID = os.getenv("GOOGLE_CUSTOMER_ID")


# -------------------------
# HELPERS
# -------------------------

def safe_float(value, default=0):
    try:
        return float(value)
    except:
        return default


def safe_int(value, default=0):
    try:
        return int(float(value))
    except:
        return default


def pct_change(current, previous):
    if previous == 0:
        if current == 0:
            return 0
        return 100
    return round(((current - previous) / previous) * 100, 2)


def build_month_range(month_str):
    year, month_num = map(int, month_str.split("-"))
    last_day = calendar.monthrange(year, month_num)[1]
    start_date = f"{month_str}-01"
    end_date = f"{month_str}-{last_day:02d}"
    return start_date, end_date, year, month_num


def previous_month(month_str):
    year, month_num = map(int, month_str.split("-"))
    if month_num == 1:
        return f"{year-1}-12"
    return f"{year}-{month_num-1:02d}"


def get_action_value(actions, action_type):
    if not actions:
        return 0
    for item in actions:
        if item.get("action_type") == action_type:
            return safe_float(item.get("value", 0))
    return 0


def get_action_value_from_values(action_values, action_type):
    if not action_values:
        return 0
    for item in action_values:
        if item.get("action_type") == action_type:
            return safe_float(item.get("value", 0))
    return 0


def get_purchase_roas(purchase_roas):
    if not purchase_roas:
        return 0
    for item in purchase_roas:
        if item.get("action_type") in [
            "omni_purchase",
            "offsite_conversion.fb_pixel_purchase",
            "purchase"
        ]:
            return safe_float(item.get("value", 0))
    return 0


def get_google_access_token():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REFRESH_TOKEN:
        raise Exception("Missing GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, or GOOGLE_REFRESH_TOKEN")

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token"
        }
    )

    token_json = token_response.json()

    if token_response.status_code != 200:
        raise Exception(f"Google token refresh failed: {token_json}")

    return token_json.get("access_token")


# -------------------------
# STATUS / COMPARISON LOGIC
# -------------------------

def status_label(metric_name, value):
    name = metric_name.lower()

    if name == "roas":
        if value >= 6:
            return "strong"
        elif value >= 3:
            return "watch"
        return "poor"

    if name == "ctr":
        if value >= 3:
            return "strong"
        elif value >= 1.5:
            return "watch"
        return "poor"

    if name == "cost_per_purchase":
        if value <= 15:
            return "strong"
        elif value <= 30:
            return "watch"
        return "poor"

    if name == "purchases":
        if value >= 20:
            return "strong"
        elif value >= 5:
            return "watch"
        return "poor"

    return "watch"


def build_metric_comparison(current, previous, metric_name):
    current_val = safe_float(current)
    previous_val = safe_float(previous)
    delta = round(current_val - previous_val, 2)
    change_pct = pct_change(current_val, previous_val)

    direction = "flat"
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"

    return {
        "current": round(current_val, 2),
        "previous": round(previous_val, 2),
        "delta": delta,
        "change_pct": change_pct,
        "direction": direction,
        "status": status_label(metric_name, current_val)
    }


def build_summary_comparison(current_summary, previous_summary, fields):
    result = {}
    for field in fields:
        result[field] = build_metric_comparison(
            current_summary.get(field, 0),
            previous_summary.get(field, 0),
            field
        )
    return result


# -------------------------
# HIGHLIGHTS / INSIGHTS
# -------------------------

def campaign_highlights(campaigns):
    if not campaigns:
        return {
            "best_roas": None,
            "most_purchases": None,
            "highest_spend": None,
            "worst_cpp": None
        }

    best_roas = max(campaigns, key=lambda x: safe_float(x.get("purchase_roas", 0)))
    most_purchases = max(campaigns, key=lambda x: safe_float(x.get("purchases", 0)))
    highest_spend = max(campaigns, key=lambda x: safe_float(x.get("amount_spent", 0)))

    valid_cpp = [c for c in campaigns if safe_float(c.get("purchases", 0)) > 0]
    worst_cpp = max(valid_cpp, key=lambda x: safe_float(x.get("cost_per_purchase", 0))) if valid_cpp else None

    return {
        "best_roas": {
            "campaign_name": best_roas.get("campaign_name", ""),
            "value": round(safe_float(best_roas.get("purchase_roas", 0)), 2)
        } if best_roas else None,
        "most_purchases": {
            "campaign_name": most_purchases.get("campaign_name", ""),
            "value": round(safe_float(most_purchases.get("purchases", 0)), 2)
        } if most_purchases else None,
        "highest_spend": {
            "campaign_name": highest_spend.get("campaign_name", ""),
            "value": round(safe_float(highest_spend.get("amount_spent", 0)), 2)
        } if highest_spend else None,
        "worst_cpp": {
            "campaign_name": worst_cpp.get("campaign_name", ""),
            "value": round(safe_float(worst_cpp.get("cost_per_purchase", 0)), 2)
        } if worst_cpp else None
    }


def build_channel_role_summary(meta_summary, google_summary):
    meta_clicks = safe_float(meta_summary.get("link_clicks", 0))
    google_clicks = safe_float(google_summary.get("link_clicks", 0))
    meta_purchases = safe_float(meta_summary.get("purchases", 0))
    google_purchases = safe_float(google_summary.get("purchases", 0))

    meta_role = "Meta is acting primarily as a traffic and retargeting channel."
    google_role = "Google is acting primarily as a demand-capture and conversion channel."

    if meta_purchases > google_purchases:
        meta_role = "Meta is contributing strongly to direct conversion performance this month."
    if google_clicks < meta_clicks and google_purchases > meta_purchases:
        google_role = "Google is converting lower-volume, higher-intent traffic efficiently."

    return {
        "meta": meta_role,
        "google": google_role
    }


def build_key_takeaways(meta_summary, google_summary, meta_highlights, google_highlights):
    takeaways = []

    if safe_float(google_summary.get("purchase_roas", 0)) > safe_float(meta_summary.get("purchase_roas", 0)):
        takeaways.append("Google delivered stronger direct conversion efficiency than Meta this month.")
    else:
        takeaways.append("Meta delivered stronger direct conversion efficiency than Google this month.")

    if google_highlights.get("best_roas"):
        takeaways.append(
            f"Top Google efficiency driver: {google_highlights['best_roas']['campaign_name']} "
            f"(ROAS {google_highlights['best_roas']['value']})."
        )

    if meta_highlights.get("best_roas"):
        takeaways.append(
            f"Top Meta efficiency driver: {meta_highlights['best_roas']['campaign_name']} "
            f"(ROAS {meta_highlights['best_roas']['value']})."
        )

    if safe_float(meta_summary.get("purchases", 0)) == 0 and safe_float(meta_summary.get("amount_spent", 0)) > 0:
        takeaways.append("Meta generated spend without tracked purchases, so campaign quality should be reviewed.")

    return takeaways[:3]


def build_recommendations(meta_summary, google_summary, meta_campaigns, google_campaigns):
    recommendations = []

    high_roas_google = [c for c in google_campaigns if safe_float(c.get("purchase_roas", 0)) >= 5]
    weak_meta = [c for c in meta_campaigns if safe_float(c.get("amount_spent", 0)) > 0 and safe_float(c.get("purchases", 0)) == 0]

    if high_roas_google:
        recommendations.append("Consider increasing budget on high-ROAS Google campaigns to scale efficient conversions.")

    if weak_meta:
        recommendations.append("Reduce or refresh Meta campaigns that are spending without producing purchases.")

    if safe_float(meta_summary.get("ctr", 0)) < 1.5:
        recommendations.append("Meta CTR is soft; refresh creative and messaging to improve engagement quality.")

    if safe_float(google_summary.get("cost_per_purchase", 0)) > 20:
        recommendations.append("Google cost per purchase is elevated; review search terms, bids, and campaign structure.")

    if not recommendations:
        recommendations.append("Maintain allocation toward strongest campaigns while testing incremental creative and audience improvements.")

    return recommendations[:4]


def build_executive_summary(blended, meta_summary, google_summary):
    winner = "Google"
    if safe_float(meta_summary.get("purchase_roas", 0)) > safe_float(google_summary.get("purchase_roas", 0)):
        winner = "Meta"

    return (
        f"This month generated {round(blended['purchase_conversion_value'], 2)} in tracked conversion value "
        f"from {round(blended['amount_spent'], 2)} spend, delivering a blended ROAS of {round(blended['purchase_roas'], 2)}. "
        f"{winner} was the stronger efficiency channel this month, while the other platform contributed supporting traffic and coverage. "
        f"The key focus next month should be concentrating spend into proven campaigns and tightening weaker areas."
    )


def build_commentary(blended, meta_summary, google_summary, takeaways, recommendations):
    return {
        "performance_overview": (
            f"Total paid media spend was {round(blended['amount_spent'], 2)} and delivered "
            f"{round(blended['purchase_conversion_value'], 2)} in tracked conversion value."
        ),
        "platform_comparison": (
            f"Meta ROAS: {round(safe_float(meta_summary.get('purchase_roas', 0)), 2)} | "
            f"Google ROAS: {round(safe_float(google_summary.get('purchase_roas', 0)), 2)}."
        ),
        "campaign_highlights": takeaways,
        "next_actions": recommendations
    }


# -------------------------
# PLATFORM FETCHERS
# -------------------------

def fetch_meta_data(month_str):
    start_date, end_date, _, _ = build_month_range(month_str)

    if not META_ACCESS_TOKEN:
        raise Exception("META_ACCESS_TOKEN is missing in Render environment variables")

    # Summary
    summary_url = f"https://graph.facebook.com/v18.0/{AD_ACCOUNT_ID}/insights"
    summary_params = {
        "fields": "spend,impressions,reach,ctr,actions,action_values,purchase_roas",
        "time_range": f"{{'since':'{start_date}','until':'{end_date}'}}",
        "access_token": META_ACCESS_TOKEN
    }

    summary_response = requests.get(summary_url, params=summary_params)
    summary_json = summary_response.json()

    if summary_response.status_code != 200:
        raise Exception(f"Meta summary API request failed: {summary_json}")

    selected_month_data = summary_json.get("data", [{}])[0] if summary_json.get("data") else {
        "spend": 0,
        "impressions": 0,
        "reach": 0,
        "ctr": 0,
        "actions": [],
        "action_values": [],
        "purchase_roas": []
    }

    actions = selected_month_data.get("actions", [])
    action_values = selected_month_data.get("action_values", [])
    purchase_roas = selected_month_data.get("purchase_roas", [])

    summary = {
        "amount_spent": round(safe_float(selected_month_data.get("spend", 0)), 2),
        "impressions": safe_int(selected_month_data.get("impressions", 0)),
        "reach": safe_int(selected_month_data.get("reach", 0)),
        "link_clicks": round(get_action_value(actions, "link_click"), 2),
        "landing_page_views": round(get_action_value(actions, "landing_page_view"), 2),
        "ctr": round(safe_float(selected_month_data.get("ctr", 0)), 2),
        "adds_to_cart": round(get_action_value(actions, "add_to_cart"), 2),
        "checkouts": round(get_action_value(actions, "initiate_checkout"), 2),
        "purchases": round(get_action_value(actions, "purchase"), 2),
        "purchase_conversion_value": round(get_action_value_from_values(action_values, "purchase"), 2),
        "purchase_roas": round(get_purchase_roas(purchase_roas), 2),
        "cost_per_purchase": 0
    }

    if summary["purchases"] > 0:
        summary["cost_per_purchase"] = round(summary["amount_spent"] / summary["purchases"], 2)

    # Campaigns
    campaign_url = f"https://graph.facebook.com/v18.0/{AD_ACCOUNT_ID}/insights"
    campaign_params = {
        "fields": "campaign_name,spend,impressions,reach,ctr,actions,action_values,purchase_roas",
        "level": "campaign",
        "time_range": f"{{'since':'{start_date}','until':'{end_date}'}}",
        "access_token": META_ACCESS_TOKEN
    }

    campaign_response = requests.get(campaign_url, params=campaign_params)
    campaign_json = campaign_response.json()

    if campaign_response.status_code != 200:
        raise Exception(f"Meta campaign API request failed: {campaign_json}")

    campaigns = []

    for row in campaign_json.get("data", []):
        row_actions = row.get("actions", [])
        row_action_values = row.get("action_values", [])
        row_purchase_roas = row.get("purchase_roas", [])

        row_spend = round(safe_float(row.get("spend", 0)), 2)
        row_purchases = round(get_action_value(row_actions, "purchase"), 2)

        campaigns.append({
            "campaign_name": row.get("campaign_name", ""),
            "amount_spent": row_spend,
            "impressions": safe_int(row.get("impressions", 0)),
            "reach": safe_int(row.get("reach", 0)),
            "link_clicks": round(get_action_value(row_actions, "link_click"), 2),
            "landing_page_views": round(get_action_value(row_actions, "landing_page_view"), 2),
            "ctr": round(safe_float(row.get("ctr", 0)), 2),
            "adds_to_cart": round(get_action_value(row_actions, "add_to_cart"), 2),
            "checkouts": round(get_action_value(row_actions, "initiate_checkout"), 2),
            "purchases": row_purchases,
            "purchase_conversion_value": round(get_action_value_from_values(row_action_values, "purchase"), 2),
            "purchase_roas": round(get_purchase_roas(row_purchase_roas), 2),
            "cost_per_purchase": round(row_spend / row_purchases, 2) if row_purchases > 0 else 0
        })

    return {
        "summary": summary,
        "campaigns": campaigns
    }


def fetch_google_data(month_str):
    start_date, end_date, _, _ = build_month_range(month_str)

    if not GOOGLE_DEV_TOKEN or not GOOGLE_CUSTOMER_ID:
        raise Exception("GOOGLE_DEV_TOKEN or GOOGLE_CUSTOMER_ID is missing in Render environment variables")

    google_access_token = get_google_access_token()

    google_query = (
        "SELECT "
        "campaign.name, "
        "metrics.cost_micros, "
        "metrics.impressions, "
        "metrics.clicks, "
        "metrics.ctr, "
        "metrics.conversions, "
        "metrics.conversions_value "
        f"FROM campaign "
        f"WHERE segments.date BETWEEN '{start_date}' AND '{end_date}' "
        "AND metrics.impressions > 0"
    )

    google_headers = {
        "Authorization": f"Bearer {google_access_token}",
        "developer-token": GOOGLE_DEV_TOKEN,
        "Content-Type": "application/json"
    }

    if GOOGLE_LOGIN_CUSTOMER_ID:
        google_headers["login-customer-id"] = GOOGLE_LOGIN_CUSTOMER_ID

    google_body = {"query": google_query}

    google_response = requests.post(
        f"https://googleads.googleapis.com/v23/customers/{GOOGLE_CUSTOMER_ID}/googleAds:search",
        headers=google_headers,
        data=json.dumps(google_body)
    )

    google_json = google_response.json()

    if google_response.status_code != 200:
        raise Exception(f"Google Ads API request failed: {google_json}")

    campaigns = []
    total_spend = 0
    total_impressions = 0
    total_clicks = 0
    total_conversions = 0
    total_conversion_value = 0

    for row in google_json.get("results", []):
        campaign_name = row.get("campaign", {}).get("name", "")
        metrics = row.get("metrics", {})

        amount_spent = round(safe_float(metrics.get("costMicros", 0)) / 1000000, 2)
        impressions = safe_int(metrics.get("impressions", 0))
        link_clicks = safe_int(metrics.get("clicks", 0))
        ctr = round(safe_float(metrics.get("ctr", 0)) * 100, 2)
        purchases = round(safe_float(metrics.get("conversions", 0)), 2)
        purchase_conversion_value = round(safe_float(metrics.get("conversionsValue", 0)), 2)
        purchase_roas = round(purchase_conversion_value / amount_spent, 2) if amount_spent > 0 else 0
        cost_per_purchase = round(amount_spent / purchases, 2) if purchases > 0 else 0

        total_spend += amount_spent
        total_impressions += impressions
        total_clicks += link_clicks
        total_conversions += purchases
        total_conversion_value += purchase_conversion_value

        campaigns.append({
            "campaign_name": campaign_name,
            "amount_spent": amount_spent,
            "impressions": impressions,
            "link_clicks": link_clicks,
            "ctr": ctr,
            "purchases": purchases,
            "purchase_conversion_value": purchase_conversion_value,
            "purchase_roas": purchase_roas,
            "cost_per_purchase": cost_per_purchase
        })

    summary_ctr = round((total_clicks / total_impressions) * 100, 2) if total_impressions > 0 else 0
    summary_roas = round(total_conversion_value / total_spend, 2) if total_spend > 0 else 0
    summary_cpp = round(total_spend / total_conversions, 2) if total_conversions > 0 else 0

    return {
        "summary": {
            "amount_spent": round(total_spend, 2),
            "impressions": total_impressions,
            "link_clicks": total_clicks,
            "ctr": summary_ctr,
            "purchases": round(total_conversions, 2),
            "purchase_conversion_value": round(total_conversion_value, 2),
            "purchase_roas": summary_roas,
            "cost_per_purchase": summary_cpp
        },
        "campaigns": campaigns
    }


def build_blended_summary(meta_summary, google_summary):
    spend = round(safe_float(meta_summary.get("amount_spent", 0)) + safe_float(google_summary.get("amount_spent", 0)), 2)
    impressions = safe_int(meta_summary.get("impressions", 0)) + safe_int(google_summary.get("impressions", 0))
    clicks = round(safe_float(meta_summary.get("link_clicks", 0)) + safe_float(google_summary.get("link_clicks", 0)), 2)
    purchases = round(safe_float(meta_summary.get("purchases", 0)) + safe_float(google_summary.get("purchases", 0)), 2)
    value = round(safe_float(meta_summary.get("purchase_conversion_value", 0)) + safe_float(google_summary.get("purchase_conversion_value", 0)), 2)

    ctr = round((clicks / impressions) * 100, 2) if impressions > 0 else 0
    roas = round(value / spend, 2) if spend > 0 else 0
    cpp = round(spend / purchases, 2) if purchases > 0 else 0

    return {
        "amount_spent": spend,
        "impressions": impressions,
        "link_clicks": clicks,
        "ctr": ctr,
        "purchases": purchases,
        "purchase_conversion_value": value,
        "purchase_roas": roas,
        "cost_per_purchase": cpp
    }


# -------------------------
# ROUTES
# -------------------------

@app.route("/")
def home():
    return "McCalls Dashboard API is running"


@app.route("/api/report")
def get_report():
    month = request.args.get("month")

    if not month:
        return jsonify({
            "error": "Month is required in YYYY-MM format"
        }), 400

    try:
        prev_month = previous_month(month)

        current_meta = fetch_meta_data(month)
        current_google = fetch_google_data(month)

        previous_meta = fetch_meta_data(prev_month)
        previous_google = fetch_google_data(prev_month)

        meta_summary = current_meta["summary"]
        meta_campaigns = current_meta["campaigns"]
        meta_prev_summary = previous_meta["summary"]

        google_summary = current_google["summary"]
        google_campaigns = current_google["campaigns"]
        google_prev_summary = previous_google["summary"]

        blended_summary = build_blended_summary(meta_summary, google_summary)
        blended_prev_summary = build_blended_summary(meta_prev_summary, google_prev_summary)

        meta_highlights = campaign_highlights(meta_campaigns)
        google_highlights = campaign_highlights(google_campaigns)

        channel_roles = build_channel_role_summary(meta_summary, google_summary)
        takeaways = build_key_takeaways(meta_summary, google_summary, meta_highlights, google_highlights)
        recommendations = build_recommendations(meta_summary, google_summary, meta_campaigns, google_campaigns)

        executive_summary = build_executive_summary(blended_summary, meta_summary, google_summary)
        commentary = build_commentary(blended_summary, meta_summary, google_summary, takeaways, recommendations)

        overview_comparison = build_summary_comparison(
            blended_summary,
            blended_prev_summary,
            ["amount_spent", "link_clicks", "purchases", "purchase_conversion_value", "purchase_roas", "cost_per_purchase"]
        )

        meta_comparison = build_summary_comparison(
            meta_summary,
            meta_prev_summary,
            ["amount_spent", "link_clicks", "purchases", "purchase_conversion_value", "purchase_roas", "cost_per_purchase", "ctr"]
        )

        google_comparison = build_summary_comparison(
            google_summary,
            google_prev_summary,
            ["amount_spent", "link_clicks", "purchases", "purchase_conversion_value", "purchase_roas", "cost_per_purchase", "ctr"]
        )

        return jsonify({
            "requested_month": month,
            "previous_month": prev_month,

            "overview": {
                "summary": blended_summary,
                "previous_summary": blended_prev_summary,
                "comparison": overview_comparison,
                "executive_summary": executive_summary,
                "commentary": commentary,
                "channel_roles": channel_roles,
                "key_takeaways": takeaways,
                "recommendations": recommendations
            },

            "meta": {
                "summary": meta_summary,
                "previous_summary": meta_prev_summary,
                "comparison": meta_comparison,
                "highlights": meta_highlights,
                "campaigns": meta_campaigns
            },

            "google": {
                "summary": google_summary,
                "previous_summary": google_prev_summary,
                "comparison": google_comparison,
                "highlights": google_highlights,
                "campaigns": google_campaigns
            }
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
