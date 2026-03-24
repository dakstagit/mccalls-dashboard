from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
AD_ACCOUNT_ID = "act_3178253445534981"


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
        if item.get("action_type") in ["omni_purchase", "offsite_conversion.fb_pixel_purchase", "purchase"]:
            try:
                return float(item.get("value", 0))
            except:
                return 0
    return 0


@app.route("/")
def home():
    return "McCalls Dashboard API is running"


@app.route("/api/report")
def get_report():
    month = request.args.get("month")

    if not META_ACCESS_TOKEN:
        return jsonify({
            "error": "META_ACCESS_TOKEN is missing in Render environment variables"
        }), 500

    if not month:
        return jsonify({
            "error": "Month is required in YYYY-MM format"
        }), 400

    try:
        # Monthly summary request
        summary_url = f"https://graph.facebook.com/v18.0/{AD_ACCOUNT_ID}/insights"
        summary_params = {
            "fields": "spend,impressions,reach,ctr,actions,action_values,purchase_roas,date_start,date_stop",
            "time_increment": "monthly",
            "date_preset": "last_90d",
            "access_token": META_ACCESS_TOKEN
        }

        summary_response = requests.get(summary_url, params=summary_params)
        summary_json = summary_response.json()

        if summary_response.status_code != 200:
            return jsonify({
                "error": "Meta summary API request failed",
                "meta_response": summary_json
            }), summary_response.status_code

        selected_month_data = None
        for row in summary_json.get("data", []):
            if row.get("date_start", "").startswith(month):
                selected_month_data = row
                break

        if not selected_month_data:
            selected_month_data = {
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

        # Campaign-level request
        campaign_data = []

        campaign_url = f"https://graph.facebook.com/v18.0/{AD_ACCOUNT_ID}/insights"
        campaign_params = {
            "fields": "campaign_name,spend,impressions,reach,ctr,actions,action_values,purchase_roas,date_start,date_stop",
            "level": "campaign",
            "time_range": f"{{'since':'{month}-01','until':'{month}-31'}}",
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
            "meta_campaigns": campaign_data
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
