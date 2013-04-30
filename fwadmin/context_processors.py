from django_project.settings import (
    FWADMIN_MODERATORS_USER_GROUP,
)


def is_moderator(request):
    is_moderator = request.user.groups.filter(
        name=FWADMIN_MODERATORS_USER_GROUP).count()
    return {'is_moderator': is_moderator,
           }
