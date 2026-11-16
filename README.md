# BCU National Database

A private countrywide register for the **Boys Christian Union (BCU)** of **The Methodist Church in Zimbabwe**.
It is a separate system from the BCU Shop (own app, own database). The shop section can be added later as another app in this project.

Stack: Django 5, Postgres (Neon) in production, SQLite locally, Django admin as the data-entry screen.

## What it holds

| Area | Records |
|---|---|
| Structure | Districts (the 8 are pre-loaded), circuits, societies |
| People | Members (name, date of birth, society, guardian, consent, status) |
| Leaders | Office bearers at national, district, circuit and society level, with terms |
| Finance | Levies per district per year, and each payment received (2027 levies are pre-loaded: 840 in total) |

Structure: **Connexion → District → Circuit → Society → Member.**

## Who can do what

| Role | Sees | Can change |
|---|---|---|
| **National officer** | Every district | Everything, including districts, levy payments and logins |
| **District officer** | Only their own district | Circuits, societies, members and leaders in that district. Views their levy. Cannot delete records, add districts, record payments or create national posts |
| Login with no access set | Nothing | Nothing |

Access is enforced on the server for every list, record page, dropdown, CSV export and the dashboard. A district officer who types another district's record address gets "does not exist". The rules are covered by tests (`python manage.py test`).

Create a login in **Users**, then fill in the **Access** section: role and, for a district officer, the district. Saving it makes the login a staff user in the right group automatically.

## Personal data (read this)

Most members are under 18, so this register holds children's data.
- Members under 18 must have a guardian name and phone number (the form will not save otherwise) and a **consent** tick. The dashboard shows how many active members have no recorded consent.
- Collect only what is needed. There is no national ID, address or photo field on purpose.
- Everything is behind a login. There are no public pages. Sessions end after 8 hours, and passwords must be at least 10 characters.
- Records are retired by setting a status (inactive, transferred, moved to the Men's Christian Union), not deleted. Only national officers can delete.
- Every add, change and delete is written to the admin history.
- CSV export is available on lists, scoped to what the officer can see. Treat exported files as confidential.
- Zimbabwe's Cyber and Data Protection Act applies. Have the church decide who is the data controller and register if required.

## Run it locally

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://localhost:8000/ and log in. `python manage.py test` runs the tests.

## Deploy (Vercel + Neon)

1. Create a **new** Neon database for this system (do not reuse the shop's): Neon > your project > Databases > New database, then copy its connection string.
2. In Vercel, import `SlyJeremiah/CONN.BCU` and add these environment variables (see `.env.example`):
   `DATABASE_URL` (the new Neon string), `DJANGO_SECRET_KEY` (long, random), `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=.vercel.app`, `CSRF_TRUSTED_ORIGINS=https://*.vercel.app`.
3. Once, against that database: `python manage.py migrate`, then `python manage.py create_national_officers` (prints one-time starting passwords).
4. After changing any CSS or JS: `DJANGO_DEBUG=0 python manage.py collectstatic --noinput` and commit `staticfiles/`.

## Logins

`python manage.py create_national_officers` creates **Connexional Minister In Charge**, **Connexional Treasurer** and **Connexional Secretary** as national officers with starting passwords that must be changed at first login.
National officers then add district admins and other Connexional executives in **Users** (Access section), with no code.

## Next steps

- Bulk import of members and societies from spreadsheets (CSV import with a template).
- A district officer view of their levy status on a phone.
- The shop section, as a further app.
