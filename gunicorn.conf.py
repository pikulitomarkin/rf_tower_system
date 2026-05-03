import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 2
threads = 2
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
worker_class = "sync"
loglevel = "info"
accesslog = "-"
errorlog = "-"
graceful_timeout = 30

preload_app = False
