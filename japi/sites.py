# -*- coding: utf-8 -*-
from japi.options import ModelApi
from japi.utils import get_host
from django.views.decorators.csrf import csrf_protect
from django.db.models.base import ModelBase
try:
    from django.utils.functional import update_wrapper
except ImportError:
    from functools import update_wrapper
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache
from django.core.exceptions import ImproperlyConfigured

from django.core.urlresolvers import reverse

from django.http import HttpResponse
from django.core import serializers
from django.utils import simplejson
from django.contrib.auth import authenticate
from models import UserToken

class UserNotExists(Exception):
    pass

class AlreadyRegistered(Exception):
    pass

class NotRegistered(Exception):
    pass

class ApiSite(object):

    def __init__(self, name='api', app_name='api'):
        self._registry = {} # model_class class -> admin_class instance
        self.name = name
        self.app_name = app_name
        

    def register(self, model_or_iterable, api_class=None):

        if not api_class:
            api_class = ModelApi

        if isinstance(model_or_iterable, ModelBase):
            model_or_iterable = [model_or_iterable]
        for model in model_or_iterable:
            if model._meta.abstract:
                raise ImproperlyConfigured(_('The model %s is abstract, so it '
                      'cannot be registered with admin.' % model.__name__))

            if model in self._registry:
                raise AlreadyRegistered(_('The model %s is already registered' % model.__name__))

            self._registry[model] = api_class(model, self)


    def unregister(self, model_or_iterable):
        if isinstance(model_or_iterable, ModelBase):
            model_or_iterable = [model_or_iterable]
        for model in model_or_iterable:
            if model not in self._registry:
                raise NotRegistered(_('The model %s is not registered' % model.__name__))
            del self._registry[model]


    def api_view(self, view, cacheable=False):
        def inner(request, *args, **kwargs):
            return view(request, *args, **kwargs)
        if not cacheable:
            inner = never_cache(inner)
        # We add csrf_protect here so this function can be used as a utility
        # function for any view, without having to repeat 'csrf_protect'.
        if not getattr(view, 'csrf_exempt', False):
            inner = csrf_protect(inner)
        return update_wrapper(inner, view)

    def has_add_permission(self, request, opts):
        return request.user.has_perm(opts.app_label + '.' + opts.get_add_permission())

    def has_change_permission(self, request, opts):
        return request.user.has_perm(opts.app_label + '.' + opts.get_change_permission())

    def has_changelist_permission(self, request, opts):
        return request.user.has_perm(opts.app_label + '.' + opts.get_change_permission().replace('change', 'changelist'))

    def has_delete_permission(self, request, opts):
        return request.user.has_perm(opts.app_label + '.' + opts.get_delete_permission())

    def get_urls(self):
        try:
            from django.conf.urls.defaults import patterns, url, include
        except ImportError:
            from django.conf.urls import patterns, url, include

        def wrap(view, cacheable=False):
            def wrapper(*args, **kwargs):
                return self.api_view(view, cacheable)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        # Api-site-wide views.
        urlpatterns = patterns('',
            url(r'^auth/$', wrap(self.auth), name='api_auth'),
            url(r'^$', wrap(self.docs), name='api_docs'),
        )

        # Add in each model's views.
        for model, model_admin in self._registry.iteritems():
            urlpatterns += patterns('',
                url(r'^%s/%s/' % (model._meta.app_label, model._meta.module_name),
                    include(model_admin.urls))
            )
        return urlpatterns

    @property
    def urls(self):
        return self.get_urls(), self.app_name, self.name

    @never_cache
    def auth(self, request):
        try:
            username = request.REQUEST.get('username')
            password = request.REQUEST.get('password')
            user = authenticate(username=username, password=password)
            if not user:
                raise UserNotExists(_('Invalid username or password.'))

            usertoken = UserToken.objects.create(user=user)

            json = simplejson.loads(serializers.serialize('json', [usertoken, ], ensure_ascii=False, use_natural_keys=True)[1:][:-1].encode("utf8"))

        except Exception as error:
            json = {
                'error': { type(error).__name__: error.message, }
            }
        return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')


    def docs(self, request):
        try:
            json = {}
            if request.user.is_authenticated():
                for model, model_admin in self._registry.iteritems():
                    opts = model._meta
                    model_name = '%s.%s' % (opts.app_label, opts.module_name)
                    if self.has_add_permission(request, opts) or self.has_change_permission(request, opts) or self.has_delete_permission(request, opts) or self.has_changelist_permission(request, opts):
                        json[model_name] = {}
                        json[model_name]['class'] = {
                            'url': '%s/api/%s/%s/class/' % (get_host(request), opts.app_label, opts.module_name),
                            'method': ['GET'],
                            'require': ['token', ],
                            'return': model_name,
                        }
                        if self.has_add_permission(request, opts):
                            json[model_name]['add'] = {
                                'url': '%s/api/%s/%s/add/' % (get_host(request), opts.app_label, opts.module_name),
                                'method': ['POST'],
                                'require': ['token', ],
                                'return': model_name,
                            }
                        if self.has_change_permission(request, opts):
                            json[model_name]['change'] = {
                                'url': '%s/api/%s/%s/OBJECT_ID/' % (get_host(request), opts.app_label, opts.module_name),
                                'method': ['POST'],
                                'require': ['token', ],
                                'return': model_name,
                            }
                        if self.has_delete_permission(request, opts):
                            json[model_name]['delete'] = {
                                'url': '%s/api/%s/%s/OBJECT_ID/delete/' % (get_host(request), opts.app_label, opts.module_name),
                                'method': ['GET', 'POST'],
                                'require': ['token', ],
                                'return': 'message',
                            }
                        if self.has_changelist_permission(request, opts):
                            json[model_name]['list'] = {
                                'url': '%s/api/%s/%s/' % (get_host(request), opts.app_label, opts.module_name),
                                'method': ['GET'],
                                'require': ['token', ],
                                'return': model_name,
                            }
            else:
                json['auth'] = {
                    'url': '%s/api/auth/' % (get_host(request)),
                    'method': ['GET', 'POST'],
                    'required': ['username', 'passowrd'],
                    'return': "japi.usertoken",
                }
        except Exception as error:
            json = {
                'error': { type(error).__name__: error.message, }
            }
        return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')


site = ApiSite()
