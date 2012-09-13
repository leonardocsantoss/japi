# -*- coding: utf-8 -*-
import random

def create_token(num=30):
    token = ""
    for x in range(num):
        token += random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    return token


def get_host(request):
    return '%s%s' % ('https://' if request.is_secure() else 'http://', request.get_host())