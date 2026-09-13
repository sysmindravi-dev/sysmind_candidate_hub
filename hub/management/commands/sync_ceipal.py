from django.core.management.base import BaseCommand
from hub.models import CeipalOrganization
from hub.services.sync import sync_org
class Command(BaseCommand):
    help='Synchronize CEIPAL Applicant metadata into the local matching index.'
    def add_arguments(self,p): p.add_argument('--org',help='Organization code, e.g. us or india')
    def handle(self,*args,**o):
        qs=CeipalOrganization.objects.filter(active=True)
        if o.get('org'): qs=qs.filter(code=o['org'])
        for org in qs:
            n=sync_org(org); self.stdout.write(self.style.SUCCESS(f'{org.code}: {n} applicants synchronized'))
