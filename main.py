from flask import Flask, render_template, Response, jsonify
import json
import time
import pandas as pd
from pathlib import Path

from live_processor import LiveRaceProcessor

PRE_RACE_CSV = r"D:\Licenta\AplicatieLucrareLicenta\date_f1\pre_race_lv_2023.csv"

app = Flask(__name__)

live_service = LiveRaceProcessor()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/drivers")
def drivers():
    return render_template("drivers.html")


@app.route("/tracks")
def tracks():
    return render_template("tracks.html")


@app.route("/api/live-data")
def live_data():
    return jsonify(live_service.get_latest_payload())


@app.route("/api/live-events")
def live_events():
    def event_stream():
        while True:
            payload = live_service.get_latest_payload()
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(2)

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/momentum")
def momentum():
    try:
        df = pd.read_csv("date_f1/pre_race_lv_2023.csv")

        required_cols = ["code", "pilot_momentum_3"]
        missing = [col for col in required_cols if col not in df.columns]

        if missing:
            return jsonify({
                "error": f"Lipsesc coloanele: {missing}"
            }), 500

        top_momentum = (
            df[["code", "pilot_momentum_3"]]
            .dropna()
            .sort_values(by="pilot_momentum_3", ascending=False)
            .head(3)
            .reset_index(drop=True)
        )

        result = []
        for _, row in top_momentum.iterrows():
            result.append({
                "code": row["code"],
                "momentum": round(float(row["pilot_momentum_3"]), 3)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/api/drivers")
def api_drivers():
    try:
        df = pd.read_csv(PRE_RACE_CSV)

        df = df[[
            "driverId",
            "code",
            "rata_accidente_pilot",
            "pilot_momentum_3"
        ]]

        df = df[df["code"].notna()]
        df = df.groupby("driverId").first().reset_index()
        df = df.sort_values(by="pilot_momentum_3", ascending=False).reset_index(drop=True)

        drivers = []

        for _, row in df.iterrows():
            drivers.append({
                "driverId": int(row["driverId"]),
                "code": row["code"],
                "rata_accidente_pilot": round(float(row["rata_accidente_pilot"]) * 100, 1),
                "pilot_momentum": round(float(row["pilot_momentum_3"]), 2)
            })

        return jsonify(drivers)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    live_service.start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)