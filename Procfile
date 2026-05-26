web: cd backend && python manage.py migrate --noinput && python seed_data.py 2>/dev/null || true && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
