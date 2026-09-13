from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from hub.models import SignalHireUsage
class Command(BaseCommand):
    help='Release stale SignalHire reservations older than 24 hours (for example, a lost async callback).'
    def handle(self,*args,**kwargs):
        qs=SignalHireUsage.objects.filter(status='RESERVED',created_at__lt=timezone.now()-timedelta(hours=24))
        n=qs.update(status='RELEASED')
        self.stdout.write(self.style.SUCCESS(f'Released {n} stale reservations.'))
