# -*- coding:utf-8 -*-
from django.http import HttpResponse
from django.utils import simplejson
from django.contrib.auth import login as auth_login

from models import UserToken
from datetime import datetime



class TokenExpired(Exception):
    pass

class TokenNotExists(Exception):
    pass

class InvalidToken(Exception):
    pass

class ApiAuth(object):

    def process_request(self, request):
        try:
            if request.REQUEST.get('token'):
                try: 
                    usertoken = UserToken.objects.get(token=request.REQUEST.get('token'))
                except UserToken.DoesNotExist:
                    raise TokenNotExists(u'Token not exists, login again.')
                usertoken.date_created = datetime.now()
                usertoken.save()
                usertoken.user.backend='django.contrib.auth.backends.ModelBackend'
                auth_login(request, usertoken.user)
                
        except Exception as error:
            json = {
                'status': False,
                'error': type(error).__name__,
                'error_message': error.message,
            }
            return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')