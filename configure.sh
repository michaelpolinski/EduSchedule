#!/bin/bash
virtualenv -p python3 venv
source venv/bin/activate
cd scheduleApp
pip install -r requirements.txt
cd scheduleApp
cp local_settings.py.debug.example local_settings.py
python make_key.py
cd ..
python manage.py collectstatic
python manage.py migrate
printf "All done! To start the testing server on localhost:8000, run\nsource venv/bin/activate && cd scheduleApp && python manage.py runserver\n"
