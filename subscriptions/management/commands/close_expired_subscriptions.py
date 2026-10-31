"""
python manage.py close_expired_subscriptions [--date YYYY-MM-DD]

Closes Active/Paused subscriptions past their expiry date whose plan has
auto_close, and reverts expired quotations to Draft. Uses the same service
functions as the API, so the rules live in one place (services.py).
Schedule it daily (Task Scheduler / cron).
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from subscriptions import services


class Command(BaseCommand):
    help = "Close expired auto-close subscriptions and revert expired quotations to Draft."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Treat this date (YYYY-MM-DD) as today. Default: today.")

    def handle(self, *args, **options):
        today = None
        if options["date"]:
            try:
                today = date.fromisoformat(options["date"])
            except ValueError:
                raise CommandError("--date must look like 2026-10-31.")

        expired_quotes = services.expire_quotations()
        closed = services.close_expired_subscriptions(today=today)

        self.stdout.write(f"Quotations reverted to draft: {expired_quotes}")
        self.stdout.write(self.style.SUCCESS(f"Subscriptions closed: {len(closed)}"))
        for number in closed:
            self.stdout.write(f"  {number}")
