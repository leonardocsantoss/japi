# -*- coding: utf-8 -*-
from japi.sites import ApiSite, site
from japi.sites import ModelApi


def autodiscover():
    """
    Auto-discover INSTALLED_APPS api.py modules and fail silently when
    not present. This forces an import on them to register any api bits they
    may want.
    """

    import copy
    from django.conf import settings
    from django.utils.importlib import import_module
    from django.utils.module_loading import module_has_submodule

    for app in settings.INSTALLED_APPS:
        mod = import_module(app)
        # Attempt to import the app's api module.
        try:
            before_import_registry = copy.copy(site._registry)
            import_module('%s.api' % app)
        except:
            site._registry = before_import_registry

            if module_has_submodule(mod, 'api'):
                raise
