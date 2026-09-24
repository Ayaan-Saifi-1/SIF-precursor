import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from core.models import Report

class Command(BaseCommand):
    help = "Run migrations, load existing data, and create superuser from environment variables"

    def handle(self, *args, **options):
        # 1. Run migrations
        self.stdout.write("Running migrations...")
        call_command("migrate", interactive=False)

        # 2. Seed initial core data (cut-copy-paste of current state)
        fixture_path = Path(__file__).resolve().parents[3] / "core_data.json"
        if fixture_path.exists() and Report.objects.count() == 0:
            self.stdout.write(f"Database is empty. Loading data from {fixture_path.name}...")
            try:
                call_command("loaddata", str(fixture_path))
                self.stdout.write(self.style.SUCCESS(f"Successfully loaded {Report.objects.count()} reports into database."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not load fixture: {e}. Falling back to demo seed..."))
                call_command("seed_demo", rules_only=True)
        else:
            self.stdout.write(f"Database already contains {Report.objects.count()} reports.")

        # 3. Create or update superuser from environment variables
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", f"{username}@ascension.internal" if username else "admin@ascension.internal")

        if username and password:
            User = get_user_model()
            if not User.objects.filter(username=username).exists():
                User.objects.create_superuser(username=username, email=email, password=password)
                self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
            else:
                user = User.objects.get(username=username)
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Updated password and permissions for superuser '{username}'."))
        else:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD not set. Skipping superuser creation.")

        self.stdout.write(self.style.SUCCESS("Deployment setup complete!"))
