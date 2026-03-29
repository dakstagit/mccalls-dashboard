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


def get_action_value(actions, action_type):
    if not actions:
        return 0
    for item in actions:
        if item.get("action_type") == action_type:
            try:
                return float(item.get("value", 0))
            except:
                return 0
    return 0


def get_action_value_from_values(action_values, action_type):
    if not action_values:
        return 0
    for item in action_values:
        if item.get("action_type") == action_type:
            try:
                return float(item.get("value", 0))
            except:
                return 0
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
            try:
                return float(item.get("value", 0))
            except:
                return 0
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

    start_date = f"{month}-01"
    year, month_num = map(int, month.split("-"))
    last_day = calendar.monthrange(year, month_num)[1]
    end_date = f"{month}-{last_day:02d}"

    try:
        # -------------------------
        # META SUMMARY
        # -------------------------
        if not META_ACCESS_TOKEN:
            return jsonify({
                "error": "META_ACCESS_TOKEN is missing in Render environment variables"
            }), 500

        summary_url = f"https://graph.facebook.com/v18.0/{AD_ACCOUNT_ID}/insights"
        summary_params = {
            "fields": "spend,impressions,reach,ctr,actions,action_values,purchase_roas",
            "time_range": f"{{'since':'{start_date}','until':'{end_date}'}}",
            "access_token": META_ACCESS_TOKEN
        }

        summary_response = requests.get(summary_url, params=summary_params)
        summary_json = summary_response.json()

        if summary_response.status_code != 200:
            return jsonify({
                "error": "Meta summary API request failed",
                "meta_response": summary_json
            }), summary_response.status_code

        selected_month_data = summary_json.get("data", [{}])[0] if summary_json.get("data") else {
            "spend": 0,
            "impressions": 0,
            "reach": 0,
            "ctr": 0,
            "actions": [],
            "action_values": [],
            "purchase_roas": []
        }

        spend = float(selected_month_data.get("spend", 0))
        impressions = int(float(selected_month_data.get("impressions", 0)))
        reach = int(float(selected_month_data.get("reach", 0)))
        ctr = float(selected_month_data.get("ctr", 0))

        actions = selected_month_data.get("actions", [])
        action_values = selected_month_data.get("action_values", [])
        purchase_roas = selected_month_data.get("purchase_roas", [])

        link_clicks = get_action_value(actions, "link_click")
        landing_page_views = get_action_value(actions, "landing_page_view")
        adds_to_cart = get_action_value(actions, "add_to_cart")
        checkouts = get_action_value(actions, "initiate_checkout")
        purchases = get_action_value(actions, "purchase")
        purchase_conversion_value = get_action_value_from_values(action_values, "purchase")
        purchase_roas_value = get_purchase_roas(purchase_roas)
        cost_per_purchase = round(spend / purchases, 2) if purchases > 0 else 0

        # -------------------------
        # META CAMPAIGNS
        # -------------------------
        campaign_data = []

        campaign_url = f"https://graph.facebook.com/v18.0/{AD_ACCOUNT_ID}/insights"
        campaign_params = {
            "fields": "campaign_name,spend,impressions,reach,ctr,actions,action_values,purchase_roas,date_start,date_stop",
            "level": "campaign",
            "time_range": f"{{'since':'{start_date}','until':'{end_date}'}}",
            "access_token": META_ACCESS_TOKEN
        }

        campaign_response = requests.get(campaign_url, params=campaign_params)
        campaign_json = campaign_response.json()

        if campaign_response.status_code == 200:
            for row in campaign_json.get("data", []):
                row_actions = row.get("actions", [])
                row_action_values = row.get("action_values", [])
                row_purchase_roas = row.get("purchase_roas", [])

                row_spend = float(row.get("spend", 0))
                row_impressions = int(float(row.get("impressions", 0)))
                row_reach = int(float(row.get("reach", 0)))
                row_ctr = float(row.get("ctr", 0))

                row_link_clicks = get_action_value(row_actions, "link_click")
                row_landing_page_views = get_action_value(row_actions, "landing_page_view")
                row_adds_to_cart = get_action_value(row_actions, "add_to_cart")
                row_checkouts = get_action_value(row_actions, "initiate_checkout")
                row_purchases = get_action_value(row_actions, "purchase")
                row_purchase_conversion_value = get_action_value_from_values(row_action_values, "purchase")
                row_purchase_roas_value = get_purchase_roas(row_purchase_roas)
                row_cost_per_purchase = round(row_spend / row_purchases, 2) if row_purchases > 0 else 0

                campaign_data.append({
                    "campaign_name": row.get("campaign_name", ""),
                    "amount_spent": row_spend,
                    "impressions": row_impressions,
                    "reach": row_reach,
                    "link_clicks": row_link_clicks,
                    "landing_page_views": row_landing_page_views,
                    "ctr": row_ctr,
                    "adds_to_cart": row_adds_to_cart,
                    "checkouts": row_checkouts,
                    "purchases": row_purchases,
                    "purchase_conversion_value": row_purchase_conversion_value,
                    "purchase_roas": row_purchase_roas_value,
                    "cost_per_purchase": row_cost_per_purchase
                })
        else:
            return jsonify({
                "error": "Meta campaign API request failed",
                "meta_response": campaign_json
            }), campaign_response.status_code

        # -------------------------
        # GOOGLE SUMMARY + CAMPAIGNS
        # -------------------------
        if not GOOGLE_DEV_TOKEN or not GOOGLE_CUSTOMER_ID:
            return jsonify({
                "error": "GOOGLE_DEV_TOKEN or GOOGLE_CUSTOMER_ID is missing in Render environment variables"
            }), 500

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
            "login-customer-id": GOOGLE_LOGIN_CUSTOMER_ID,
            "Content-Type": "application/json"
        }

        google_body = {
            "query": google_query
        }

        google_response = requests.post(
            f"https://googleads.googleapis.com/v23/customers/{GOOGLE_CUSTOMER_ID}/googleAds:search",
            headers=google_headers,
            data=json.dumps(google_body)
        )

        google_json = google_response.json()

        if google_response.status_code != 200:
            return jsonify({
                "error": "Google Ads API request failed",
                "google_response": google_json
            }), google_response.status_code

        google_campaigns = []
        google_total_spend = 0
        google_total_impressions = 0
        google_total_clicks = 0
        google_total_conversions = 0
        google_total_conversion_value = 0

        for row in google_json.get("results", []):
            campaign_name = row.get("campaign", {}).get("name", "")
            metrics = row.get("metrics", {})

            amount_spent = round(float(metrics.get("costMicros", 0)) / 1000000, 2)
            impressions = int(metrics.get("impressions", 0))
            link_clicks = int(metrics.get("clicks", 0))
            ctr = round(float(metrics.get("ctr", 0)) * 100, 2)
            purchases = round(float(metrics.get("conversions", 0)), 2)
            purchase_conversion_value = round(float(metrics.get("conversionsValue", 0)), 2)
            purchase_roas = round(purchase_conversion_value / amount_spent, 2) if amount_spent > 0 else 0
            cost_per_purchase = round(amount_spent / purchases, 2) if purchases > 0 else 0

            google_total_spend += amount_spent
            google_total_impressions += impressions
            google_total_clicks += link_clicks
            google_total_conversions += purchases
            google_total_conversion_value += purchase_conversion_value

            google_campaigns.append({
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

        google_summary_ctr = round((google_total_clicks / google_total_impressions) * 100, 2) if google_total_impressions > 0 else 0
        google_summary_roas = round(google_total_conversion_value / google_total_spend, 2) if google_total_spend > 0 else 0
        google_summary_cpp = round(google_total_spend / google_total_conversions, 2) if google_total_conversions > 0 else 0

        return jsonify({
            "requested_month": month,
            "meta_ads": {
                "amount_spent": spend,
                "impressions": impressions,
                "reach": reach,
                "link_clicks": link_clicks,
                "landing_page_views": landing_page_views,
                "ctr": ctr,
                "adds_to_cart": adds_to_cart,
                "checkouts": checkouts,
                "purchases": purchases,
                "purchase_conversion_value": purchase_conversion_value,
                "purchase_roas": purchase_roas_value,
                "cost_per_purchase": cost_per_purchase
            },
            "meta_campaigns": campaign_data,
            "google_ads": {
                "amount_spent": round(google_total_spend, 2),
                "impressions": google_total_impressions,
                "link_clicks": google_total_clicks,
                "ctr": google_summary_ctr,
                "purchases": round(google_total_conversions, 2),
                "purchase_conversion_value": round(google_total_conversion_value, 2),
                "purchase_roas": google_summary_roas,
                "cost_per_purchase": google_summary_cpp
            },
            "google_campaigns": google_campaigns
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
