import datetime
from django.test import TestCase
from StringIO import StringIO

from mock import (
    Mock,
    patch,
)

from django.core.urlresolvers import reverse
from django.conf import settings

from fwadmin.management.commands.genrules import (
    Command as GenrulesCommand,
)
from fwadmin.management.commands.disableinactive import (
    Command as DisableInactiveCommand
)
from fwadmin.management.commands.warnexpire import (
    Command as WarnExpireCommand,
    send_renew_mail,
    get_opening,
)
from fwadmin.management.commands.moderationnag import (
    send_moderation_nag_mail,
)

from fwadmin.models import (
    Host,
    ComplexRule,
    StaticRule,
)
from django.contrib.auth.models import User
from django_project.settings import (
    FWADMIN_ACCESS_LIST_NR,
    FWADMIN_EMAIL_FROM,
    FWADMIN_MODERATION_WAITING_MAIL_NAG,
)


def make_host(name, ip, owner, active_until=None, approved=True):
    if active_until is None:
        active_until = datetime.date.today() + datetime.timedelta(days=360)
    host = Host.objects.create(
        name=name, ip=ip, active_until=active_until, owner=owner,
        approved=approved)
    return host


def make_owner(username, email):
    owner = User.objects.create(username=username, email=email)
    return owner


# XXX: use native django fixtue support
class MyBaseTest(TestCase):

    def setUp(self):
        self.owner = make_owner("user1", "meep@example.com")
        self.host = make_host("test", "192.168.1.1", owner=self.owner)
        self.host.save()


class DisableInactiveTestCase(MyBaseTest):

    def setUp(self):
        MyBaseTest.setUp(self)
        self.cmd = DisableInactiveCommand()

    @patch("fwadmin.management.commands.disableinactive.ldap_user_exists")
    def test_no_gen_rules_expired(self, mock_f):
        mock_f.return_value = False
        self.assertEqual(self.host.active, True)
        self.assertEqual(self.host.approved, True)
        self.cmd.handle()
        # we need to "refresh" the host from the Db self.host is stale
        host_from_db = Host.objects.filter(pk=self.host.pk)[0]
        self.assertEqual(host_from_db.active, False)


class WarnExpireTestCase(MyBaseTest):

    def setUp(self):
        MyBaseTest.setUp(self)
        self.cmd = WarnExpireCommand()

    @patch("fwadmin.management.commands.warnexpire.send_renew_mail")
    def test_no_send_renew_mail_when_still_active(self, mock_f):
        """Ensure we do not send mails if there is enough delta"""
        today = datetime.date.today()
        delta = self.host.active_until - today
        self.assertEqual(delta, datetime.timedelta(days=360))
        self.cmd.handle()
        self.assertEqual(mock_f.mock_calls, [])

    @patch("fwadmin.management.commands.warnexpire.send_renew_mail")
    def test_send_renew_mail_from_cmd(self, mock_f):
        """Ensure we do send mails"""
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        self.host.active_until = tomorrow
        self.host.save()
        self.cmd.handle()
        mock_f.assert_called_with(self.host)

    @patch("fwadmin.management.commands.warnexpire.send_mail")
    def test_send_renew_mail(self, mock_f):
        """Ensure we do send mails"""
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        self.host.active_until = tomorrow
        self.host.save()
        send_renew_mail(self.host)
        subject = u"Firewall config for 'test'"
        body = u"""Dear user1,

The firewall config for machine: 'test' (192.168.1.1) will expire at
'%s'.

Please click on https://fwadmin.uni-trier.de%s to renew.
""" % (self.host.active_until,
           reverse("fwadmin:edit_host", args=(self.host.id,)))
        mock_f.assert_called_with(
            subject, body, FWADMIN_EMAIL_FROM,
            [self.host.owner.email])

    @patch("fwadmin.management.commands.warnexpire"
           ".get_gender_for_username_from_ldap")
    def test_send_renew_mail_opening(self, mock_f):
        """Ensure we do send mails"""
        test_list = [ 
            ("male", "Dear Mr. %s," % self.host.owner.username),
            ("female", "Dear Mrs. %s," % self.host.owner.username),
            ("unknown", "Dear %s," % self.host.owner.username),
        ]
        for gender, opening in test_list:
            mock_f.return_value = gender
            self.assertEqual(get_opening(self.host), opening)


class ManagementCommandsTestCase(MyBaseTest):

    def setUp(self):
        MyBaseTest.setUp(self)
        self.cmd = GenrulesCommand()

    @patch("fwadmin.management.commands.genrules.Command.OUTPUT",
           new_callable=StringIO)
    def test_no_gen_rules_unapproved(self, mock_f):
        """Ensure we do not write rules for unapproved hosts"""
        self.host.approved = False
        self.host.save()
        self.cmd.handle()
        self.assertEqual(mock_f.getvalue(), "")

    @patch("fwadmin.management.commands.genrules.Command.OUTPUT",
           new_callable=StringIO)
    def test_no_gen_rules_not_active(self, mock_f):
        """Ensure to not write rules for inactive hosts"""
        self.host.active = False
        self.host.save()
        self.cmd.handle()
        self.assertEqual(mock_f.getvalue(), "")

    @patch("fwadmin.management.commands.genrules.Command.OUTPUT",
           new_callable=StringIO)
    def test_no_gen_rules_active_until_over(self, mock_f):
        """Ensure we do not write rules for hosts that are expired"""
        self.host.active_until = datetime.date.today()
        self.host.save()
        self.cmd.handle()
        self.assertEqual(mock_f.getvalue(), "")

    @patch("fwadmin.management.commands.genrules.Command.OUTPUT",
           new_callable=StringIO)
    def test_gen_rules_complex(self, mock_f):
        """ Ensure complex rules are written """
        ComplexRule.objects.create(
            host=self.host,
            name="complex", from_net="192.168.2.0/24", permit=False,
            ip_protocol="UDP", port=53)
        self.cmd.handle()
        self.assertEqual(
            mock_f.getvalue(),
            "\n".join(
                ["! fw rules for %s (%s) owned by %s" % (
                    self.host.name, self.host.ip, self.owner.username),
                 "access-list %s deny UDP 192.168.2.0/24 host 192.168.1.1 "
                 "eq 53" % FWADMIN_ACCESS_LIST_NR,
             ])
        )

    @patch("fwadmin.management.commands.genrules.Command.OUTPUT",
           new_callable=StringIO)
    def test_gen_rules_header(self, mock_f):
        """ Ensure complex rules are written """
        rule_header = "! my header"
        StaticRule.objects.create(
            type=StaticRule.HEADER,
            text=rule_header,
        )
        rule_footer = "! my footer"
        StaticRule.objects.create(
            type=StaticRule.FOOTER,
            text=rule_footer
        )
        ComplexRule.objects.create(
            host=self.host,
            name="complex", from_net="192.168.2.0/24", permit=False,
            ip_protocol="UDP", port=53)
        self.cmd.handle()
        rule_1_comment = "! fw rules for %s (%s) owned by %s" % (
            self.host.name, self.host.ip, self.owner.username)
        rule_1 = "access-list %s deny UDP 192.168.2.0/24 host "\
                 "192.168.1.1 eq 53" % FWADMIN_ACCESS_LIST_NR
        self.assertEqual(
            mock_f.getvalue(),
            "\n".join([rule_header,
                       rule_1_comment,
                       rule_1,
                       rule_footer,
                   ]))


class GenRulesUfwTestCase(MyBaseTest):

    def setUp(self):
        MyBaseTest.setUp(self)
        self.cmd = GenrulesCommand()

    @patch("fwadmin.management.commands.genrules.Command.OUTPUT",
           new_callable=StringIO)
    def test_gen_rules(self, mock_f):
        """ Test the ufw backend """
        ComplexRule.objects.create(
            host=self.host,
            name="complex", from_net="192.168.2.0/24", permit=False,
            ip_protocol="UDP", port=53)
        self.cmd.handle("ufw")
        self.assertEqual(
            mock_f.getvalue(),
            "\n".join(
                ["# fw rules for %s (%s) owned by %s" % (
                    self.host.name, self.host.ip, self.owner.username),
                 "ufw deny proto udp from 192.168.2.0/24 to 192.168.1.1 "
                 "port 53",
             ])
        )


class SendModerationWaitingMailTestCase(MyBaseTest):

    def setUp(self):
        MyBaseTest.setUp(self)

    @patch("fwadmin.management.commands.moderationnag.send_mail")
    def test_no_send_moderation_mail(self, mock_f):
        """ if there are no hosts to moderate, do not send mail"""
        send_moderation_nag_mail()
        self.assertFalse(mock_f.called)

    @patch("fwadmin.management.commands.moderationnag.send_mail")
    def test_send_moderation_mail(self, mock_f):
        """ if there is something to moderate, send mail"""
        self.host.approved = False
        self.host.save()
        send_moderation_nag_mail()
        self.assertTrue(mock_f.called)
        mail_body = mock_f.call_args[0][1]
        mail_to = mock_f.call_args[0][3]
        self.assertTrue(
            reverse("fwadmin:moderator_list_unapproved") in mail_body)
        self.assertTrue(
            "\ntest (192.168.1.1)" in mail_body)
        self.assertEqual(mail_to, [FWADMIN_MODERATION_WAITING_MAIL_NAG])
