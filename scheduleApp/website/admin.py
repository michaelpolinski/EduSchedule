from cuser.admin import UserAdmin
from django.contrib.admin import AdminSite
from django.utils.translation import ugettext_lazy as _
from ratelimitbackend import admin

from .models import User, Appointment, Comment, Institution, AppointmentNotification, UserNotification


class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'isEmailConfirmed', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Institution'), {'fields': ('institution', 'userType', 'isTeacherApprovedByAdministrator')})
        )


class CustomAdminSite(AdminSite):
    site_title = 'EduSchedule admin'
    site_header = 'EduSchedule server administration'
    index_title = 'EduSchedule administration'


custom_admin_site = CustomAdminSite()

custom_admin_site.register(User, CustomUserAdmin)
custom_admin_site.register(Appointment)
custom_admin_site.register(Comment)
custom_admin_site.register(Institution)
custom_admin_site.register(AppointmentNotification)
custom_admin_site.register(UserNotification)
