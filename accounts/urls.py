from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('verify/<str:token>/', views.verify_email_view, name='verify-email'),
    path('google/', views.google_login_view, name='google-login'),
    path('google/callback/', views.google_callback_view, name='google-callback'),
]
