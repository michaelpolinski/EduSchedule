from django.urls import path

from . import views

app_name = 'eduschedulesite'
urlpatterns = [
    path('', views.HomePage, name = 'home'),
    path('about/', views.AboutPage, name = 'about'),
    path('contact/', views.ContactPage, name = 'contact'),
    path('terms/', views.TermsPage, name = 'terms'),
    ]
