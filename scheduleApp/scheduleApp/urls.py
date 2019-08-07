"""scheduleApp URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import sitemaps
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.urls import reverse

from website.admin import custom_admin_site


class EduScheduleSitemap(sitemaps.Sitemap):

    def items(self):
        return ['eduschedulesite:home', 'eduschedulesite:about', 'eduschedulesite:contact', 'eduschedulesite:terms']

    def location(self, item):
        return reverse(item)


sitemaps = {
    'static': EduScheduleSitemap,
}

urlpatterns = [
    path('web/', include('website.urls', namespace = 'website')),
    path('admin/', custom_admin_site.urls),
    path('account/', include('django.contrib.auth.urls')),
    path('', include('EduScheduleSite.urls', namespace = 'EduScheduleSite')),
    path('captcha/', include('captcha.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name = 'django.contrib.sitemaps.views.sitemap')
]

