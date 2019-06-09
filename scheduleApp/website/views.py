from copy import copy
from datetime import datetime, timedelta
from logging import _startTime

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Q, query
from django.http.response import Http404
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.urls.base import reverse
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from ratelimit.decorators import ratelimit

from website.forms import DeleteAccountForm, MyInstitutionUserEditForm, \
    MyInstitutionUserDeleteForm, AppointmentCancelForm, AppointmentEditForm, \
    AppointmentCommentForm, FindTeacherForm, NewAppointmentForm
from website.models import Comment

from .forms import FindInstitutionForm, UserTypeForm, RegisterForm, MyAccountForm, StudentSettingsForm, TeacherSettingsForm, AdministratorSettingsForm, InstitutionSettingsForm, NotificationsDeleteForm
from .models import AccountActivationTokenGenerator
from .models import User, Institution, AppointmentNotification, UserNotification, Appointment


def HomePage(request):
    domain = get_current_site(request).domain
    notifications = 0
    institution = None
    if request.user.is_authenticated:
        user = request.user
        institution = user.institution.name
        usertype = user.userType
        tz = user.institution.timezone
        timezone.activate(tz)
        start_time = timezone.now() - timedelta(days = 14)
        end_time = timezone.now()
        if usertype == 0:
            notifications = UserNotification.objects.filter(user = user, datetime__lt = end_time, datetime__gt = start_time).__len__()
        else:
            notifications = AppointmentNotification.objects.filter(user = user, datetime__lt = end_time, datetime__gt = start_time).__len__()
    return render(request, 'website/index.html', {'domain':domain, 'notifications':notifications, 'institution':institution})


@login_required
def MyAppointmentsView(request, time_begin = None, time_end = None):
    user = request.user
    usertype = user.userType
    if time_begin is None or time_end is None or time_begin >= time_end:
            time_begin = timezone.now()
            time_end = timezone.now() + timedelta(days = 30)
    appointments = user.get_appointments(time_begin = time_begin, time_end = time_end)
    overlapping_indices = []
    i = 0
    while i < len(appointments):
        if user.get_overlapping_appointments(appointments[i].startTime, appointments[i].endTime, exclude = appointments[i]) is not None:
            overlapping_indices.append(i)
        i += 1
    try:
        message = request.GET['msg']
    except:
        message = None
    return render(request, 'website/my_appointments.html', {'appointments':appointments, 'usertype':usertype, 'message':message, 'overlapping_indices':overlapping_indices})


@login_required
def AppointmentApproveView(request, pk):
    if not request.method == 'POST':
        return "This endpoint should be accessed via POST request only."
    user = request.user
    usertype = user.userType
    tz = user.institution.timezone
    timezone.activate(tz)
    if usertype == 1:
        appointment = get_object_or_404(Appointment, pk = pk, teacher = user, endTime__gte = timezone.now(), teacherConfirmed = False)
        target_user = appointment.student
        appointment.teacherConfirmed = True
        appointment.previousStartTime = None
        appointment.previousEndTime = None
        # technically not needed, but
        appointment.previousLocation = None
    elif usertype == 2:
        appointment = get_object_or_404(Appointment, pk = pk, student = user, endTime__gte = timezone.now(), studentConfirmed = False)
        target_user = appointment.teacher
        appointment.studentConfirmed = True
        appointment.previousLocation = None
        appointment.previousStartTime = None
        appointment.previousEndTime = None
    else:
        return "This page is intended for teachers and students only."
    appointment.save()
    try:
        notifications_remove = AppointmentNotification.objects.filter(user = user, appointment = appointment).exclude(event = 5)
        notifications_remove.delete()
    finally:
        if target_user.notifyAppointmentApprovedChangedCancelledWeb:
            notification = AppointmentNotification(datetime = timezone.now(), user = target_user, appointment = appointment, event = 0)
            notification.save()
        return redirect(reverse('website:myappointments') + '?msg=approve_success')


@login_required
def AppointmentEditView(request, pk):
    user = request.user
    usertype = user.userType
    tz = user.institution.timezone
    timezone.activate(tz)
    if usertype == 1:
        appointment = get_object_or_404(Appointment, pk = pk, teacher = user, endTime__gte = timezone.now())
        target_user = appointment.student
    elif usertype == 2:
        appointment = get_object_or_404(Appointment, pk = pk, student = user, endTime__gte = timezone.now())
        target_user = appointment.teacher
    else:
        raise Http404()
    commentform = AppointmentCommentForm()
    comments = Comment.objects.filter(appointment = appointment)
    if request.method == 'POST':
        prevStart = copy(appointment.startTime)
        prevEnd = copy(appointment.endTime)
        prevLocation = copy(appointment.location)
        form = AppointmentEditForm(request.POST, instance = appointment, usertype = usertype)
        if form.is_valid():
            updated_appointment = form.save(commit = False)
            change = False
            if not updated_appointment.location == prevLocation:
                updated_appointment.previousLocation = prevLocation
                change = True
            if not (updated_appointment.startTime == prevStart and updated_appointment.endTime == prevEnd):
                updated_appointment.previousStartTime = prevStart
                updated_appointment.previousEndTime = prevEnd
                change = True
            if usertype == 1 and change:
                updated_appointment.studentConfirmed = False
                updated_appointment.teacherConfirmed = True
                notification = AppointmentNotification(datetime = timezone.now(), user = target_user, appointment = updated_appointment, event = 1)
            elif usertype == 2 and change:
                updated_appointment.studentConfirmed = True
                updated_appointment.teacherConfirmed = False
                notification = AppointmentNotification(datetime = timezone.now(), user = target_user, appointment = updated_appointment, event = 1)
            updated_appointment.save()
            try:
                notifications_remove = AppointmentNotification.objects.filter(user = user, appointment = updated_appointment)
                notifications_remove.delete()
            finally:
                if change and target_user.notifyAppointmentApprovedChangedCancelledWeb:
                    notification.save()
                return redirect(reverse('website:myappointments') + '?msg=edit_success')
    else:
        form = AppointmentEditForm(instance = appointment, usertype = usertype)
    return render(request, 'website/appointment_edit.html', {'appointment':appointment, 'form':form, 'commentform':commentform, 'comments':comments, 'usertype':usertype})


@login_required
def AppointmentCommentView(request, pk):
    user = request.user
    usertype = user.userType
    tz = user.institution.timezone
    timezone.activate(tz)
    if usertype == 1:
        appointment = get_object_or_404(Appointment, pk = pk, teacher = user, endTime__gte = timezone.now())
        target_user = appointment.student
    elif usertype == 2:
        appointment = get_object_or_404(Appointment, pk = pk, student = user, endTime__gte = timezone.now())
        target_user = appointment.teacher
    else:
        raise Http404()
    if request.method == 'POST':
        form = AppointmentCommentForm(request.POST)
        if form.is_valid():
            comment = Comment(user = user, appointment = appointment, message = form.cleaned_data['comment'])
            comment.save()
            if target_user.notifyAppointmentCommentWeb:
                notification = AppointmentNotification(datetime = timezone.now(), user = target_user, appointment = appointment, event = 5)
                notification.save()
            return redirect('website:appointmentedit', appointment.pk)
    else:
        return "This endpoint should be accessed via POST request only."


@login_required
def AppointmentCancelView(request, pk):
    user = request.user
    usertype = user.userType
    if usertype == 1:
        appointment = get_object_or_404(Appointment, pk = pk, teacher = user, endTime__gte = timezone.now(), cancelled = False)
        target_user = appointment.student
    elif usertype == 2:
        appointment = get_object_or_404(Appointment, pk = pk, student = user, endTime__gte = timezone.now(), cancelled = False)
        target_user = appointment.teacher
    else:
        raise Http404()
    if request.method == 'POST':
        form = AppointmentCancelForm(request.POST)
        if form.is_valid():
            appointment.cancelled = True
            notification = AppointmentNotification(datetime = timezone.now(), user = target_user, appointment = appointment, event = 2)
            appointment.save()
            try:
                notifications_remove = AppointmentNotification.objects.filter(user = user, appointment = appointment).exclude(event = 5)
                notifications_remove.delete()
            finally:
                if target_user.notifyAppointmentApprovedChangedCancelledWeb:
                    notification.save()
                return redirect(reverse('website:myappointments') + '?msg=cancel_success')
    else:
        form = AppointmentCancelForm()
    return render(request, 'website/appointment_cancel.html', {'appointment':appointment, 'form':form, 'usertype':usertype})


@login_required
def NewAppointmentView(request, pk):
    user = request.user
    usertype = user.userType
    if usertype != 2:
        return "This page is intended for students only."
    target_user = get_object_or_404(User, pk = pk, isEmailConfirmed = True, institution = user.institution, userType = 1, isTeacherApprovedByAdministrator = True)
    tz = user.institution.timezone
    timezone.activate(tz)
    if request.method == 'POST':
        form = NewAppointmentForm(request.POST, user = user, target_user = target_user)
        if form.is_valid():
            new_appointment = form.save(commit = False)
            new_appointment.student = user
            new_appointment.teacher = target_user
            new_appointment.location = target_user.defaultLocation
            new_appointment.save()
            if target_user.notifyAppointmentRequestedWeb:
                notification = AppointmentNotification(datetime = timezone.now(), user = target_user, appointment = new_appointment, event = 4)
                notification.save()
            return redirect(reverse('website:myappointments') + '?msg=create_success')
    else:
        form = NewAppointmentForm(user = user, target_user = target_user)
    return render(request, 'website/new_appointment.html', {'form':form, 'target_user':target_user})


@login_required
def NewAppointmentRedirectView(request):
    return redirect('website:newappointmentteacher')


@login_required
def NewAppointmentFindTeacherView(request):
    user = request.user
    usertype = user.userType
    institution = user.institution
    if usertype != 2:
        return "This page is intended for students only."
    results = []
    empty = False
    if request.method == 'POST':
        form = FindTeacherForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data['teacher_name'].split(' ')
            query = [item.strip() for item in query]
            query = list(filter(None, query))
            if query.__len__() > 10:
                raise OverflowError("potential dos on database")
            q_set = Q()
            results = User.objects.filter(institution = institution, isEmailConfirmed = True, userType = 1, isTeacherApprovedByAdministrator = True, is_active = True)
            for item in query:
                q_set.add(Q(first_name__icontains = item), Q.OR)
                q_set.add(Q(last_name__icontains = item), Q.OR)
            results = results.filter(q_set)
            empty = results.__len__() == 0
    else:
        form = FindTeacherForm()
    return render(request, 'website/find_teacher.html', {'form':form, 'results':results, 'empty':empty})


@login_required
def MyInstitutionView(request, user_limiter = 0):
    # user_limiter set to 1 to display only students, 2 to display only approved teachers, 3 to display only unapproved teachers
    try:
        message = request.GET['msg']
    except:
        message = None
    user = request.user
    usertype = user.userType
    if not usertype == 0:
        raise Http404()
    institution = user.institution
    students = None
    approved_teachers = None
    unapproved_teachers = None
    if user_limiter == 0 or user_limiter == 1:
        students = User.objects.filter(institution = institution, userType = 2)
    if user_limiter == 0 or user_limiter == 2:
        approved_teachers = User.objects.filter(institution = institution, userType = 1, isTeacherApprovedByAdministrator = True)
    if user_limiter == 0 or user_limiter == 3:
        unapproved_teachers = User.objects.filter(institution = institution, userType = 1, isTeacherApprovedByAdministrator = False)
    single_column_view = (not user_limiter == 0)
    return render(request, 'website/my_institution.html', {'institution':institution, 'message':message, 'students':students, 'approved_teachers':approved_teachers, 'unapproved_teachers':unapproved_teachers, 'single_column_view':single_column_view})


@login_required
def MyInstitutionStudentsView(request):
    return MyInstitutionView(request, user_limiter = 1)


@login_required
def MyInstitutionTeachersView(request):
    return MyInstitutionView(request, user_limiter = 2)


@login_required
def MyInstitutionUnapprovedView(request):
    return MyInstitutionView(request, user_limiter = 3)


@login_required
def MyInstitutionUserApproveView(request, pk):
    if request.method == 'POST':
        user = request.user
        usertype = user.userType
        if not usertype == 0:
            raise Http404()
        institution = user.institution
        target_user = User.objects.get(pk = pk, institution = institution, userType = 1, isTeacherApprovedByAdministrator = False)
        if target_user is not None:
            target_user.isTeacherApprovedByAdministrator = True
            target_user.save()
            notifications_remove = UserNotification.objects.filter(user = user, target_user = target_user)
            notifications_remove.delete()
            return redirect(reverse('website:myinstitution') + '?msg=approve_success')
        else:
            return "Invalid request. This user may not exist or may be already approved."
    else:
        return "This endpoint should be accessed via POST request only."


@login_required
def MyInstitutionUserEditView(request, pk):
    user = request.user
    usertype = user.userType
    if not usertype == 0:
        raise Http404()
    institution = user.institution
    target_user = get_object_or_404(User, pk = pk, institution = institution)
    if target_user.userType == 0:
        raise Http404()
    if request.method == 'POST':
        form = MyInstitutionUserEditForm(request.POST, instance = target_user, usertype = target_user.userType)
        if form.is_valid():
            form.save()
            notifications_remove = UserNotification.objects.filter(user = user, target_user = target_user)
            notifications_remove.delete()
            return redirect(reverse('website:myinstitution') + '?msg=edit_success')
    else:
        form = MyInstitutionUserEditForm(instance = target_user, usertype = target_user.userType)
    return render(request, 'website/my_institution_user_edit.html', {'form':form, 'target_user':target_user})


@login_required
def MyInstitutionUserDeleteView(request, pk):
    user = request.user
    usertype = user.userType
    if not usertype == 0:
        raise Http404()
    institution = user.institution
    target_user = get_object_or_404(User, pk = pk, institution = institution)
    if target_user.userType == 0:
        raise Http404()
    if request.method == 'POST':
        form = MyInstitutionUserDeleteForm(request.POST)
        if form.is_valid():
            target_user.delete()
            return redirect(reverse('website:myinstitution') + '?msg=delete_success')
    else:
        form = MyInstitutionUserDeleteForm()
    return render(request, 'website/my_institution_user_delete.html', {'form':form, 'target_user':target_user})


@login_required
def NotificationsView(request):
    user = request.user
    usertype = user.userType
    success = False
    if request.method == 'POST':
        form = NotificationsDeleteForm(request.POST)
        if form.is_valid():
            if usertype == 0:
                UserNotification.objects.filter(user = user).delete()
            else:
                AppointmentNotification.objects.filter(user = user).delete()
    else:
        form = NotificationsDeleteForm()
    tz = user.institution.timezone
    timezone.activate(tz)
    start_time = timezone.now() - timedelta(days = 14)
    end_time = timezone.now()
    if usertype == 0:
        total_notifications = UserNotification.objects.filter(user = user).__len__()
        notifications = UserNotification.objects.filter(user = user, datetime__lt = end_time, datetime__gt = start_time).order_by('-datetime')
    else:
        total_notifications = UserNotification.objects.filter(user = user).__len__()
        notifications = AppointmentNotification.objects.filter(user = user, datetime__lt = end_time, datetime__gt = start_time).order_by('-datetime')
    older = 0
    if notifications.__len__() < total_notifications:
        older = total_notifications - notifications.__len__()
    return render(request, 'website/notifications.html', {'notifications':notifications, 'older':older, 'form':form, 'success':success})


@login_required
def NotificationDeleteView(request, pk):
    if not request.method == 'POST':
        return "This endpoint should be accessed via POST request only."
    user = request.user
    usertype = user.userType
    if usertype == 0:
        notification = get_object_or_404(UserNotification, pk = pk, user = user)
    else:
        notification = get_object_or_404(AppointmentNotification, pk = pk, user = user)
    notification.delete()
    return redirect(to = 'website:notifications')


@login_required
def InstitutionSettingsView(request):
    user = request.user
    usertype = user.userType
    success = False
    if not usertype == 0:
        return Http404('user is not school administrator')
    user_institution = user.institution
    if request.method == 'POST':
        form = InstitutionSettingsForm(request.POST, instance = user_institution)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = InstitutionSettingsForm(instance = user_institution)
    return render(request, 'website/institution_settings.html', {'form':form, 'success':success})


@login_required
def SettingsView(request):
    user = request.user
    usertype = user.userType
    success = False
    if request.method == 'POST':
        if usertype == 2:
            form = StudentSettingsForm(request.POST, instance = user)
        elif usertype == 1:
            form = TeacherSettingsForm(request.POST, instance = user)
        elif usertype == 0:
            form = AdministratorSettingsForm(request.POST, instance = user)
        if form.is_valid():
            form.save()
            success = True
    else:
        if usertype == 2:
            form = StudentSettingsForm(instance = user)
        elif usertype == 1:
            form = TeacherSettingsForm(instance = user)
        elif usertype == 0:
            form = AdministratorSettingsForm(instance = user)
    return render(request, 'website/settings.html', {'form':form, 'success':success})


@login_required
def MyAccountView(request):
    user = request.user
    success = False
    if request.method == 'POST':
        form = MyAccountForm(request.POST, instance = user)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = MyAccountForm(instance = user)
    email = user.email
    institution_name = user.institution
    usertype = user.userType
    usertype_friendly = ['School Administator', 'Teacher', 'Student'][usertype]
    last_login = user.last_login
    return render(request, 'website/my_account.html', {'form':form, 'email':email, 'institution':institution_name, 'usertype_friendly':usertype_friendly, 'last_login':last_login, 'success':success})


@login_required
def DeleteAccountView(request):
    user = request.user
    usertype = user.userType
    if usertype == 0:
        return render(request, "website/delete_account.html", {'admin':True})
    if request.method == 'POST':
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            if User.check_password(user, form.cleaned_data['password']):
                user.delete()
                return redirect(to = 'website:homepage')
            else:
                form.add_error('password', 'The password is incorrect.')
    else:
        form = DeleteAccountForm()
    return render(request, 'website/delete_account.html', {'admin':False, 'form':form})


def RegisterRedirectView(request):
    if request.user.is_authenticated:
        return redirect(to = 'website:homepage')
    else:
        return redirect('website:usertype')


@sensitive_post_parameters()
@ratelimit(key = 'ip', rate = '10/m', method = ratelimit.UNSAFE, block = True)
def RegisterView(request, usertype = 0, institution_id = None):
    # set up based on variables, throw on errors
    if usertype < 0 or usertype > 2:
        raise Http404('Invalid parameter usertype')
    usertype_friendly = ['School Administator', 'Teacher', 'Student'][usertype]
    domains = []
    institution = None
    if usertype == 0:
        if institution_id:
            raise Http404('No institution id should be provided with usertype==0')
    else:
        # we must check whether the institution is approved; this is the only place where this happens
        institution = get_object_or_404(Institution, id = institution_id, isVerified = True)
        domains = institution.get_approved_domains(usertype)
    # post request
    if request.method == 'POST':
        form = RegisterForm(request.POST, usertype = usertype, institution_id = institution_id)
        if form.is_valid():
            email = form.cleaned_data['email']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            password = form.cleaned_data['password']

            # create user and set values
            if usertype == 0:
                institution_name = form.cleaned_data['institution_name']
                institution_address = form.cleaned_data['institution_address']
                institution_city_and_state = form.cleaned_data['institution_city_and_state']
                institution_zip_code = form.cleaned_data['institution_zip_code']
                institution = Institution(name = institution_name, streetAddress = institution_address, cityState = institution_city_and_state, zipcode = institution_zip_code)
                institution.save()
            user = User.objects.create_user(email = email, password = password, first_name = first_name, last_name = last_name, is_active = False, institution = institution, userType = usertype)

            # send registration email
            user.send_activation_email(request)

            # display registration confirmation asking user to check email
            return render(request, 'website/register_confirmation.html', {'user_email':email})
    else:
        form = RegisterForm(usertype = usertype, institution_id = institution_id)

    return render(request, 'website/register.html', {'form':form, 'domains':domains, 'institution':institution, 'usertype':usertype, 'usertype_friendly':usertype_friendly})


def ActivateView(request, uidb64, token):
    if request.method == 'GET':
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk = uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        account_activation_token = AccountActivationTokenGenerator()
        if user is not None and account_activation_token.check_token(user, token):
            usertype = user.userType
            institution = user.institution
            user.is_active = True
            user.isEmailConfirmed = True
            if usertype == 1:
                if institution.autoApproveTeachers:
                    user.isTeacherApprovedByAdministrator = True
                else:
                    tz = user.institution.timezone
                    timezone.activate(tz)
                    notification = UserNotification(datetime = timezone.now(), user = User.objects.get(institution = institution, userType = 0), target_user = user)
                    notification.save()
            user.save()
            # <<must>> force user login at the end! Otherwise, last login timestamp is not updated and there is a potential for a replay attack if server admin is unscrupulous
            login(request, user)
            is_school_admin = user.userType == 0
            institution = user.institution
            return render(request, 'website/activation_valid.html', {'user':user, 'is_school_admin':is_school_admin, 'institution':institution})
        else:
            return render(request, 'website/activation_invalid.html', {'uid':uid, 'token':token})


def UserTypeView(request):
    if request.method == 'POST':
        form = UserTypeForm(request.POST)
        if form.is_valid():
            usertype = form.cleaned_data['usertype']
            if int(usertype) == 0:
                return redirect('website:registeradmin')
            else:
                return redirect('website:findinstitution', usertype)
    else:
        form = UserTypeForm()
    return render(request, 'website/usertype.html', {'form':form})


def FindInstitutionView(request, usertype):
    if usertype < 0 or usertype > 2:
        raise Http404('Invalid parameter usertype')
    results = []
    empty = False
    if request.method == 'POST':
        form = FindInstitutionForm(request.POST)
        if form.is_valid():
            # don't display institutions that are unapproved
            results = Institution.objects.filter(zipcode = form.cleaned_data['zipcode'], isVerified = True)
            empty = results.__len__() == 0
    else:
        form = FindInstitutionForm()
    return render(request, 'website/find_institution.html', {'form':form, 'results':results, 'empty':empty, 'usertype':usertype})
