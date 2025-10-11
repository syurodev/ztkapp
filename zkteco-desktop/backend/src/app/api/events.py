from flask import Blueprint, Response, current_app
from app.events import device_event_stream
from app.shared.logger import app_logger
import json
from queue import Empty

bp = Blueprint('live_events', __name__, url_prefix='/')

@bp.route('/live-events')
def live_events():
    """
    SSE endpoint for real-time attendance events.
    Works with both pull devices (via live_capture_service) and push devices (via push_protocol_service).
    """
    def event_stream():
        # Subscribe to the device event stream
        subscriber_queue = device_event_stream.subscribe()

        try:
            # Send a confirmation event immediately to the client
            yield "event: connected\ndata: Connection established\n\n"
            app_logger.info("[SSE] Client connected to /live-events")

            while True:
                try:
                    # Wait for an event, but with a timeout to avoid blocking forever
                    data = subscriber_queue.get(timeout=5)
                    yield f"event: attendance\ndata: {data}\n\n"
                except Empty:
                    # No new attendance data, send a heartbeat to keep the connection alive
                    yield "event: heartbeat\ndata: ping\n\n"
        except GeneratorExit:
            # This block is executed when the client disconnects
            app_logger.info("[SSE] Client disconnected from /live-events")
            device_event_stream.unsubscribe(subscriber_queue)
        except Exception as e:
            app_logger.error(f"[SSE] Error in event stream: {e}")
            device_event_stream.unsubscribe(subscriber_queue)

    return Response(event_stream(), mimetype="text/event-stream")
