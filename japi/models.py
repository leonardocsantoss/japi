# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext as _
from django.contrib.auth.models import User

from japi.utils import create_token
from japi import settings as api_settings

from datetime import datetime, timedelta
from django.utils.timezone import utc


class UserToken(models.Model):

    class Meta:
        verbose_name = _(u"UserToken API")
        verbose_name_plural = _(u"UserToken API")

    user = models.ForeignKey(User, related_name='usertoken', verbose_name=_(u'User'))
    date_created = models.DateTimeField(_(u"Date of created"), default=datetime.now)
    token = models.CharField(_(u"Token"), max_length=30, unique=True, default=create_token)

    def _actions(self):
        acoes = u"<a style=\"padding-left: 7px;\" href=\"%s\"><img src=\"%sadmin/img/admin/icon_changelink.gif\" />%s</a>" % (self.pk, settings.STATIC_URL, _(u"Editar"))
        acoes += u"<a style=\"padding-left: 7px;\" href=\"javascript://\" onClick=\"(function($) { $('input:checkbox[name=_selected_action]').attr('checked', ''); $('input:checkbox[name=_selected_action][value=%s]').attr('checked', 'checked'); $('select[name=action]').attr('value', 'delete_selected'); $('#changelist-form').submit(); })(jQuery);\" ><img src=\"%sadmin/img/admin/icon_deletelink.gif\" />%s</a>" % (self.pk, settings.STATIC_URL, _(u"Remover"))
        return acoes
    _actions.allow_tags = True
    _actions.short_description = _(u"Ações")

    def __unicode__(self):
        return u"%s" % self.user
    