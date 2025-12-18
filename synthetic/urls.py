from django.urls import path

from . import views

app_name = 'synthetic'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('generate/', views.upload_view, name='generate'),
    path('history/', views.history_view, name='history'),
    path('api/stage-upload/', views.api_stage_upload, name='api-stage-upload'),
    path('api/finalize-metadata/', views.api_finalize_metadata, name='api-finalize-metadata'),
    path('api/start-run/', views.api_start_run, name='api-start-run'),
    path('api/run-status/<str:token>/', views.api_job_status, name='api-run-status'),
    path('api/dataset/<str:token>/', views.api_dataset_view, name='api-dataset'),
    path('result/<str:token>/', views.result_view, name='result'),
    path('download/<str:token>/', views.download_view, name='download'),
    path('download/plot/<str:token>/', views.download_plot, name='download-plot'),
]
