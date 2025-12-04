#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python3 manage.py collectstatic --no-input

# Run migrations
python3 manage.py migrate --noinput

# Create superuser ONLY if it doesn't exist
python3 manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='sakal').exists():
    User.objects.create_superuser('sakal', 'sakalytshit@gmail.com', 'Salibill1')
    print('✅ Superuser created')
else:
    print('ℹ️ Superuser already exists')
EOF