from django.urls import path
from . import views
urlpatterns=[
 path('',views.dashboard,name='dashboard'),path('requirements/new/',views.new_requirement,name='new_requirement'),
 path('requirements/<int:pk>/',views.requirement_detail,name='requirement_detail'),path('requirements/<int:pk>/upload/',views.upload_csv,name='upload_csv'),
 path('batches/<int:pk>/',views.batch_detail,name='batch_detail'),path('batches/<int:pk>/selection/',views.update_selection,name='update_selection'),path('batches/<int:pk>/process/',views.process_batch,name='process_batch'),
 path('candidates/<int:pk>/retry/',views.retry_candidate,name='retry_candidate'),path('activity/',views.activity,name='activity'),path('reports/',views.report,name='report'),
 path('sync/<int:org_id>/',views.sync_ceipal_now,name='sync_ceipal_now'),path('signalhire/callback/<str:secret>/<int:candidate_id>/',views.signalhire_callback,name='signalhire_callback'),
]
