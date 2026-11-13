from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import never_verified_users


class Command(BaseCommand):
    help = 'Delete inactive accounts that have never completed registration verification and are older than 24 hours.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report matching accounts without deleting them.',
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=24)
        accounts = never_verified_users().filter(date_joined__lt=cutoff)
        count = accounts.count()

        if options['dry_run']:
            self.stdout.write(f'Dry run: {count} unverified account(s) would be deleted.')
            return

        accounts.delete()
        self.stdout.write(f'Deleted {count} unverified account(s).')
