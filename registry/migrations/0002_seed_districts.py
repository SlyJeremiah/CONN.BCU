from django.db import migrations

DISTRICTS = ["Harare East", "Harare West", "Kadoma", "Marondera", "Hwange", "Masvingo", "Bulawayo", "Kwekwe"]


def seed(apps, schema_editor):
    District = apps.get_model("registry", "District")
    for name in DISTRICTS:
        District.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("registry", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
