from flask import Flask, render_template, Response, jsonify
import json
import time

from live_processor import LiveRaceProcessor

app = Flask(__name__)

# porneste serviciul live o singura data
live_service = LiveRaceProcessor()
live_service.start()


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


@app.route("/video_feed")
def video_feed():
    def generate():
        while True:
            frame = live_service.get_latest_frame_jpeg()

            if frame is None:
                time.sleep(0.1)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )

            time.sleep(0.03)

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(debug=True, threaded=True)