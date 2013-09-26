# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.translation import ugettext as _

from models import UserToken


class AdminUserToken(admin.ModelAdmin):

    list_display = ("user", "token", "date_created", "_actions", )
    save_on_top = True

    fieldsets = [
        (_(u"UserToken API"),                   {'fields' : ("user", "token", "date_created",), }, ),
    ]

admin.site.register(UserToken, AdminUserToken)