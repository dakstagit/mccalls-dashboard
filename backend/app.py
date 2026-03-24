from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
AD_ACCOUNT_ID = "act_3178253445534981"


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

    url = f"https://graph.facebook.com/v18.0/{AD_ACCOUNT_ID}/insights"

    params = {
        "fields": "spend,impressions,clicks,ctr,cpc,actions,purchase_roas,date_start,date_stop",
        "time_increment": "monthly",
        "date_preset": "last_90d",
        "access_token": META_ACCESS_TOKEN
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if response.status_code != 200:
            return jsonify({
                "error": "Meta API request failed",
                "meta_response": data
            }), response.status_code

        selected_month_data = None

        if month:
            for row in data.get("data", []):
                if row.get("date_start", "").startswith(month):
                    selected_month_data = row
                    break

        return jsonify({
            "requested_month": month,
            "meta_ads": selected_month_data if selected_month_data else data.get("data", [])
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
