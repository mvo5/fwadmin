import datetime
#from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied

from django.http import (
    HttpResponseBadRequest,
    HttpResponseRedirect,
    HttpResponseForbidden,
)
from django.shortcuts import (
    render_to_response,
    redirect,
)
from django.template import RequestContext
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
)
from fwadmin.models import (
    ComplexRule,
    Host,
)
from fwadmin.forms import (
    NewHostForm,
    EditHostForm,
    NewRuleForm,
)
from django_project.settings import (
    FWADMIN_ALLOWED_USER_GROUP,
    FWADMIN_MODERATORS_USER_GROUP,
    FWADMIN_DEFAULT_ACTIVE_DAYS,
)


def group_required(group_name):
    """ Custom decorator that will raise a PermissionDendied if not in the
        right group
    """
    def is_in_group(user, group_name):
        if user:
            if user.groups.filter(name=group_name).count() == 1:
                return True
        # XXX: add template with logout form here
        raise PermissionDenied("You are not in group '%s'" % group_name)
    return user_passes_test(lambda u: is_in_group(u, group_name))


class NotOwnerError(HttpResponseForbidden):
    """A error if the user is not the owner of the object he/she tries
       to modify
    """
    def __init__(self, user):
        super(HttpResponseForbidden, self).__init__(
            "You (%s) are not owner of this object" % user.username)


@login_required
@group_required(FWADMIN_ALLOWED_USER_GROUP)
def index(request):
    all_hosts = Host.objects.filter(owner=request.user)
    # pass all views that the user owns too
    all_rules = ComplexRule.objects.filter(host__owner=request.user)
    return render_to_response('fwadmin/index.html',
                              {'all_hosts': all_hosts,
                               'complex_rules': all_rules,
                              },
                              context_instance=RequestContext(request))


@login_required
@group_required(FWADMIN_ALLOWED_USER_GROUP)
def new_host(request):
    if request.method == 'POST':
        form = NewHostForm(request.POST)
        if form.is_valid():
            # do not commit just yet, we need to add more stuff
            host = form.save(commit=False)
            # add the stuff here that the user can't edit
            host.owner = request.user
            active_until = (datetime.date.today() +
                            datetime.timedelta(FWADMIN_DEFAULT_ACTIVE_DAYS))
            host.active_until = active_until
            # and really save
            host.save()
            return HttpResponseRedirect(reverse("fwadmin:edit_host",
                                                args=(host.id,)))
    else:
        form = NewHostForm()
    return render_to_response('fwadmin/new_host.html',
                              {'form': form,
                              },
                              context_instance=RequestContext(request))


@login_required
@group_required(FWADMIN_ALLOWED_USER_GROUP)
def renew_host(request, pk):
    host = Host.objects.filter(pk=pk)[0]
    if host.owner != request.user:
        return NotOwnerError(request.user)
    active_until = (datetime.date.today() +
                    datetime.timedelta(FWADMIN_DEFAULT_ACTIVE_DAYS))
    host.active_until = active_until
    host.save()
    return render_to_response('fwadmin/renewed.html',
                              {'active_until': active_until,
                              },
                              context_instance=RequestContext(request))


@login_required
@group_required(FWADMIN_ALLOWED_USER_GROUP)
def delete_host(request, pk):
    host = Host.objects.get(pk=pk)
    if host.owner != request.user:
        return NotOwnerError(request.user)
    if request.method == 'POST':
        host.delete()
        return redirect(reverse("fwadmin:index"),
                        context_instance=RequestContext(request))
    return HttpResponseBadRequest("Only POST supported here")


@login_required
@group_required(FWADMIN_ALLOWED_USER_GROUP)
def edit_host(request, pk):
    host = Host.objects.filter(pk=pk)[0]
    if host.owner != request.user:
        return NotOwnerError(request.user)
    if request.method == 'POST':
        form = EditHostForm(request.POST, instance=host)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse("fwadmin:index"))
    else:
        form = EditHostForm(instance=host)
    rules_list = ComplexRule.objects.filter(host=host)
    return render_to_response('fwadmin/edit_host.html',
                              {'form': form,
                               'host': host,
                               'rules_list': rules_list,
                              },
                              context_instance=RequestContext(request))


@login_required
@group_required(FWADMIN_MODERATORS_USER_GROUP)
def moderator_list_unapproved(request):
    all_hosts = Host.objects.filter(approved=False)
    all_rules = ComplexRule.objects.filter(host__approved=False)
    # XXX: add a template for list
    return render_to_response('fwadmin/list-unapproved.html',
                              {'all_hosts': all_hosts,
                               'complex_rules': all_rules,
                               },
                              context_instance=RequestContext(request))


@login_required
@group_required(FWADMIN_MODERATORS_USER_GROUP)
def moderator_approve_host(request, pk):
    host = Host.objects.get(pk=pk)
    host.approved = True
    host.save()
    return redirect(reverse("fwadmin:moderator_list_unapproved"),
                    context_instance=RequestContext(request))


@login_required
@group_required(FWADMIN_ALLOWED_USER_GROUP)
def delete_rule(request, pk):
    if request.method == 'POST':
        rule = ComplexRule.objects.get(pk=pk)
        host = rule.host
        if host.owner != request.user:
            return NotOwnerError()
        rule.delete()
        return redirect(reverse("fwadmin:edit_host", args=(host.id,)))
    return HttpResponseBadRequest("Only POST supported here")


@login_required
@group_required(FWADMIN_ALLOWED_USER_GROUP)
def new_rule_for_host(request, hostid):
    host = Host.objects.get(pk=hostid)
    if host.owner != request.user:
        return HttpResponseForbidden("you are not the owner of the host")
    if request.method == 'POST':
        form = NewRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.host = host
            stock_port = form.cleaned_data["stock_port"]
            if stock_port:
                rule.ip_protocol = stock_port.ip_protocol
                rule.port = stock_port.number
            rule.save()
            return HttpResponseRedirect(reverse("fwadmin:edit_host",
                                                args=(host.id,)))
    else:
        form = NewRuleForm()
    return render_to_response('fwadmin/new_rule.html',
                              {'host': host,
                               'form': form,
                              },
                              context_instance=RequestContext(request))
