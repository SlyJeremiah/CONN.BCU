import datetime

from django.db import migrations

# 2027 district levies from the Connexional Budget 2027 (total 840), payable by June 2027.
LEVIES_2027 = {"Harare East": 150, "Harare West": 150, "Kadoma": 100, "Marondera": 80,
               "Hwange": 100, "Masvingo": 80, "Bulawayo": 100, "Kwekwe": 80}


def seed(apps, schema_editor):
    District = apps.get_model("registry", "District")
    Levy = apps.get_model("finance", "LevyAssessment")
    for name, amount in LEVIES_2027.items():
        d = District.objects.get(name=name)
        Levy.objects.get_or_create(district=d, year=2027, defaults={"amount": amount, "due_date": datetime.date(2027, 6, 30)})


class Migration(migrations.Migration):
    dependencies = [("finance", "0001_initial"), ("registry", "0002_seed_districts")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
