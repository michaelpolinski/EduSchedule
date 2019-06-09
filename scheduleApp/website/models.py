from _ctypes import ArgumentError
from _operator import concat
from datetime import timedelta
import datetime
import json

from cuser.models import AbstractCUser, CUserManager
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, \
    validate_email
from django.db import models
from django.db.models.fields import related
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from timezone_field.fields import TimeZoneField

from scheduleApp import settings


class Institution(models.Model):
    # should be json-formatted tuples like '["a", "b"]'
    approvedStudentEmailDomains = models.CharField(max_length = 2000, default = '[]')
    approvedTeacherEmailDomains = models.CharField(max_length = 2000, default = '[]')
    autoApproveTeachers = models.BooleanField('Automatically approve teachers', default = False)

    # isSuspended = models.BooleanField('Suspend institution', default = False)
    isVerified = models.BooleanField('Administrator/institution identity verified?', default = False)
    name = models.CharField(verbose_name = 'Institution name', max_length = 200)
    streetAddress = models.CharField(verbose_name = 'Institution street address', max_length = 200)
    cityState = models.CharField(verbose_name = 'Institution city,state/province', max_length = 200)
    zipcode = models.IntegerField(verbose_name = 'Institution zip code', validators = [MaxValueValidator(99999), MinValueValidator(1)])
    timezone = TimeZoneField(default = 'US/Central')

    def __str__(self):
        return self.name

    def get_approved_domains(self, usertype):
        if usertype == 1:
            domains = json.loads(self.approvedTeacherEmailDomains)
            return [d for d in domains if d.strip()]
        elif usertype == 2:
            domains = json.loads(self.approvedStudentEmailDomains)
            return [d for d in domains if d.strip()]
        elif usertype == 0:
            return []
        else:
            raise IndexError("usertype not between 0 and 2")
        # json.dumps(var, separators=(',',":"))

    def validate_email(self, email, usertype):
        validate_email(email)
        if User.objects.filter(email = email).__len__() != 0:
            raise ValidationError("This email address is already in use.")
        domains = self.get_approved_domains(usertype)
        domain = email.split('@')[1]
        if domains and (domain not in domains):
            raise ValidationError("This email address is not on a domain permitted by the institution administrator.")
        return True


class UserManager(CUserManager):

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('userType', 0)
        if len(Institution.objects.filter(name = "Test Institution")) == 0:
            institution = Institution(name = "Test Institution", streetAddress = "Nonexistent Street", cityState = "Chicago, IL", zipcode = 69900)
            institution.save()
        else:
            institution = Institution.objects.get(name = "Test Institution")
        extra_fields.setdefault('institution', institution)

        return super().create_superuser(email, password, **extra_fields)


class User(AbstractCUser):
    isEmailConfirmed = models.BooleanField('Email address confirmed', default = False)
    institution = models.ForeignKey(Institution, on_delete = models.CASCADE)
    userType = models.SmallIntegerField('User type', choices = ((0, ("School Administrator")), (1, ("Teacher")), (2, ("Student")),))
    # defaultAppointmentLength = models.DurationField('Default appointment length', default = datetime.timedelta(minutes = 20))
    # defaultAppointmentTime = models.TimeField('Default appointment time', default = datetime.time(12, 0, 0))
    # use24HourTime = models.BooleanField('Use 24-hour time format', default = False)
    # reminderTimeBeforeAppointment = models.DurationField('Remind me _ before my appointment starts', default = datetime.timedelta(minutes = 15))
    # needs to be dealt with somehow. Cron job?

    defaultLocation = models.CharField(verbose_name = 'Default location for meetings', max_length = 200, default = "unspecified")
    minAppointmentTimespan = models.DurationField('Enforced minimum meeting duration', default = datetime.timedelta(minutes = 0))
    maxAppointmentTimespan = models.DurationField('Enforced maximum meeting duration', default = datetime.timedelta(hours = 12))
    showUnavailability = models.BooleanField('Show to students when I am unavailable', default = False)
    isTeacherApprovedByAdministrator = models.BooleanField('Teacher approved to join institution by the institution administrator?', default = False)

    # user notification settings (all boolean), email/web/mobile. By default, web/mobile notifications are all on; email notifications are all off.
    # notifyTeacherSignupEmail = models.BooleanField('Notify of new teacher signup requests at my institution by EMAIL notification', default = False)
    notifyTeacherSignupWeb = models.BooleanField('Notify of new teacher signup requests at my institution', default = True)
    # notifyTeacherSignupMobile = models.BooleanField('Notify of new teacher signup requests at my institution by MOBILE PUSH notification', default = True)
    # notifyAppointmentApprovedChangedCancelledEmail = models.BooleanField('Notify of approved, changed, or cancelled appointments by EMAIL notification', default = False)
    notifyAppointmentApprovedChangedCancelledWeb = models.BooleanField('Notify of approved, changed, or cancelled appointments', default = True)
    # notifyAppointmentApprovedChangedCancelledMobile = models.BooleanField('Notify of approved, changed, or cancelled appointments by MOBILE PUSH notification', default = True)
    # notifyAppointmentUpcomingEmail = models.BooleanField('Notify of upcoming appointments by EMAIL notification', default = False)
    notifyAppointmentUpcomingWeb = models.BooleanField('Notify of upcoming appointments', default = True)
    # notifyAppointmentUpcomingMobile = models.BooleanField('Notify of upcoming appointments by MOBILE PUSH notification', default = True)
    # notifyAppointmentRequestedEmail = models.BooleanField('Notify of student appointment requests by EMAIL notification', default = False)
    notifyAppointmentRequestedWeb = models.BooleanField('Notify of student appointment requests', default = True)
    # notifyAppointmentRequestedMobile = models.BooleanField('Notify of student appointment requests by MOBILE PUSH notification', default = True)
    # notifyAppointmentCommentEmail = models.BooleanField('Notify of comments by EMAIL notification', default = False)
    notifyAppointmentCommentWeb = models.BooleanField('Notify of comments', default = True)
    # notifyAppointmentCommentMobile = models.BooleanField('Notify of comments by MOBILE PUSH notification', default = True)

    def __str__(self):
        return concat(concat(self.first_name, " "), self.last_name)

    def send_activation_email(self, request):
        current_site = get_current_site(request)
        account_activation_token = AccountActivationTokenGenerator()
        subject = 'Complete your EduSchedule registration'
        message = render_to_string('website/account_activation_email.html', {
            'protocol': request.scheme,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(self.pk)),
            'token': account_activation_token.make_token(self),
        })
        self.email_user(subject, message)

    def get_appointments(self, time_begin = None, time_end = None, exclude_cancelled = False):
        usertype = self.userType
        tz = self.institution.timezone
        timezone.activate(tz)
        if time_begin is None or time_end is None or time_begin >= time_end:
            raise ArgumentError('Invalid time_begin or time_end')
            # time_begin = timezone.now()
            # time_end = timezone.now() + timedelta(days = 14)
        if usertype == 1:
            appointments = Appointment.objects.filter(teacher = self, startTime__lt = time_end, endTime__gt = time_begin)
            if exclude_cancelled:
                appointments = appointments.exclude(cancelled = True)
        elif usertype == 2:
            appointments = Appointment.objects.filter(student = self, startTime__lt = time_end, endTime__gt = time_begin)
            if exclude_cancelled:
                appointments = appointments.exclude(cancelled = True)
        else:
            return "Error - user is not a student or teacher."
        return appointments

    # returns appointments that overlap with the given begin and end time only if the user does not have showUnavailability set to True
    def get_overlapping_appointments(self, time_begin, time_end, exclude = None):
        appointments = self.get_appointments(time_begin, time_end, exclude_cancelled = True)
        if exclude is not None:
            appointments = appointments.exclude(pk = exclude.pk)
        if appointments.__len__() == 0:
            return None
        return appointments

    def get_overlapping_appointments_other(self, *args, **kwargs):
        if self.showUnavailability:
            return self.get_overlapping_appointments(*args, **kwargs)
        else:
            return None

    objects = UserManager()


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):

    def _make_hash_value(self, user, timestamp):
        login_timestamp = '' if user.last_login is None else user.last_login.replace(microsecond = 0, tzinfo = None)
        return (
            str(user.pk) +
            user.password +
            str(timestamp) +
            str(user.is_active) +
            str(login_timestamp) +
            str(user.isEmailConfirmed)
        )


class Appointment(models.Model):
    student = models.ForeignKey(User, on_delete = models.CASCADE, related_name = 'student')
    teacher = models.ForeignKey(User, on_delete = models.CASCADE, related_name = 'teacher')
    startTime = models.DateTimeField('Start time')
    endTime = models.DateTimeField('End time')  # should never be the following day
    previousStartTime = models.DateTimeField('Previously stored appointment start time', null = True, blank = True)
    previousEndTime = models.DateTimeField('Previously stored appointment end time', null = True, blank = True)
    teacherConfirmed = models.BooleanField('Teacher approved appointment details', default = False)
    studentConfirmed = models.BooleanField('Student approved appointment details', default = True)
    location = models.CharField(verbose_name = 'Location', max_length = 200)
    previousLocation = models.CharField(verbose_name = 'Previously stored appointment location', max_length = 200, null = True, blank = True)
    cancelled = models.BooleanField('Appointment cancelled', default = False)

    def __str__(self):
        return concat(concat(concat("Appointment by ", self.student.__str__()), " with "), self.teacher.__str__())


class Comment(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete = models.CASCADE)
    user = models.ForeignKey(User, on_delete = models.CASCADE)
    message = models.TextField('Comment', max_length = 2000)

    def __str__(self):
        return self.message


class AppointmentNotification(models.Model):
    datetime = models.DateTimeField(default = timezone.now)
    user = models.ForeignKey(User, on_delete = models.CASCADE)
    appointment = models.ForeignKey(Appointment, on_delete = models.CASCADE)
    event = models.PositiveSmallIntegerField(choices = ((0, ("Approved")), (1, ("Changed")), (2, ("Cancelled")), (3, ("Upcoming")), (4, ("Requested")), (5, ("Comment")),))

    def __str__(self):
        tz = self.user.institution.timezone
        timezone.activate(tz)
        return "Notification for " + self.user.__str__() + " regarding event " + self.event.__str__() + " for " + self.appointment.__str__()

    def notification_title(self):
        if self.event == 0:
            if self.user.userType == 1:
                return "Appointment changes confirmed"
            elif self.user.userType == 2:
                return "Appointment confirmed"
        elif self.event == 1:
            return "Appointment change requested"
        elif self.event == 2:
            return "Appointment cancelled"
        elif self.event == 3:
            return "Upcoming appointment"
        elif self.event == 4:
            return "Appointment requested"
        elif self.event == 5:
            return "New comment"

    def notification_text(self):
        tz = self.user.institution.timezone
        timezone.activate(tz)
        if self.event == 0:
            if self.user.userType == 1:
                return self.appointment.student.__str__() + " confirmed your proposed appointment time and location"
            elif self.user.userType == 2:
                return self.appointment.teacher.__str__() + " confirmed your appointment request"
        elif self.event == 1:
            if self.user.userType == 1:
                return self.appointment.student.__str__() + " requested to change an appointment time"
            elif self.user.userType == 2:
                if self.appointment.previousLocation is None:
                    return self.appointment.teacher.__str__() + " changed the appointment time"
                elif self.appointment.previousStartTime is None and self.appointment.previousEndTime is None:
                    return self.appointment.teacher.__str__() + " changed the appointment location"
                else:
                    return self.appointment.teacher.__str__() + " changed the appointment time and location"
        elif self.event == 2:
            if self.user.userType == 1:
                return self.appointment.student.__str__() + " cancelled an appointment"
            elif self.user.userType == 2:
                return self.appointment.teacher.__str__() + " cancelled an appointment"
        elif self.event == 3:
            return "You have an appointment scheduled from " + self.appointment.startTime.date().__str__() + " to " + self.appointment.endTime.date().__str__()
        elif self.event == 4:
            return self.appointment.student.__str__() + " requested a new appointment for " + self.appointment.startTime.date().__str__()
        elif self.event == 5:
            if self.user.userType == 1:
                return self.appointment.student.__str__() + " commented on a scheduled appointment"
            elif self.user.userType == 2:
                return self.appointment.teacher.__str__() + " commented on a scheduled appointment"


class UserNotification(models.Model):
    datetime = models.DateTimeField(default = timezone.now)
    user = models.ForeignKey(User, on_delete = models.CASCADE, related_name = 'user')
    target_user = models.ForeignKey(User, on_delete = models.CASCADE, related_name = 'target_user')

    def __str__(self):
        tz = self.user.institution.timezone
        timezone.activate(tz)
        return "Request for " + self.user.__str__() + " to approve " + self.target_user.__str__() + " as a teacher at " + self.user.institution.__str__()

    def notification_text(self):
        return "would like to join " + self.user.institution.__str__() + " as a teacher."

    def notification_title(self):
        return self.target_user.__str__()
