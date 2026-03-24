from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "McCalls Dashboard API is running"

@app.route("/api/report")
def get_report():
    month = request.args.get("month")

    return jsonify({
        "month": month,
        "meta_ads": {
            "spend": 0,
            "impressions": 0,
            "clicks": 0,
            "purchases": 0,
            "roas": 0
        },
        "google_ads": {
            "cost": 0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "conversion_value": 0
        }
    })

if __name__ == "__main__":
    app.run(debug=True)
