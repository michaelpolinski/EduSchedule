from datetime import timedelta, timezone
import json

from bootstrap_datepicker_plus import DateTimePickerInput
from captcha.fields import CaptchaField
from captcha.fields import CaptchaTextInput
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Fieldset, ButtonHolder, Div, HTML
from crispy_forms.templatetags.crispy_forms_field import css_class
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, validate_email, EmailValidator
from django.db.models.fields import DateTimeField
from django.forms import widgets
from django.forms.fields import SplitDateTimeField
from django.forms.widgets import PasswordInput, DateInput, \
    TimeInput, DateTimeInput, SplitDateTimeWidget, MultiWidget, CheckboxInput, \
    TextInput
from django.templatetags.l10n import localize

from scheduleApp import settings

from .models import Institution, User, Appointment


class UserTypeForm(forms.Form):
    usertype = forms.ChoiceField(choices = ((0, ("School Administrator")), (1, ("Teacher")), (2, ("Student")),), label = "I am a...", widget = forms.RadioSelect, required = True)


class FindInstitutionForm(forms.Form):
    zipcode = forms.IntegerField(label = "Zip code", validators = [MaxValueValidator(99999), MinValueValidator(1)], required = True, widget = forms.TextInput)


class FindTeacherForm(forms.Form):
    teacher_name = forms.CharField(required = True)

    def __init__(self, *args, **kwargs):
        super(FindTeacherForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', "Search", css_class = 'btn btn-primary'))


class NewAppointmentForm(forms.ModelForm):
    CUSTOM_FORMAT = '%m/%d/%Y %I:%M %p'
    schedule_overlapping_appointment_anyway = forms.BooleanField(widget = widgets.HiddenInput, required = False)

    class Meta:
        model = Appointment
        fields = ['startTime', 'endTime', ]
        widgets = {
            'startTime': DateTimePickerInput(options = {'format':'MM/DD/YYYY hh:mm a'}),
            'endTime': DateTimePickerInput(options = {'format':'MM/DD/YYYY hh:mm a'}),
            }
        help_texts = {
            'startTime':'MM/DD/YYYY hh:mm [am/pm]',
            'endTime':'MM/DD/YYYY hh:mm [am/pm]'
            }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        self.user = user
        target_user = kwargs.pop('target_user')
        self.target_user = target_user
        super(NewAppointmentForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', "Submit"))
        self.helper.include_media = False
        if self.CUSTOM_FORMAT not in self.fields['startTime'].input_formats:
            self.fields['startTime'].input_formats.append(self.CUSTOM_FORMAT)
        if self.CUSTOM_FORMAT not in self.fields['endTime'].input_formats:
            self.fields['endTime'].input_formats.append(self.CUSTOM_FORMAT)

    def clean(self):
        user = self.user
        target_user = self.target_user
        if not self.cleaned_data['startTime'].day == self.cleaned_data['endTime'].day:
            self.add_error('startTime', "The start and end time should not be on different calendar days.")
            self.add_error('endTime', "The start and end time should not be on different calendar days.")
            return self.cleaned_data
        elif not self.cleaned_data['startTime'] < self.cleaned_data['endTime']:
            self.add_error('endTime', "The start time should come before the end time.")
            self.add_error('startTime', "The start time should come before the end time.")
            return self.cleaned_data
        elif ((self.cleaned_data['endTime'] - self.cleaned_data['startTime']) > target_user.maxAppointmentTimespan):
            self.add_error('endTime', "Your teacher does not allow appointments longer than " + str((target_user.maxAppointmentTimespan.seconds // 60) % 60) + " minutes.")
            self.add_error('startTime', "Your teacher does not allow appointments longer than " + str((target_user.maxAppointmentTimespan.seconds // 60) % 60) + " minutes.")
            return self.cleaned_data
        elif ((self.cleaned_data['endTime'] - self.cleaned_data['startTime']) < target_user.minAppointmentTimespan):
            self.add_error('endTime', "Your teacher does not allow appointments shorter than " + str((target_user.minAppointmentTimespan.seconds // 60) % 60) + " minutes.")
            self.add_error('startTime', "Your teacher does not allow appointments shorter than " + str((target_user.minAppointmentTimespan.seconds // 60) % 60) + " minutes.")
            return self.cleaned_data
        overlap_target_user = target_user.get_overlapping_appointments_other(self.cleaned_data['startTime'], self.cleaned_data['endTime']) is not None
        overlap_user = user.get_overlapping_appointments(self.cleaned_data['startTime'], self.cleaned_data['endTime']) is not None
        if overlap_target_user or overlap_user:
            self.fields['schedule_overlapping_appointment_anyway'].widget = CheckboxInput()
            passed = False
            try:
                passed = self.cleaned_data['schedule_overlapping_appointment_anyway']
            except:
                passed = False
            if not passed:
                if overlap_target_user:
                    self.add_error('schedule_overlapping_appointment_anyway', target_user.__str__() + " has an overlapping appointment. Request the appointment anyway?")
                if overlap_user:
                    self.add_error('schedule_overlapping_appointment_anyway', "You have an overlapping appointment. Proceed?")
        return self.cleaned_data


class AppointmentEditForm(forms.ModelForm):
    CUSTOM_FORMAT = '%m/%d/%Y %I:%M %p'
    schedule_overlapping_appointment_anyway = forms.BooleanField(widget = widgets.HiddenInput, required = False)

    class Meta:
        model = Appointment
        fields = ['startTime', 'endTime', 'location', 'cancelled']
        widgets = {
            'startTime': DateTimePickerInput(options = {'format':'MM/DD/YYYY hh:mm a'}),
            'endTime': DateTimePickerInput(options = {'format':'MM/DD/YYYY hh:mm a'}),
            }

    def __init__(self, *args, **kwargs):
        usertype = kwargs.pop('usertype')
        self.usertype = usertype
        super(AppointmentEditForm, self).__init__(*args, **kwargs)
        if usertype == 2:
            self.fields.pop('location')
        if not self.instance.cancelled:
            self.fields.pop('cancelled')
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', "Save changes"))
        self.helper.include_media = False
        if self.CUSTOM_FORMAT not in self.fields['startTime'].input_formats:
            self.fields['startTime'].input_formats.append(self.CUSTOM_FORMAT)
        if self.CUSTOM_FORMAT not in self.fields['endTime'].input_formats:
            self.fields['endTime'].input_formats.append(self.CUSTOM_FORMAT)

    def clean(self):
        usertype = self.usertype
        if usertype == 1:
            target_user = Appointment.objects.get(pk = self.instance.pk).student
            user = Appointment.objects.get(pk = self.instance.pk).teacher
        elif usertype == 2:
            target_user = Appointment.objects.get(pk = self.instance.pk).teacher
            user = Appointment.objects.get(pk = self.instance.pk).student
        if not self.cleaned_data['startTime'].day == self.cleaned_data['endTime'].day:
            self.add_error('startTime', "The start and end time should not be on different calendar days.")
            self.add_error('endTime', "The start and end time should not be on different calendar days.")
            return self.cleaned_data
        elif not self.cleaned_data['startTime'] < self.cleaned_data['endTime']:
            self.add_error('endTime', "The start time should come before the end time.")
            self.add_error('startTime', "The start time should come before the end time.")
            return self.cleaned_data
        elif usertype == 2 and ((self.cleaned_data['endTime'] - self.cleaned_data['startTime']) > target_user.maxAppointmentTimespan):
            self.add_error('endTime', "Your teacher does not allow appointments longer than " + str((target_user.maxAppointmentTimespan.seconds // 60) % 60) + " minutes.")
            self.add_error('startTime', "Your teacher does not allow appointments longer than " + str((target_user.maxAppointmentTimespan.seconds // 60) % 60) + " minutes.")
            return self.cleaned_data
        elif usertype == 2 and ((self.cleaned_data['endTime'] - self.cleaned_data['startTime']) < target_user.minAppointmentTimespan):
            self.add_error('endTime', "Your teacher does not allow appointments shorter than " + str((target_user.minAppointmentTimespan.seconds // 60) % 60) + " minutes.")
            self.add_error('startTime', "Your teacher does not allow appointments shorter than " + str((target_user.minAppointmentTimespan.seconds // 60) % 60) + " minutes.")
            return self.cleaned_data
        overlap_target_user = target_user.get_overlapping_appointments_other(self.cleaned_data['startTime'], self.cleaned_data['endTime'], exclude = self.instance) is not None
        overlap_user = user.get_overlapping_appointments(self.cleaned_data['startTime'], self.cleaned_data['endTime'], exclude = self.instance) is not None
        if overlap_target_user or overlap_user:
            self.fields['schedule_overlapping_appointment_anyway'].widget = CheckboxInput()
            passed = False
            try:
                passed = self.cleaned_data['schedule_overlapping_appointment_anyway']
            except:
                passed = False
            if not passed:
                if overlap_target_user:
                    self.add_error('schedule_overlapping_appointment_anyway', target_user.__str__() + " has an overlapping appointment. Request the appointment anyway?")
                if overlap_user:
                    self.add_error('schedule_overlapping_appointment_anyway', "You have an overlapping appointment. Proceed?")
        return self.cleaned_data


class AppointmentCommentForm(forms.Form):
    comment = forms.CharField(label = 'Add a comment', required = True, max_length = 2000, widget = widgets.Textarea(attrs = {'rows':'5'}))

    def __init__(self, *args, **kwargs):
        super(AppointmentCommentForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', "Submit", css_class = 'btn btn-primary'))


class AppointmentCancelForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(AppointmentCancelForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', "Cancel appointment", css_class = 'btn btn-danger'))


class NotificationsDeleteForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(NotificationsDeleteForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', "Clear all notifications", css_class = 'btn btn-danger'))


class StudentSettingsForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(StudentSettingsForm, self).__init__(*args, **kwargs)

        # fix: remove seconds on all time-widgets in settings
        # self.fields['defaultAppointmentTime'].widget=forms.TimeInput(format='%H:%M')
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            # Fieldset(
            #    'Appointment Settings',
            #    'defaultAppointmentLength', 'defaultAppointmentTime',  # 'use24HourTime', 'reminderTimeBeforeAppointment',
            #    ),
            HTML("<br />"),
            Fieldset(
                'Notification Settings',
                'notifyAppointmentApprovedChangedCancelledWeb',  # 'notifyAppointmentApprovedChangedCancelledEmail',  # 'notifyAppointmentApprovedChangedCancelledMobile',
                # 'notifyAppointmentUpcomingWeb',  # 'notifyAppointmentUpcomingEmail',  # 'notifyAppointmentUpcomingMobile',
                'notifyAppointmentCommentWeb',  # 'notifyAppointmentCommentEmail',  # 'notifyAppointmentCommentMobile',
                ),
            HTML("<br />"),
            ButtonHolder(
                Submit('submit', 'Save changes')
                ),
            )

    class Meta:
        model = User
        fields = [  # 'defaultAppointmentLength', 'defaultAppointmentTime',  # 'use24HourTime', 'reminderTimeBeforeAppointment',
                  'notifyAppointmentApprovedChangedCancelledWeb',  # 'notifyAppointmentApprovedChangedCancelledWeb',  # 'notifyAppointmentApprovedChangedCancelledMobile',
                  # 'notifyAppointmentUpcomingWeb',  # 'notifyAppointmentUpcomingEmail',  # 'notifyAppointmentUpcomingMobile',
                  'notifyAppointmentCommentWeb',  # 'notifyAppointmentCommentEmail',  # 'notifyAppointmentCommentMobile'
                  ]


class TeacherSettingsForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['defaultLocation', 'minAppointmentTimespan', 'maxAppointmentTimespan', 'showUnavailability',  # 'use24HourTime', 'reminderTimeBeforeAppointment',
                  'notifyAppointmentApprovedChangedCancelledWeb',  # 'notifyAppointmentApprovedChangedCancelledEmail',  # 'notifyAppointmentApprovedChangedCancelledMobile',
                  # 'notifyAppointmentUpcomingWeb',  # 'notifyAppointmentUpcomingEmail',  # 'notifyAppointmentUpcomingMobile',
                  'notifyAppointmentCommentWeb',  # 'notifyAppointmentCommentEmail',  # 'notifyAppointmentCommentMobile',
                  'notifyAppointmentRequestedWeb',  # 'notifyAppointmentRequestedEmail',  # 'notifyAppointmentRequestedMobile'
                  ]

        help_texts = {
            'minAppointmentTimespan':'hours : minutes : seconds',
            'maxAppointmentTimespan':'hours : minutes : seconds'
            }

    def __init__(self, *args, **kwargs):
        super(TeacherSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Fieldset(
                'Appointment Settings',
                # 'use24HourTime',
                'reminderTimeBeforeAppointment',
                'defaultLocation',
                'minAppointmentTimespan',
                'maxAppointmentTimespan',
                'showUnavailability',
                ),
            HTML("<br />"),
            Fieldset(
                'Notification Settings',
                'notifyAppointmentApprovedChangedCancelledWeb',  # 'notifyAppointmentApprovedChangedCancelledEmail',  # 'notifyAppointmentApprovedChangedCancelledMobile',
                # 'notifyAppointmentUpcomingWeb',  # 'notifyAppointmentUpcomingEmail',  # 'notifyAppointmentUpcomingMobile',
                'notifyAppointmentCommentWeb',  # 'notifyAppointmentCommentEmail',  # 'notifyAppointmentCommentMobile',
                'notifyAppointmentRequestedWeb',  # 'notifyAppointmentRequestedEmail',  # 'notifyAppointmentRequestedMobile'
                ),
            HTML("<br />"),
            ButtonHolder(
                Submit('submit', 'Save changes')
                ),
            )


class AdministratorSettingsForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(AdministratorSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            # Fieldset(
            #    'Preferences',
            #    'use24HourTime',
            #    ),
            Fieldset(
                'Notification Settings',
                'notifyTeacherSignupWeb',  # 'notifyTeacherSignupEmail',  # 'notifyTeacherSignupMobile',
                ),
            HTML("<br />"),
            ButtonHolder(
                Submit('submit', 'Save changes')
                ),
            )

    class Meta:
        model = User
        fields = ['notifyTeacherSignupWeb',  # 'notifyTeacherSignupEmail',  # 'notifyTeacherSignupMobile', 'use24HourTime',
                  ]


class InstitutionSettingsForm(forms.ModelForm):

    class Meta:
        model = Institution
        fields = ['approvedStudentEmailDomains', 'approvedTeacherEmailDomains', 'timezone', 'autoApproveTeachers',  # 'isSuspended', ]
                  ]

    def __init__(self, *args, **kwargs):
        super(InstitutionSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', 'Save changes'))
        self.fields['autoApproveTeachers'].help_text = "Caution! This will automatically approve teachers who register to join this institution. It is recommended to leave this disabled unless domains for teacher email addresses are enforced above and teachers have email addresses on a unique domain, like @staff.example.edu."
        self.fields['approvedStudentEmailDomains'].help_text = "Enter domains to which student email addresses should be limited, one per line. To allow any, leave blank."
        self.fields['approvedTeacherEmailDomains'].help_text = "Enter domains to which teacher email addresses should be limited, one per line. To allow any, leave blank."
        self.fields['approvedStudentEmailDomains'].label = "Enforce student email addresses on one of these domains:"
        self.fields['approvedTeacherEmailDomains'].label = "Enforce teacher email addresses on one of these domains:"
        self.fields['approvedStudentEmailDomains'].widget = widgets.Textarea(attrs = {'rows':'3'})
        self.fields['approvedTeacherEmailDomains'].widget = widgets.Textarea(attrs = {'rows':'3'})
        self.fields['approvedStudentEmailDomains'].required = False
        self.fields['approvedTeacherEmailDomains'].required = False
        student_domains = json.loads(self.initial['approvedStudentEmailDomains'])
        teacher_domains = json.loads(self.initial['approvedTeacherEmailDomains'])
        self.initial['approvedStudentEmailDomains'] = '\n'.join('{}'.format(domain) for domain in student_domains)
        self.initial['approvedTeacherEmailDomains'] = '\n'.join('{}'.format(domain) for domain in teacher_domains)

    def clean_approvedStudentEmailDomains(self):
        domains = self.cleaned_data['approvedStudentEmailDomains'].replace("\r\n", "\n").split("\n")
        return json.dumps(domains, separators = (',', ":"))

    def clean_approvedTeacherEmailDomains(self):
        domains = self.cleaned_data['approvedTeacherEmailDomains'].replace("\r\n", "\n").split("\n")
        return json.dumps(domains, separators = (',', ":"))


class CustomCaptchaTextInput(CaptchaTextInput):
    template_name = 'website/captcha_widget.html'


class RegisterForm(forms.Form):
    email = forms.EmailField(required = True)
    email.help_text = "Your email address will be verified. Please check your inbox for an email with a link to complete your registration."
    first_name = forms.CharField(required = True)
    last_name = forms.CharField(required = True)
    password = forms.CharField(widget = forms.PasswordInput(), required = True)

    def __init__(self, *args, **kwargs):
        usertype = kwargs.pop('usertype')
        institution_id = kwargs.pop('institution_id')
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.usertype = usertype
        self.institution_id = institution_id
        if usertype == 0:
            self.fields['institution_name'] = forms.CharField(required = True)
            self.fields['institution_name'].help_text = "Enter the full, official name of your institution or school."
            self.fields['institution_address'] = forms.CharField(required = True)
            self.fields['institution_address'].help_text = "Enter the street address of your school, e.g. \"100 Main Street\""
            self.fields['institution_city_and_state'] = forms.CharField(required = True)
            self.fields['institution_city_and_state'].help_text = "Enter the city and state/province of your school, e.g. \"Chicago, IL\""
            self.fields['institution_zip_code'] = forms.IntegerField(widget = widgets.TextInput, required = True, validators = [MaxValueValidator(99999), MinValueValidator(1)])
        self.fields['captcha'] = CaptchaField(label = "Enter the characters you see:", widget = CustomCaptchaTextInput)

    # fix: email should not be validated unless captcha is valid to prevent email-guessing attacks
    def clean_email(self):
        cleaned_data = super(RegisterForm, self).clean()
        email = cleaned_data.get("email")
        validate_email(email)
        if self.usertype != 0:
            institution = Institution.objects.get(id = self.institution_id)
            institution.validate_email(email = email, usertype = self.usertype)
        return email

    def clean_password(self):
        cleaned_data = super(RegisterForm, self).clean()
        password = cleaned_data.get("password")
        # confirm_password = cleaned_data.get("confirm_password")
        # if password != confirm_password:
        #    self.add_error('confirm_password', "The passwords do not match.")
        validate_password(password)
        return password


class MyAccountForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        super(MyAccountForm, self).__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class DeleteAccountForm(forms.Form):
    password = forms.CharField(widget = PasswordInput, required = True)

    def __init__(self, *args, **kwargs):
        super(DeleteAccountForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', 'Permanently delete my account'))


class MyInstitutionUserEditForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'isTeacherApprovedByAdministrator', 'is_active']

    def __init__(self, *args, **kwargs):
        usertype = kwargs.pop('usertype')
        super(MyInstitutionUserEditForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        if usertype != 1:
            self.fields.pop('isTeacherApprovedByAdministrator')
        else:
            self.fields['isTeacherApprovedByAdministrator'].label = "Teacher approved"
            self.fields['isTeacherApprovedByAdministrator'].help_text = "Marks the teacher's identity as validated and permits students to schedule appointments with them."
            self.fields['is_active'].help_text = "Designates whether this user should be permitted to sign in. Disable this instead of deleting accounts."
        self.helper.add_input(Submit('submit', 'Save changes'))

    def clean_is_active(self):
        if self.cleaned_data['is_active'] and (not User.objects.get(pk = self.instance.pk).isEmailConfirmed):
            raise ValidationError("Security - cannot set this account to Active because the user has not yet confirmed their email address.")
        else:
            return self.cleaned_data['is_active']

    def clean_isTeacherApprovedByAdministrator(self):
        if self.cleaned_data['isTeacherApprovedByAdministrator'] and (not User.objects.get(pk = self.instance.pk).isEmailConfirmed):
            raise ValidationError("Security - cannot approve this teacher because the user has not yet confirmed their email address.")
        else:
            return self.cleaned_data['isTeacherApprovedByAdministrator']


class MyInstitutionUserDeleteForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(MyInstitutionUserDeleteForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', 'Delete user', css_class = 'btn btn-danger'))

