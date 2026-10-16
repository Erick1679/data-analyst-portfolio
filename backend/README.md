# The Brights Analytics: Independent Django Prototype

Separate from the existing live static Netlify site and the old redirect branch.
Do not deploy this prototype publicly until the production security checklist is complete.

## Local setup (Mac)

```bash
cd ~/Coding/data-analyst-portfolio/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py makemigrations analytics
python manage.py migrate
python manage.py createsuperuser
python manage.py test
python manage.py runserver
```

Dashboard: http://127.0.0.1:8000/
Private admin: http://127.0.0.1:8000/admin/

## Data licensing and imports

Create a DataSource in admin with publisher and usage rights notes.
Publication and commercial use approval switches are OFF by default.
Only use properly licensed, non-personal, aggregate county datasets.
Example local CSV header: county,indicator,period,value,unit
Dates use YYYY-MM-DD format.

```bash
python manage.py import_county_csv /path/to/approved_dataset.csv --source-id 1
```

Imported data remains hidden until you deliberately approve its source.
The dashboard reads published data from the backend once per minute.
Actual automatic external ingestion, scheduling and licence checks require a later module.
Some KNBS data repository items are non-commercial by default: verify rights before selling derived products.

## Security before hosting

Set DJANGO_DEBUG=0, DJANGO_SECRET_KEY to a long unique secret, and
DJANGO_ALLOWED_HOSTS to the actual domain. Configure HTTPS termination,
CSRF origins where needed, a secure web server and recurring backups.
Do not commit .env, SQLite databases or uploaded client files.
Implement privacy notices, retention rules and consent records before public forms.

## SMS

No unsolicited telephone-number harvesting or sending is implemented.
Future bulk SMS must use opted-in contacts, opt-out handling, compliant sender IDs,
and a connected Kenyan SMS provider; operator message fees still apply.

## Future milestones

1. Permissioned ingestion connectors plus a scheduled task runner.
2. Live analytics products, source freshness labels and QA alerts.
3. Replace external booking forms with secure Django-native forms.
4. Production deployment with independent hosting and backups.
5. Consent-based bulk SMS and payment integration.
