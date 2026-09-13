#!/bin/sh
set -e
python manage.py migrate --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 3 --threads 2 --timeout 90
