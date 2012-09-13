# -*- coding:utf-8 -*-
from django.http import HttpResponse
from django.utils import simplejson

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
                    if usertoken.ip != request.META.get('REMOTE_ADDR'):
                        raise InvalidToken(u'Invalid token for this id, login again.')
                except:
                    raise TokenNotExists(u'Token not exists, login again.')

                if usertoken.is_expired():
                    raise TokenExpired(u'Token has expired, login again.')
                usertoken.date_created = datetime.now()
                usertoken.save()
                request.__class__.user = usertoken.user
                print request
                
        except Exception as error:
            json = {
                'error': { type(error).__name__: error.message, }
            }
            return HttpResponse(simplejson.dumps(json, ensure_ascii=False), mimetype='text/javascript; charset=utf-8')