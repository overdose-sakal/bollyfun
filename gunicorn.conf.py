# gunicorn.conf.py

# A single synchronous worker is generally efficient for simple webhook setups.
workers = 1 

# Instruct Gunicorn to bind to the address and port provided by Render (0.0.0.0 is all interfaces).
bind = '0.0.0.0:8000' 

# Set a reasonable timeout for handling requests.
timeout = 30