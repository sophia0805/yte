# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:{}".format(int(os.environ.get("PORT", 5000)))
backlog = 2048

# Worker processes
# Use 1 worker for bot to avoid multiple bot instances
# Bots should only have one instance running
workers = 1
worker_class = "sync"
worker_connections = 1000
timeout = 120  # Increase timeout to 120 seconds (default is 30)
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "yts-bot"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None
