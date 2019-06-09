from django.urls import path
from . import views

app_name = 'website'
urlpatterns = [
    path('', views.HomePage, name = 'homepage'),
    path('appointments/', views.MyAppointmentsView, name = 'myappointments'),
    path('appointments/approve/<int:pk>/', views.AppointmentApproveView, name = 'appointmentapprove'),
    path('appointments/edit/<int:pk>/', views.AppointmentEditView, name = 'appointmentedit'),
    path('appointments/comment/<int:pk>/', views.AppointmentCommentView, name = 'appointmentcomment'),
    path('appointments/cancel/<int:pk>/', views.AppointmentCancelView, name = 'appointmentcancel'),

    path('new_appointment/teacher/', views.NewAppointmentFindTeacherView, name = 'newappointmentteacher'),
    path('new_appointment/<int:pk>/', views.NewAppointmentView, name = 'newappointment'),
    path('new_appointment/', views.NewAppointmentRedirectView, name = 'newappointmentredirect'),

    path('my_institution/', views.MyInstitutionView, name = 'myinstitution'),
    path('my_institution/students/', views.MyInstitutionStudentsView, name = 'myinstitutionstudents'),
    path('my_institution/teachers/', views.MyInstitutionTeachersView, name = 'myinstitutionteachers'),
    path('my_institution/unapproved_teachers/', views.MyInstitutionUnapprovedView, name = 'myinstitutionunapproved'),
    path('my_institution/approve/<int:pk>/', views.MyInstitutionUserApproveView, name = 'myinstitutionapprove'),
    path('my_institution/edit/<int:pk>/', views.MyInstitutionUserEditView, name = 'myinstitutionedit'),
    path('my_institution/delete/<int:pk>/', views.MyInstitutionUserDeleteView, name = 'myinstitutiondelete'),

    path('notifications/', views.NotificationsView, name = 'notifications'),
    path('notifications/delete/<int:pk>/', views.NotificationDeleteView, name = 'deletenotification'),

    path('settings/', views.SettingsView, name = 'settings'),
    path('institution_settings/', views.InstitutionSettingsView, name = 'institutionsettings'),

    path('my_account/', views.MyAccountView, name = 'myaccount'),
    path('my_account/delete/', views.DeleteAccountView, name = 'deleteaccount'),

    path('usertype/', views.UserTypeView, name = 'usertype'),
    path('find_institution/usertype/<int:usertype>/', views.FindInstitutionView, name = 'findinstitution'),
    path('register/', views.RegisterRedirectView, name = 'registerredirect'),
    path('register/usertype/0/', views.RegisterView, name = 'registeradmin'),
    path('register/usertype/<int:usertype>/institution/<int:institution_id>/', views.RegisterView, name = 'register'),
    path('register_verify/<uidb64>/<token>/', views.ActivateView, name = 'activate'),
]
