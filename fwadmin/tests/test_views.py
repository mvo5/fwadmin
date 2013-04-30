import datetime
import re

from urlparse import urlsplit

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.contrib.auth.models import (
    Group,
    User,
)
from fwadmin.models import (
    ComplexRule,
    Host,
)
from django_project.settings import (
    FWADMIN_ALLOWED_USER_GROUP,
    FWADMIN_MODERATORS_USER_GROUP,
    FWADMIN_DEFAULT_ACTIVE_DAYS,
)


class AnonymousTestCase(TestCase):

    def test_index_need_login(self):
        # we do only test "fwadmin:index" here as the other ones
        # need paramters
        url = reverse("fwadmin:index")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp["Location"],
            "http://testserver/accounts/login/?next=%s" % url)

    def test_user_has_permission_to_view_index(self):
        User.objects.create_user("user_without_group", password="lala")
        res = self.client.login(username="user_without_group", password="lala")
        self.assertEqual(res, True)
        url = reverse("fwadmin:index")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)


class LoggedInViewsTestCase(TestCase):

    def setUp(self):
        allowed_group = Group.objects.get(name=FWADMIN_ALLOWED_USER_GROUP)
        self.user = User.objects.create_user("meep", password="lala")
        self.user.groups.add(allowed_group)
        res = self.client.login(username="meep", password="lala")
        self.assertTrue(res)
        self.host = Host.objects.create(
            name="ahost", description="some description",
            ip="192.168.0.2", active_until="2022-01-01",
            owner=self.user)
        self.host.save()

    def test_index_has_host(self):
        """Test that the index view has a html table with out test host"""
        resp = self.client.get(reverse("fwadmin:index"))
        needle = r'<td>ahost</td>\s+<td>some description</td>\s+'\
                  '<td><a href="/fwadmin/host/%s/edit/">%s</a></td>' % (
                      self.host.id, self.host.ip)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(re.search(needle, resp.content))

    def test_new_host_get(self):
        resp = self.client.get(reverse("fwadmin:new_host"))
        self.assertEqual(resp.status_code, 200)

    def test_edit_host_get(self):
        resp = self.client.get(reverse("fwadmin:edit_host", args=(1,)))
        self.assertEqual(resp.status_code, 200)

    def test_new_rule_get(self):
        resp = self.client.get(reverse("fwadmin:new_rule_for_host",
                                       args=(self.host.id,)))
        self.assertEqual(resp.status_code, 200)

    def test_delete_needs_post(self):
        for action in ["delete_host", "delete_rule"]:
            resp = self.client.get(reverse("fwadmin:%s" % action,
                                           args=(self.host.id,)))
            self.assertEqual(resp.status_code, 400)

    def test_delete_host(self):
        resp = self.client.post(reverse("fwadmin:delete_host",
                                        args=(self.host.id,)))
        self.assertEqual(resp.status_code, 302)
        with self.assertRaises(Host.DoesNotExist):
            Host.objects.get(pk=self.host.id)

    def test_renew_host(self):
        # create ancient host
        host = Host.objects.create(name="meep", ip="192.168.1.1",
                                   # XXX: should we disallow renew after
                                   #      some time?
                                   active_until="1789-01-01",
                                   owner=self.user)
        # post to renew url
        resp = self.client.post(reverse("fwadmin:renew_host", args=(host.id,)))
        # ensure we get something of the right message
        self.assertTrue("Thanks for renewing" in resp.content)
        # and that it is actually renewed
        host = Host.objects.get(name="meep")
        self.assertEqual(
            host.active_until,
            (datetime.date.today() +
             datetime.timedelta(days=FWADMIN_DEFAULT_ACTIVE_DAYS)))

    def test_new_host(self):
        post_data = {"name": "newhost",
                     "ip": "192.168.1.1",
                    }
        resp = self.client.post(reverse("fwadmin:new_host"), post_data)
        # check the data
        host = Host.objects.get(name=post_data["name"])
        self.assertEqual(host.ip, post_data["ip"])
        self.assertEqual(host.owner, self.user)
        self.assertEqual(host.approved, False)
        self.assertEqual(
            host.active_until,
            (datetime.date.today() +
             datetime.timedelta(days=FWADMIN_DEFAULT_ACTIVE_DAYS)))
        # ensure the redirect to index works works
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            urlsplit(resp["Location"])[2], reverse("fwadmin:edit_host",
                                                   args=(host.id,)))

    def test_edit_host(self):
        # create a new host
        initial_hostname = "My initial hostname"
        new_post_data = {"name": initial_hostname,
                         "ip": "192.168.1.1",
                         }
        resp = self.client.post(reverse("fwadmin:new_host"), new_post_data)
        pk = Host.objects.get(name=initial_hostname).pk
        # now edit it and also try changing the IP
        edit_post_data = {"name": "edithost",
                         "ip": "192.168.99.99",
                         }
        # get the PK of the new host
        resp = self.client.post(reverse("fwadmin:edit_host", args=(pk,)),
                                edit_post_data)
        # and verify that:
        host = Host.objects.get(pk=pk)
        # name changed
        self.assertEqual(host.name, "edithost")
        # IP did not change (django forms give this for free, but its still
        # good to be paranoid if its just a single extra line)
        self.assertEqual(host.ip, "192.168.1.1")
        # and we redirect back
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            urlsplit(resp["Location"])[2], reverse("fwadmin:index"))

    def test_same_owner_actions(self):
        a_user = User.objects.create_user("Alice")
        host_name = "alice host"
        active_until = datetime.date(2036, 01, 01)
        host = Host.objects.create(name=host_name, ip="192.168.1.1",
                                   owner=a_user, active_until=active_until)
        for action in ["renew_host", "edit_host", "delete_host"]:
            resp = self.client.post(reverse("fwadmin:%s" % action,
                                            args=(host.id,)))
            # ensure we get a error status
            self.assertEqual(resp.status_code, 403)
            # check error message
            self.assertTrue("are not owner of this object" in resp.content)
            # ensure the active_until date is not modified
            host = Host.objects.get(name=host_name)
            self.assertEqual(host.active_until, active_until)

    def test_moderator_auth(self):
        resp = self.client.get(
            reverse("fwadmin:moderator_list_unapproved"))
        self.assertEqual(resp.status_code, 403)
        resp = self.client.get(
            reverse("fwadmin:moderator_approve_host", args=(1,)))
        self.assertEqual(resp.status_code, 403)

    def test_moderator_approve(self):
        moderators = Group.objects.get(name=FWADMIN_MODERATORS_USER_GROUP)
        self.user.groups.add(moderators)
        self.host.approved = False
        self.host.save()
        resp = self.client.post(reverse("fwadmin:moderator_approve_host",
                                        args=(self.host.id,)))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            urlsplit(resp["Location"])[2],
            reverse("fwadmin:moderator_list_unapproved"))
        # refresh from DB
        host = Host.objects.get(pk=self.host.id)
        self.assertEqual(host.approved, True)

    def test_moderator_list_unapproved(self):
        moderators = Group.objects.get(name=FWADMIN_MODERATORS_USER_GROUP)
        self.user.groups.add(moderators)
        self.host.approved = False
        self.host.save()
        # check that the unapproved one is listed
        resp = self.client.post(reverse("fwadmin:moderator_list_unapproved"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue("<td>%s</td>" % self.host.ip in resp.content)
        # simulate approve
        self.host.approved = True
        self.host.save()
        resp = self.client.post(reverse("fwadmin:moderator_list_unapproved"))
        self.assertFalse("<td>%s</td>" % self.host.ip in resp.content)

    def test_delete_rule(self):
        rule = ComplexRule.objects.create(
            host=self.host, name="ssh", permit=True, ip_protocol="TCP",
            port=22)
        resp = self.client.post(reverse("fwadmin:delete_rule",
                                       args=(1,)))
        # check that its gone
        with self.assertRaises(ComplexRule.DoesNotExist):
            ComplexRule.objects.get(pk=rule.pk)
        # check redirect
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            urlsplit(resp["Location"])[2],
            reverse("fwadmin:edit_host", args=(self.host.id,)))

    def test_new_rule_for_host(self):
        rule_name = "random rule name"
        post_data = {"name": rule_name,
                     "permit": False,
                     "ip_protocol": "UDP",
                     "port": 1337,
                    }
        resp = self.client.post(reverse("fwadmin:new_rule_for_host",
                                        args=(self.host.id,)),
                                post_data)
        # ensure we have the new rule
        rule = ComplexRule.objects.get(name=rule_name)
        for k, v in post_data.items():
            self.assertEqual(getattr(rule, k), v)
        # check redirect
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            urlsplit(resp["Location"])[2],
            reverse("fwadmin:edit_host", args=(self.host.id,)))
