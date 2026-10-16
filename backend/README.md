# The Brights Analytics — Independent Worldwide Django Prototype

This Django foundation will eventually support a global analytics platform with
countries/territories, states, provinces, regions, counties, districts and cities.
Geography and statistical datasets are separate. A listed location does **not**
guarantee that any statistics are available for it.

The existing Netlify frontend and old-site redirect remain untouched.

## Local setup on a Mac

```bash
cd ~/Coding/data-analyst-portfolio/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py makemigrations analytics
python manage.py migrate
python manage.py createsuperuser
python manage.py test
python manage.py runserver
```

Preview: http://127.0.0.1:8000/
Private administrator panel: http://127.0.0.1:8000/admin/

## Worldwide geographic hierarchy

GeographicPlace uses a globally unique code and a flexible parent relationship.
A country/territory is a root with an ISO 3166-1 alpha-2 code. Examples:

- Kenya (KE) -> Nairobi County (KE-047) -> Nairobi City (KE-NRB-CITY)
- United States (US) -> California State (US-CA) -> Los Angeles (local code)

Codes for cities and other subnational areas are internal stable identifiers
unless explicitly sourced as recognised official standard codes. They are
not necessarily ISO 3166-2 codes. Some countries have no counties or states.

Sources such as ISO country lists, geoBoundaries, OpenStreetMap and GeoNames
may be considered for place reference records, **subject to their distinct
licences, attribution requirements, completeness and update policies**.
Do not assume public download rights equal unrestricted commercial reuse.

## Prepare geography and indicators

Create a DataSource in /admin/ with the publisher and reviewed licence notes.
Both publication and commercial reuse flags are OFF by default.

Import a vetted place CSV in parent-first order:

```text
code,name,place_type,parent_code
KE,Kenya,country,
KE-047,Nairobi County,county,KE
KE-NRB-CITY,Nairobi,city,KE-047
US,United States,country,
US-CA,California,state,US
```

```bash
python manage.py import_places_csv /path/to/approved_places.csv --source-id 1
```

Now import aggregate observations with verified data rights:

```text
place_code,indicator,period,value,unit
KE-047,Synthetic demonstration index,2026-01-01,10.25,index
```

```bash
python manage.py import_geographic_indicators /path/to/approved_aggregate.csv --source-id 2
```

Use synthetic test values only for demonstrations, and label them accordingly.
Imported observations are hidden until the source is approved for publication.
The data API is /api/indicators/?place=KE-047; geographic child lookup is
/api/places/?parent=KE. The dashboard refreshes the displayed published data
every minute, not the original data source itself.

## Scalability and future work

SQLite is suitable for this prototype and small local datasets. For many
cities, heavy querying, multiple workers or geospatial boundaries, plan a
migration to PostgreSQL/PostGIS with backups, indexes, caching, paging,
data provenance and source-specific ingestion jobs.

Next steps: permissioned bulk data imports, background scheduling, change
detection, charts/maps, searchable worldwide places, freshness reports,
licensed subscription analytics and consent-based customer services.

No SMS sending, marketing-number harvesting, subscriptions, live feeds,
payment system or automated scraping is included yet.

## Security before public deployment

Set DJANGO_DEBUG=0, a unique DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, HTTPS,
trusted origins as appropriate, secure backups and retention/access rules.
Never commit .env, database files or client uploads. Do not deploy this
prototype on the current static Netlify site: it does not host Django.

## Bulk-import ISO countries and territories

The free `pycountry` dependency supplies 249 ISO 3166-1 country/territory
records from Debian's `pkg-isocodes` database. Its package licence is
LGPL-2.1-only; confirm downstream licensing and attribution conditions
before any commercial redistribution of reference data.

Create a **new** DataSource in Django admin (do not reuse the internal manual
test reference source):

- Name: `ISO 3166-1 Countries — pycountry 26.2.16`
- Publisher: `pycountry / Debian pkg-isocodes`
- Source URL: `https://pypi.org/project/pycountry/`
- Licence notes: `pycountry 26.2.16 / Debian pkg-isocodes; package LGPL-2.1-only. ISO-based geographic reference; publication and commercial reuse are pending separate review.`
- Leave both publication and commercial approval boxes unchecked.

Then from the `backend` folder run the following, replacing `ID` with
its actual DataSource database ID:

```bash
python -m pip install -r requirements.txt
python manage.py import_iso_countries --source-id ID --dry-run
python manage.py import_iso_countries --source-id ID
```

The import leaves previously entered countries such as Kenya (KE) and
United States (US) unchanged, and is safe to run repeatedly. It adds only
country and territory reference entries, not statistics, cities or phone
numbers. Source usage rights and names require continued review.

## Kenya county numbering in the dashboard

Kenya's official county numbers are **001 Mombasa** through **047 Nairobi**
(see the [Government of Kenya county list](https://gok.kenya.go.ke/devolved-governments)
and the [Kenya Gazette](https://new.kenyalaw.org/akn/ke/officialGazette/gazette/2024-05-09/64/eng@2024-05-09/source)).

The geographic child API `/api/places/?parent=KE` orders counties by these
official numbers, with `county_number` and `display_name` fields like
`"001 — Mombasa"`. The dashboard uses the display label. Existing database
keys and source provenance remain untouched: `KE-01` in the ISO source is
Baringo, **not** Kenya's official County 001. This is a display crosswalk, not
a replacement of ISO identifiers. Other countries still sort alphabetically.


## Local authorities (separate from geographic places)

A `LocalAuthority` is an administrative institution (for example, a
district, town or city council). It is **not** a new district, city or
territory. Each authority records its name, country, council type, DataSource,
verification status (pending by default), optional notes, and an **optional**
geographic jurisdiction. Jurisdiction links are only for independently
verified relationships; the model validates that a linked place belongs to
the selected country.

Generate and apply the migration after updating the development branch:

```bash
python manage.py makemigrations analytics
python manage.py migrate
python manage.py test analytics
```

In Django admin, `Local authorities` can be maintained separately from
`Geographic places`. The Botswana 31-council review is held in
`reference_data/botswana_local_authorities_review.md`; its naming disputes
require resolution before importing council records. Local authorities are
**not exposed in the public API**, and creating them does not grant
publication or commercial reuse rights.
