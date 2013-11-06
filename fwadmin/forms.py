import netaddr

import django.forms as forms
from django.forms import ModelForm
from django.utils.translation import ugettext_lazy as _

from .models import (
    ComplexRule,
    Host,
    SamplePort,
)


class NewHostForm(ModelForm):

    class Meta:
        model = Host
        exclude = ('owner', 'approved', 'active', 'active_until',
                   'complex_rules')


class EditHostForm(ModelForm):

    class Meta:
        model = Host
        exclude = ('owner', 'approved', 'active', 'active_until',
                   'ip', 'complex_rules')


class NewRuleForm(ModelForm):

    IP_PROTOCOL_CHOICES = (
        ('TCP', 'TCP protocol'),
        ('UDP', 'UDP protocol'),
        )

    ip_protocol = forms.CharField(
        label=_("IP Protocol"),
        max_length=3,
        widget=forms.Select(choices=IP_PROTOCOL_CHOICES))

    stock_port = forms.ModelChoiceField(
        label=_("Standard Port"),
        queryset=SamplePort.objects.all(),
        required=False)

    def clean(self):
        """ Custom validation """
        cleaned_data = super(NewRuleForm, self).clean()
        port = cleaned_data.get("port")
        stock_port = cleaned_data.get("stock_port")
        # XXX: no test for this yet
        from_net_list = cleaned_data.get("from_net")
        if from_net_list and from_net_list != "any":
            for from_net in from_net_list.split(","):
                try:
                    net = netaddr.IPNetwork(from_net)
                    net  # pyflakes
                except netaddr.AddrFormatError:
                    raise forms.ValidationError(_("Invalid network address"))
        if not (port or stock_port):
            raise forms.ValidationError(
                _("Need a port number or a stock port"))
        if (port and stock_port and port != stock_port.number):
            raise forms.ValidationError(_("You port and stock port differ"))
        return cleaned_data

    class Meta:
        fields = (
            'stock_port',
            'name',
            'permit',
            'ip_protocol',
            'port',
            'from_net',
            )
        model = ComplexRule
