"""Gunicorn is used by the server image; start.sh remains a local dev launcher."""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
timeout = 60
accesslog = "-"
errorlog = "-"
# Django handles the gateway's scheme header only when TRUST_PROXY_HEADERS is set.
forwarded_allow_ips = ""

control_socket_disable = True
