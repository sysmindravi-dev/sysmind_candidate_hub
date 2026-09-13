import time
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hub.models import BackgroundTask, ImportCandidate
from hub.services.processing import process_with_signalhire
class Command(BaseCommand):
    help='Processes lightweight background tasks, including SignalHire async callbacks.'
    def add_arguments(self,p): p.add_argument('--once',action='store_true')
    def handle(self,*args,**o):
        while True:
            task=None
            with transaction.atomic():
                task=BackgroundTask.objects.select_for_update(skip_locked=True).filter(status='PENDING',available_at__lte=timezone.now()).first()
                if task: task.status='RUNNING'; task.locked_at=timezone.now(); task.attempts+=1; task.save()
            if task:
                try:
                    if task.task_type=='FINALIZE_SIGNALHIRE':
                        c=ImportCandidate.objects.get(pk=task.payload['candidate_id']); process_with_signalhire(c,c.batch.uploaded_by,signalhire_result=task.payload['row'])
                    task.status='DONE'; task.save(update_fields=['status','updated_at'])
                except Exception as e:
                    task.status='FAILED'; task.error=str(e); task.save(update_fields=['status','error','updated_at'])
            elif o['once']: break
            else: time.sleep(3)
