import secrets

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from registry.models import Profile

OFFICERS = [
    ("conn.minister", "Connexional Minister In Charge"),
    ("conn.treasurer", "Connexional Treasurer"),
    ("conn.secretary", "Connexional Secretary"),
]


class Command(BaseCommand):
    help = "Create the three Connexional logins with one-time starting passwords (each must change theirs at first login)."

    def add_arguments(self, parser):
        for username, _ in OFFICERS:
            parser.add_argument(f"--{username.split('.')[1]}-email", default="", help=f"Email for {username}")

    def handle(self, *args, **opts):
        self.stdout.write("")
        for username, title in OFFICERS:
            email = opts[f"{username.split('.')[1]}_email"]
            user, created = User.objects.get_or_create(username=username, defaults={"email": email, "last_name": title})
            if not created:
                self.stdout.write(f"{username}: already exists, left unchanged")
                continue
            password = secrets.token_urlsafe(12)
            user.set_password(password)
            user.save()
            Profile.objects.create(user=user, role=Profile.NATIONAL, must_change_password=True)
            self.stdout.write(self.style.SUCCESS(f"{title}\n    username: {username}\n    starting password: {password}\n"))
        self.stdout.write("Share each password privately. It works once: they must choose their own at first login.")
