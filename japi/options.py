from django import forms
from django.forms.models import modelform_factory, model_to_dict
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.util import unquote, get_deleted_objects
from django.core.exceptions import PermissionDenied
from django.db import models, router
from django.http import Http404, HttpResponse
from django.utils.functional import update_wrapper
from django.utils.html import escape
from django.utils.functional import curry
from django.utils.text import get_text_list
from django.utils.translation import ugettext as _
from django.utils.encoding import force_unicode, smart_str
from django.views.decorators.csrf import csrf_exempt
import operator

from django.http import HttpResponse
from django.core import serializers
from django.utils import simplejson

class SaveModelError(Exception):
    pass

class HttpError(Exception):
    pass


class ModelApi(object):
    
    fields = None
    exclude = []
    readonly_fields = []
    search_fields = []
    form = forms.ModelForm
    order_by = []
    list_per_page = 500

    def __init__(self, model, api_site):
        self.model = model
        self.opts = model._meta
        self.api_site = api_site
        super(ModelApi, self).__init__()

    def get_fields(self, request):
        if request.REQUEST.get('fields'):
            if self.fields:
                fields = [field for field in request.REQUEST.get('fields').split(',') if field in self.fields]
            else:
                fields = request.REQUEST.get('fields').split(',')
        elif self.fields:
            fields = list(self.fields)
        else:
            lists = self.opts.local_many_to_many+self.opts.fields
            fields = [field.name for field in lists]
        return fields

    def get_editables_fields(self, request):
        fields = self.get_fields(request)
        for field in self.get_readonly_fields(request):
            fields.remove(field)
        for field in self.exclude:
            fields.remove(field)
        return fields

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields

    def formfield_for_dbfield(self, db_field, **kwargs):
        request = kwargs.pop("request", None)
        if db_field.choices:
            return self.formfield_for_choice_field(db_field, request, **kwargs)
        # ForeignKey or ManyToManyFields
        if isinstance(db_field, (models.ForeignKey, models.ManyToManyField)):
            # Get the correct formfield.
            if isinstance(db_field, models.ForeignKey):
                formfield = self.formfield_for_foreignkey(db_field, request, **kwargs)
            elif isinstance(db_field, models.ManyToManyField):
                formfield = self.formfield_for_manytomany(db_field, request, **kwargs)
            return formfield
        # For any other type of field, just call its formfield() method.
        return db_field.formfield(**kwargs)

    def formfield_for_choice_field(self, db_field, request=None, **kwargs):
        #TODO:
        return db_field.formfield(**kwargs)

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        #TODO:
        return db_field.formfield(**kwargs)

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        #TODO:
        return db_field.formfield(**kwargs)

    def queryset(self, request):
        qs = self.model._default_manager.get_query_set()

        params = dict(request.GET.items())
        if 'order_by' in params.keys(): del params['order_by']
        if 'fields' in params.keys(): del params['fields']
        if 'list_per_page' in params.keys(): del params['list_per_page']
        if 'page' in params.keys(): del params['page']
        if 'token' in params.keys(): del params['token']
        if 'q' in params.keys(): del params['q']

        exclude = {}
        for key, value in params.items():
            if key.startswith('exclude__'):
                if not isinstance(key, str):
                    del params[key]
                    exclude[smart_str(key).replace('exclude__', '')] = value

                if key.endswith('__in'):
                    value = value.split(',')
                    exclude[key.replace('exclude__', '')] = value

                if key.endswith('__isnull'):
                    if value.lower() in ('', 'false'): value = False
                    else: value = True
                    exclude[key.replace('exclude__', '')] = value
            else:
                if not isinstance(key, str):
                    del params[key]
                    params[smart_str(key)] = value

                if key.endswith('__in'):
                    value = value.split(',')
                    params[key] = value

                if key.endswith('__isnull'):
                    if value.lower() in ('', 'false'): value = False
                    else: value = True
                    params[key] = value

        qs = qs.filter(**params).exclude(**exclude)


        def construct_search(field_name):
            if field_name.startswith('^'):
                return "%s__istartswith" % field_name[1:]
            elif field_name.startswith('='):
                return "%s__iexact" % field_name[1:]
            elif field_name.startswith('@'):
                return "%s__search" % field_name[1:]
            else:
                return "%s__icontains" % field_name

        if request.GET.get('q'):
            orm_lookups = [construct_search(str(search_field)) for search_field in self.search_fields]
            for bit in request.GET.get('q').split():
                or_queries = [models.Q(**{orm_lookup: bit}) for orm_lookup in orm_lookups]
                qs = qs.filter(reduce(operator.or_, or_queries))

        order_by = request.GET.get('order_by', u",".join(self.order_by)).split(',')
        qs = qs.order_by(*order_by)

        return qs

    def get_urls(self):
        from django.conf.urls.defaults import patterns, url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.api_site.api_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.module_name

        urlpatterns = patterns('',
            url(r'^$',
                wrap(self.changelist_view),
                name='%s_%s_changelist' % info),
            url(r'^class/$',
                wrap(self.class_view),
                name='%s_%s_class' % info),
            url(r'^add/$',
                 wrap(self.add_view),
                 name='%s_%s_add' % info),
            url(r'^(.+)/delete/$',
                wrap(self.delete_view),
                name='%s_%s_delete' % info),
            url(r'^(.+)/$',
                 wrap(self.change_view),
                 name='%s_%s_change' % info),
        )
        return urlpatterns

    def urls(self):
        return self.get_urls()
    urls = property(urls)


    def has_add_permission(self, request):
        opts = self.opts
        return request.user.has_perm(opts.app_label + '.' + opts.get_add_permission())

    def has_change_permission(self, request, obj=None):
        opts = self.opts
        return request.user.has_perm(opts.app_label + '.' + opts.get_change_permission())

    def has_changelist_permission(self, request, obj=None):
        opts = self.opts
        return request.user.has_perm(opts.app_label + '.' + opts.get_change_permission().replace('change', 'changelist'))

    def has_delete_permission(self, request, obj=None):
        opts = self.opts
        return request.user.has_perm(opts.app_label + '.' + opts.get_delete_permission())

    def get_model_perms(self, request):
        return {
            'add': self.has_add_permission(request),
            'change': self.has_change_permission(request),
            'changelist': self.has_changelist_permission(request),
            'delete': self.has_delete_permission(request),
        }

    def get_form(self, request, obj=None, **kwargs):

        if self.exclude is None:
            exclude = []
        else:
            exclude = list(self.exclude)
        exclude.extend(kwargs.get("exclude", []))
        exclude.extend(self.get_readonly_fields(request, obj))
        exclude = exclude or None

        defaults = {
            "form": self.form,
            "fields": self.get_fields(request),
            "exclude": exclude,
            "formfield_callback": curry(self.formfield_for_dbfield, request=request),
        }
        defaults.update(kwargs)
        return modelform_factory(self.model, **defaults)

    def get_object(self, request, object_id):
        queryset = self.queryset(request)
        try:
            return queryset.get(pk=object_id)
        except:
            return None

    def log_addition(self, request, object):
        from django.contrib.admin.models import LogEntry, ADDITION
        LogEntry.objects.log_action(
            user_id         = request.user.pk,
            content_type_id = ContentType.objects.get_for_model(object).pk,
            object_id       = object.pk,
            object_repr     = force_unicode(object),
            action_flag     = ADDITION
        )

    def log_change(self, request, object, message):

        from django.contrib.admin.models import LogEntry, CHANGE
        LogEntry.objects.log_action(
            user_id         = request.user.pk,
            content_type_id = ContentType.objects.get_for_model(object).pk,
            object_id       = object.pk,
            object_repr     = force_unicode(object),
            action_flag     = CHANGE,
            change_message  = message
        )

    def log_deletion(self, request, object, object_repr):
        from django.contrib.admin.models import LogEntry, DELETION
        LogEntry.objects.log_action(
            user_id         = request.user.id,
            content_type_id = ContentType.objects.get_for_model(self.model).pk,
            object_id       = object.pk,
            object_repr     = object_repr,
            action_flag     = DELETION
        )

    def construct_change_message(self, request, form):
        change_message = []
        if form.changed_data:
            change_message.append(_('Changed %s.') % get_text_list(form.changed_data, _('and')))
        change_message = ' '.join(change_message)
        return change_message or _('No fields changed.')

    def save_form(self, request, form, change):
        return form.save(commit=False)

    def save_model(self, request, obj, form, change):
        obj.save()
        form.save_m2m()

    def delete_model(self, request, obj):
        obj.delete()

    @csrf_exempt
    def changelist_view(self, request, extra_context=None):
        try:
            json = {}

            opts = self.model._meta
            app_label = opts.app_label
            if not self.has_changelist_permission(request, None):
                raise PermissionDenied

            queryset = self.queryset(request)
            order_by = request.REQUEST.get('order_by', u",".join(self.order_by)).split(',')
            queryset = queryset.order_by(*order_by)

            json['status'] = True
            json['count_queryset'] = len(queryset)
            #Pagination
            page = int(request.REQUEST.get('page', 1))
            list_per_page = int(request.REQUEST.get('list_per_page', self.list_per_page))
            queryset = queryset[list_per_page*(page-1):list_per_page*page]

            json['count_page'] = len(queryset)
            json['page'] = page
            json['list_per_page'] = list_per_page

            if json['count_queryset'] > (json['count_page']*json['page']):
                if page:
                    next_page = request.build_absolute_uri().replace('&page=%s' % page, '&page=%s' % (page+1))
                    if page > 1:
                        json['previous_page'] = request.build_absolute_uri().replace('&page=%s' % page, '&page=%s' % (page-1))
                else:
                    next_page = "%s%s" % (request.build_absolute_uri(), '&page=2')
                json['next_page'] = next_page
            
            json['queryset'] = []
            for query in queryset:
                new_json = simplejson.loads(serializers.serialize('json', [query, ], fields=self.get_fields(request), ensure_ascii=False, use_natural_keys=True)[1:][:-1].encode("utf8"))['fields']
                new_json['pk'] = query.pk
                for field in self.get_fields(request):
                    if "instancemethod" in str(type(getattr(query, field))):
                        func = getattr(query, field)
                        new_json[field] = func()
                json['queryset'].append(new_json)
        
        except Exception as error:
            json = {
                'status': False,
                'error': type(error).__name__,
                'error_message': u'%s' % error,
            }
        return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')
    
    @csrf_exempt
    def class_view(self, request, extra_context=None):
        try:
            json = {}

            opts = self.model._meta
            app_label = opts.app_label
            if not self.has_add_permission(request) and not self.has_change_permission(request) and not self.has_changelist_permission(request):
                raise PermissionDenied

            json['model'] = "%s.%s" % (self.opts.app_label, self.opts.module_name)
            json['status'] = True
            json['fields'] = {}
            for field in self.get_editables_fields(request):
                field_object = self.opts.get_field(field)
                attrs = {}
                attrs['type'] = type(field_object).__name__
                if field_object.unique: attrs['unique'] = field_object.unique
                if field_object.max_length: attrs['max_length='] = field_object.max_length
                if field_object.blank: attrs['blank'] = field_object.blank
                if field_object.null: attrs['null'] = field_object.null

                if field_object.choices:
                    attrs['choices'] = list(self.formfield_for_choice_field(field_object, request).choices)

                if type(field_object).__name__ == 'ManyToManyField':
                    attrs['model'] = "%s.%s" % (field_object.related.parent_model._meta.app_label, field_object.related.parent_model._meta.module_name)
                    attrs['choices'] = list(self.formfield_for_manytomany(field_object, request).choices)

                if type(field_object).__name__ == 'ForeignKey':
                    attrs['model'] = "%s.%s" % (field_object.related.parent_model._meta.app_label, field_object.related.parent_model._meta.module_name)
                    attrs['choices'] = list(self.formfield_for_foreignkey(field_object, request).choices)

                json['fields'][field] = attrs

        except Exception as error:
            json = {
                'status': False,
                'error': type(error).__name__,
                'error_message': u'%s' % error,
            }
        return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')

    @csrf_exempt
    def add_view(self, request, extra_context=None):
        try:
            model = self.model
            opts = model._meta

            if not self.has_add_permission(request):
                raise PermissionDenied

            ModelForm = self.get_form(request)
            form = ModelForm(request.POST, request.FILES)
            if form.is_valid():
                new_object = self.save_form(request, form, change=False)
                self.save_model(request, new_object, form, change=False)
                self.log_addition(request, new_object)

                json = {}
                json['status'] = True
                json['queryset'] = []
                for query in [new_object, ]:
                    new_json = simplejson.loads(serializers.serialize('json', [query, ], fields=self.get_fields(request), ensure_ascii=False, use_natural_keys=True)[1:][:-1].encode("utf8"))['fields']
                    new_json['pk'] = query.pk
                    for field in self.get_fields(request):
                        if "instancemethod" in str(type(getattr(query, field))):
                            func = getattr(query, field)
                            new_json[field] = func()
                    json['queryset'].append(new_json)
            else:
                raise SaveModelError(dict(form.errors))
        except Exception as error:
            json = {
                'status': False,
                'error': type(error).__name__,
                'error_message': u'%s' % error,
            }
        return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')
            
    @csrf_exempt
    def change_view(self, request, object_id, extra_context=None):
        try:
            model = self.model
            opts = model._meta

            obj = self.get_object(request, object_id)

            if not self.has_change_permission(request, obj):
                raise PermissionDenied

            if obj is None:
                raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {'name': force_unicode(opts.verbose_name), 'key': escape(object_id)})

            ModelForm = self.get_form(request, obj)
            form = ModelForm(dict(model_to_dict(obj).items()+request.POST.items()), request.FILES, instance=obj)
            if form.is_valid():
                obj = self.save_form(request, form, change=True)
                self.save_model(request, obj, form, change=False)
                change_message = self.construct_change_message(request, form)
                self.log_change(request, obj, change_message)

                json = {}
                json['status'] = True
                json['queryset'] = []
                for query in [obj, ]:
                    new_json = simplejson.loads(serializers.serialize('json', [query, ], fields=self.get_fields(request), ensure_ascii=False, use_natural_keys=True)[1:][:-1].encode("utf8"))['fields']
                    new_json['pk'] = query.pk
                    for field in self.get_fields(request):
                        if "instancemethod" in str(type(getattr(query, field))):
                            func = getattr(query, field)
                            new_json[field] = func()
                    json['queryset'].append(new_json)
            else:
                raise SaveModelError(dict(form.errors))
        except Exception as error:
            json = {
                'status': False,
                'error': type(error).__name__,
                'error_message': u'%s' % error,
            }
        return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')
            
    @csrf_exempt
    def delete_view(self, request, object_id, extra_context=None):
        try:
            opts = self.model._meta
            app_label = opts.app_label

            obj = self.get_object(request, unquote(object_id))

            if not self.has_delete_permission(request, obj):
                raise PermissionDenied

            if obj is None:
                raise Http404(_("'%(name)s' object with primary key %(key)r does not exist.") % {'name': force_unicode(opts.verbose_name), 'key': escape(object_id)})

            using = router.db_for_write(self.model)

            # Populate deleted_objects, a data structure of all related objects that
            # will also be deleted.
            (deleted_objects, perms_needed, protected) = get_deleted_objects(
                [obj], opts, request.user, self.api_site, using)

            object_name = force_unicode(opts.verbose_name)

            if perms_needed:
                raise PermissionDenied
            obj_display = force_unicode(obj)
            self.log_deletion(request, obj, obj_display)
            self.delete_model(request, obj)

            if perms_needed or protected:
                raise PermissionDenied("Cannot delete '%(name)s' with primary key %(key)r.") % {"name": object_name, "key": escape(object_id)}
            else:
                json = {"status": True, "sucess": "Object '%(name)s' with primary key %(key)r deleted." % {"name": object_name, "key": escape(object_id)}, }
        except Exception as error:
            json = {
                'status': False,
                'error': type(error).__name__,
                'error_message': u'%s' % error,
            }
        return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')