import datetime

from django.core.management.base import BaseCommand
from django.conf import settings

from fwadmin.models import (
    ComplexRule,
    Host,
)


class BaseRulesWriter:
    """Base class for writing host rules"""

    COMMENT_CHAR = "#"

    def _get_fw_string(list_nr, permit, type, from_net, to_ip, port):
        raise Exception("NotImplemented")

    def get_rules_list(self, host):
        l = []
        l.append("%s fw rules for %s (%s) owned by %s" % (
                self.COMMENT_CHAR, host.name, host.ip, host.owner))
        # complex rules
        list_nr = settings.FWADMIN_ACCESS_LIST_NR
        for complex_rule in ComplexRule.objects.filter(host=host):
            for from_net in complex_rule.from_net.split(","):
                if from_net:
                    s = self._get_fw_string(list_nr=list_nr,
                                            permit=complex_rule.permit,
                                            type=complex_rule.ip_protocol,
                                            from_net=from_net,
                                            to_ip=host.ip,
                                            port=complex_rule.port)
                    l.append(s)
        return l


class UfwRulesWriter(BaseRulesWriter):

    COMMENT_CHAR = "#"

    def _get_fw_string(self, list_nr, permit, type, from_net, to_ip, port):
        # ufw expects a lower case protocol
        type = type.lower()
        # note that list_nr is not used for ufw
        d = {'type': type,
             'from_net': from_net,
             'to_ip': to_ip,
             'port': "",
            }
        if permit:
            d["permit_or_deny"] = "allow"
        else:
            d["permit_or_deny"] = "deny"
        # port is optional I think
        if port:
            d["port"] = "port %s" % port
        s = ("ufw %(permit_or_deny)s proto %(type)s from %(from_net)s "
             "to %(to_ip)s %(port)s" % d)
        return s


class CiscoRulesWriter(BaseRulesWriter):

    COMMENT_CHAR = "!"

    def _get_fw_string(self, list_nr, permit, type, from_net, to_ip, port):
        # HRM, ugly and lacks tests!
        d = {'list_nr': list_nr,
             'type': type,
             'from_net': from_net,
             'to_ip': to_ip,
             'port': "",
            }
        if permit:
            d["permit_or_deny"] = "permit"
        else:
            d["permit_or_deny"] = "deny"
        # port is optional I think
        if port:
            d["port"] = "eq %s" % port
        s = ("access-list %(list_nr)s %(permit_or_deny)s %(type)s "
             "%(from_net)s host %(to_ip)s %(port)s" % d)
        return s


class Command(BaseCommand):
    help = 'write the firewall rules to stdout'

    def _write_rules(self, rules_list):
        print "\n".join(rules_list)

    def print_firewall_rules(self, writer):
        for host in Host.objects.all():
            if (host.active_until > datetime.date.today() and
                host.approved and
                host.active):
                rules_list = writer.get_rules_list(host)
                self._write_rules(rules_list)

    def handle(self, *args, **options):
        # default writer is cisco
        if not args:
            fw = "cisco"
        else:
            fw = args[0]
        fw_writer_class = globals()["%sRulesWriter" % fw.capitalize()]
        writer = fw_writer_class()
        self.print_firewall_rules(writer)
