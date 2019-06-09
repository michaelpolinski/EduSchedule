from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render


def HomePage(request):
    domain = get_current_site(request).domain
    return render(request, 'EduScheduleSite/index.html', {'domain':domain})


def AboutPage(request):
    return render(request, 'EduScheduleSite/about.html')


def ContactPage(request):
    return render(request, 'EduScheduleSite/contact.html')


def TermsPage(request):
    domain = get_current_site(request).domain
    return render(request, 'EduScheduleSite/terms.html', {'domain':domain})

