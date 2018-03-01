# -*- coding: utf-8 -*-

import sys
import httplib
import urllib
from traceback import print_exc
from django.conf import settings


class OpenamAuth(object):
    """description of class"""

    urls = {
        "check_access_token":   "/openam/oauth2/tokeninfo",
    }


    def __init__(self):
        """ Class constructor """
        pass


    def validateAccessToken(self, accessToken):
        try:
            endpoint = OpenamAuth.urls['check_access_token']
            endpoint += "?access_token=" + str(accessToken)

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            connection = httplib.HTTPConnection(settings.OAUTH_SERVER)
            connection.request("GET", endpoint, None, headers)
            response = connection.getresponse()
            return response.status, response.read()
        except Exception, e:
            print_exc()
            return 500, str(e)
