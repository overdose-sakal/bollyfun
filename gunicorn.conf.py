# gunicorn.conf.py (UPDATED)

# worker_class = 'uvicorn.workers.UvicornWorker' # REMOVE OR COMMENT OUT THIS LINE
workers = 1
bind = '0.0.0.0:8000'
timeout = 120
keepalive = 5