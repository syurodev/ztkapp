from flask import Blueprint, Response
from zkteco.events import events_queue
from zkteco.services.live_capture_service import start_live_capture_thread
import json
from queue import Empty

bp = Blueprint('live_events', __name__, url_prefix='/')

@bp.route('/live-events')
def live_events():

    start_live_capture_thread()

    def event_stream():
        try:
            # Send a confirmation event immediately to the client
            yield "event: connected\ndata: Connection established\n\n"
            while True:
                try:
                    # Wait for an event, but with a timeout to avoid blocking forever
                    data = events_queue.get(timeout=5)
                    yield f"event: attendance\ndata: {json.dumps(data)}\n\n"
                except Empty:
                    # No new attendance data, send a heartbeat to keep the connection alive
                    yield "event: heartbeat\ndata: ping\n\n"
        except GeneratorExit:
            # This block is executed when the client disconnects
            pass

    return Response(event_stream(), mimetype="text/event-stream")
