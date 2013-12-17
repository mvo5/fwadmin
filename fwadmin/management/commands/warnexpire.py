import datetime
import os

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse

from django.conf import settings

from fwadmin.mail import send_mail
from fwadmin.models import Host


# run command as:
#   python manage.py warnexpire 14

def get_gender_for_username_from_ldap(username):
    if settings.FWADMIN_REAL_LDAP:
        # use ldap to determine the gender
        from django_auth_ldap.backend import LDAPBackend
        backend = LDAPBackend()
        user = backend.populate_user(username)
        if user:
            gender = user.ldap_user.attrs["initials"][0].strip()
            if gender.lower() == settings.LDAP_USER_INITIALS_MALE_MARKER:
                return "male"
            elif gender.lower() == settings.LDAP_USER_INITIALS_FEMALE_MARKER: 
                return "female"
    return "unknown"


def get_opening(host):
    gender = get_gender_for_username_from_ldap(host.owner.username)
    if gender == "male":
        # TRANSLATOR: gender "male"
        return _("Dear Mr. %(user)s,") % {
            'user': host.owner.username,
        }
    elif gender == "female":
        # TRANSLATOR: gender "femail"
        return _("Dear Mrs. %(user)s,") % {
            'user': host.owner.username,
        }
    else:
        # TRANSLATOR: gender unknown
        return _("Dear %(user)s,") % {
            'user': host.owner.username,
        }


def send_renew_mail(host):
    url = settings.FWADMIN_HOST_URL_TEMPLATE % {
        'url': reverse("fwadmin:edit_host", args=(host.pk,)),
        }
    # the text
    subject = _("Firewall config for '%s'") % host.name
    body = _("""%(opening)s

The firewall config for machine: '%(host)s' (%(ip)s) will expire at
'%(expire_date)s'.

Please click on %(url)s to renew.
""") % {
        'opening': get_opening(host),
        'host': host.name,
        'ip': host.ip,
        'expire_date': host.active_until,
        'url': url,
       }
    if "FWADMIN_DRY_RUN" in os.environ:
        print "From:", settings.FWADMIN_EMAIL_FROM
        print "To:", host.owner.email
        print "Subject: ", subject
        print body
        print
    else:
        send_mail(subject, body, settings.FWADMIN_EMAIL_FROM,
                  [host.owner.email])


class Command(BaseCommand):
    help = 'send warning mails when expire is close, first arg is nr of days'

    def handle(self, *args, **options):
        days_delta = settings.FWADMIN_WARN_EXPIRE_DAYS
        td = datetime.timedelta(days=days_delta)
        for host in Host.objects.all():
            if (host.active_until - td < datetime.date.today() and
                host.approved and
                host.active):
                send_renew_mail(host)
