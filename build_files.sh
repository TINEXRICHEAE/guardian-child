#!/bin/bash
set -e

pip install --break-system-packages -r requirements.txt

export DJANGO_SETTINGS_MODULE=pita.settings
export PYTHONPATH="${PYTHONPATH}:$(pwd)/pita"

cd pita
python manage.py migrate --noinput
python manage.py collectstatic --noinput
cd ..

mkdir -p staticfiles_build/static
cp -r pita/staticfiles/. staticfiles_build/static/
