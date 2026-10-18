#!/bin/sh
set -eu
python manage.py wait_for_database
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn --config gunicorn.conf.py config.wsgi:application
