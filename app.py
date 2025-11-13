"""
app.py
Flask backend for Smart Waste Management System.
Endpoints:
- GET /api/level           -> returns current level for main bin
- GET /api/bins            -> returns list of bins and their latest levels
- GET /stream              -> SSE stream to push updates in real-time
"""

import time
import json
import threading
from queue import Queue
from flask import Flask, jsonify, Response, stream_with_context
from sensor import UltrasonicSensor

# Configuration
BIN_HEIGHT_CM = 40           # physical height from sensor to bottom (adjust to your bin)
POLL_INTERVAL = 5            # seconds between reads
ALERT_THRESHOLD = 80.0       # percent to trigger 'full' alert

# If you plan multiple bins, you could create multiple UltrasonicSensor instances with different pins.
BINS = {
    "bin_1": {
        "name": "Main Gate Bin",
        "sensor": UltrasonicSensor(trig_pin=23, echo_pin=24, max_distance_cm=BIN_HEIGHT_CM),
        "height_cm": BIN_HEIGHT_CM,
        "last_level": None,
        "last_update": None,
        "is_alert": False
    }
    # Add more bins here e.g. "bin_2": {...}
}

# Simple in-memory event queue used for SSE subscribers
event_queue = Queue()

app = Flask(__name__)

def poll_sensors():
    """Background thread: poll sensors periodically and update in-memory store and queue events."""
    try:
        while True:
            for bin_id, info in BINS.items():
                try:
                    level = info["sensor"].get_fill_level_percent(info["height_cm"])
                except Exception as e:
                    # If any sensor read error occurs, set None or keep previous
                    app.logger.exception(f"Error reading sensor for {bin_id}: {e}")
                    level = None

                timestamp = time.time()
                info["last_level"] = level
                info["last_update"] = timestamp
                info["is_alert"] = (level is not None and level >= ALERT_THRESHOLD)

                # Push an event for listeners
                payload = {
                    "bin_id": bin_id,
                    "name": info.get("name"),
                    "level": level,
                    "is_alert": info["is_alert"],
                    "timestamp": int(timestamp)
                }
                # Put latest event in queue (non-blocking)
                try:
                    event_queue.put_nowait(payload)
                except Exception:
                    pass

            time.sleep(POLL_INTERVAL)
    except Exception:
        app.logger.exception("Sensor polling thread terminated unexpectedly.")


@app.route("/api/level", methods=["GET"])
def get_single_level():
    """Return the main bin's level (for single-bin simple dashboards)."""
    # choose first bin by insertion order
    first_key = next(iter(BINS))
    info = BINS[first_key]
    response = {
        "bin_id": first_key,
        "name": info.get("name"),
        "level": info.get("last_level"),
        "is_alert": info.get("is_alert"),
        "last_update": info.get("last_update")
    }
    return jsonify(response)


@app.route("/api/bins", methods=["GET"])
def get_all_bins():
    """Return all bins with latest cached values."""
    result = {}
    for bin_id, info in BINS.items():
        result[bin_id] = {
            "name": info.get("name"),
            "level": info.get("last_level"),
            "is_alert": info.get("is_alert"),
            "last_update": info.get("last_update")
        }
    return jsonify(result)


def sse_format(event: dict):
    """Format a JSON-serializable dict as SSE data."""
    data = json.dumps(event)
    return f"data: {data}\n\n"


@app.route("/stream")
def stream():
    """
    Server-Sent Events endpoint. Clients can connect and receive JSON events in real-time.
    Example JS in client:
      const es = new EventSource('/stream');
      es.onmessage = (e) => { const data = JSON.parse(e.data); ... }
    """
    def event_stream():
        # Send an initial snapshot of all bins
        snapshot = {"type": "snapshot", "bins": {
            k: {
                "name": v["name"],
                "level": v["last_level"],
                "is_alert": v["is_alert"],
                "last_update": v["last_update"]
            } for k, v in BINS.items()
        }}
        yield sse_format(snapshot)

        # Then stream live events from queue
        while True:
            try:
                event = event_queue.get()
                wrapped = {"type": "update", "data": event}
                yield sse_format(wrapped)
            except GeneratorExit:
                break
            except Exception:
                continue

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")


# Optional: endpoint to manually trigger test alerts / simulate levels
@app.route("/api/simulate/<bin_id>/<float:level>", methods=["POST"])
def simulate_level(bin_id, level):
    if bin_id not in BINS:
        return jsonify({"error": "unknown bin id"}), 404
    info = BINS[bin_id]
    info["last_level"] = float(level)
    info["last_update"] = time.time()
    info["is_alert"] = level >= ALERT_THRESHOLD
    payload = {
        "bin_id": bin_id,
        "name": info.get("name"),
        "level": info.get("last_level"),
        "is_alert": info["is_alert"],
        "timestamp": int(info["last_update"])
    }
    try:
        event_queue.put_nowait(payload)
    except Exception:
        pass
    return jsonify({"ok": True, "bin": bin_id, "level": level})


if __name__ == "__main__":
    # Start background polling thread
    poller = threading.Thread(target=poll_sensors, daemon=True)
    poller.start()

    # For production, use gunicorn/uvicorn or a WSGI server. Flask dev server is okay for testing.
    app.run(host="0.0.0.0", port=5000, debug=True)
