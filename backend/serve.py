# -*- coding: utf-8 -*-
"""Production entrypoint for PM2. Runs the Flask app (API + the built React
frontend, see FRONTEND_DIST in app.py) through waitress instead of Flask's
own dev server, since the dev server's debug/auto-reload behavior isn't
appropriate for a long-running process managed by a process supervisor."""
from waitress import serve

import config
from app import app

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=config.FLASK_PORT)
