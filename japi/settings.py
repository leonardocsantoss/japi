# -*- coding: utf-8 -*-
from django.conf import settings

# Time in days to token expires
API_DAYS_TOKEN_EXPIRES = getattr(settings, "API_DAYS_TOKEN_EXPIRES", 5)