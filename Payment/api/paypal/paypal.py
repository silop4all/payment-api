# -*- coding: utf-8 -*-

import sys
import httplib
import urllib
from traceback import print_exc
from django.conf import settings
import requests

from config import __base_map__, __endpoint_map__



class Paypal(object):
    """Paypal class
    """

    def __init__(self, http_authorization_token):
        """Class constructor

        :param http_authorization_token: the authentication token for access in Paypal API (type Bearer)
        :type http_authorization_token: string
        """
        self.__base_map__ = __base_map__
        self.__endpoint_map__ = __endpoint_map__
        self.http_authorization_token = http_authorization_token

        self.headers = {
            "Accept": "application/json",
            "Content-type": "application/json",
            'User-agent': 'Prosperity4all/0.1',
            "Authorization": "Bearer " + str(self.http_authorization_token)
        }


class Token(Paypal):
    """Token class that inherits the Paypal class
    """
    
    def validate(self):
        """Validate the authorization information in Paypal

        Usage::
            >>> from api.paypal import paypal
            >>> payment = paypal.Token("your_authorization_bearer_token")
            >>> (http_status, response_json) = payment.validate()

        :returns: the HTTP status and the response body (if any)
        :rtype: tuple(integer, dictionary)
        """
        try:
            self.headers["Content-type"] = "application/x-www-form-urlencoded"
            endpoint = str(self.__base_map__['sandbox']) + str(self.__endpoint_map__['authentication'])
            request = requests.post(endpoint, data="grant_type=client_credentials", headers=self.headers)
            try:
                return request.status_code, request.json()
            except ValueError as ex:
                return request.status_code, dict({"error": request.reason})
        except:
            print_exc()
            return 500, dict({"error":"Internal server error"})


class Payment(Paypal):
    """Payment class that inherits the Paypal class

    Invoke a subset of web services included in the Paypal Payment API
    For more details visit the link https://developer.paypal.com/docs/api/payments/
    """

    def create(self, payload):
        """Create a payment in Paypal

        Usage::
            >>> from api.paypal import paypal
            >>> payment = paypal.Payment("your_authorization_bearer_token")
            >>> (http_status, response_json) = payment.create("payment_payload_as_json")

        :param payload: the description of payment 
        :type payload: JSON
        :returns: the HTTP status and the response body (if any)
        :rtype: tuple(integer, dictionary)
        """
        try:
            endpoint = str(self.__base_map__['sandbox']) + str(self.__endpoint_map__['payment'])
            request = requests.post(endpoint, json=payload, headers=self.headers)
            try:
                return request.status_code, request.json()
            except ValueError as ex:
                return request.status_code, dict({"error": request.reason})
        except:
            return 500, dict({"error":"Internal server error"})


    def execute(self, pay_id, payload):
        """Execute a payment in Paypal after customer agreement

        Usage::
            >>> from api.paypal import paypal
            >>> payment = paypal.Payment("your_authorization_bearer_token")
            >>> (http_status, response_json) = payment.execute("PAY-xxx", {"payer_id": "xxxxxxxxxxx"})

        :param pay_id: the payment id in Paypal format (PAY-xxx)
        :type pay_id: string
        :param payload: the payer_id details
        :type payload: JSON
        :returns: the HTTP status and the response body (if any)
        :rtype: tuple(number, dictionary)
        """
        try:
            endpoint = str(self.__base_map__['sandbox']) + str(self.__endpoint_map__['payment'])
            endpoint += str("/") + str(pay_id) 
            endpoint += str("/") + str("execute")
            request = requests.post(endpoint, json=payload, headers=self.headers)
            try:
                return request.status_code, request.json()
            except ValueError as ex:
                return request.status_code, dict({"error": request.reason})
        except:
            return 500, dict({"error":"Internal server error"})


class BillingPlan(Paypal):
    """BillingPlan class that inherits the Paypal class

    For more details visit the link https://developer.paypal.com/docs/api/payments.billing-plans
    """

    def create(self, payload):
        """Create a billing plan in Paypal

        Usage::
            >>> from api.paypal import paypal
            >>> plan = paypal.BillingPlan("your_authorization_bearer_token")
            >>> (http_status, response_json) = plan.create("plan_payload_as_json")

        :param payload: the description of billing plan 
        :type payload: dictionary/JSON
        :returns: the HTTP status and the response body (if any)
        :rtype: tuple(integer, dictionary)
        """
        try:
            endpoint = str(self.__base_map__['sandbox']) + str(self.__endpoint_map__['billing_plan'])
            request = requests.post(endpoint, json=payload, headers=self.headers)
            try:
                return request.status_code, request.json()
            except ValueError as ex:
                print ex
                return request.status_code, dict({"error": request.reason})
        except:
            print_exc()
            return 500, dict({"error":"Internal server error"})


    def activate(self, plan_id):
        """Activate an existing billing plan in Paypal

        Usage::
            >>> from api.paypal import paypal
            >>> plan = paypal.BillingPlan("your_authorization_bearer_token")
            >>> (http_status, response_json) = plan.activate("paypal_plan_id")

        :param plan_id: the billing plan id as provided from the Paypal, i.e. P-xxxxxxxxx 
        :type plan_id: string
        :returns: the HTTP status and the response body (if any)
        :rtype: tuple(integer, dictionary)
        """
        try:
            endpoint = str(self.__base_map__['sandbox']) + str(self.__endpoint_map__['billing_plan'])
            endpoint += "/" + str(plan_id)
            payload = [
                {
                    "op": "replace",
                    "path": "/",
                    "value": {
                        "state": "ACTIVE"
                    }
                }
            ]
            request = requests.patch(endpoint, json=payload, headers=self.headers)
            try:
                return request.status_code, request.json()
            except ValueError as ex:
                print ex
                return request.status_code, dict({"message": request.reason})
        except:
            print_exc()
            return 500, dict({"error":"Internal server error"})


class BillingAgreement(Paypal):
    """BillingAgreement class that inherits the Paypal class

    For more details visit the link https://developer.paypal.com/docs/api/payments.billing-agreements
    """

    def create(self, payload):
        """Create a billing agreement in Paypal

        Usage::
            >>> from api.paypal import paypal
            >>> agreement = paypal.BillingAgreement("your_authorization_bearer_token")
            >>> (http_status, response_json) = agreement.create("plan_payload_as_json")

        :param payload: the description of billing agreement 
        :type payload: dictionary/JSON
        :returns: the HTTP status and the response body (if any)
        :rtype: tuple(integer, dictionary)
        """
        try:
            endpoint = str(self.__base_map__['sandbox']) + str(self.__endpoint_map__['billing_agreement'])
            request = requests.post(endpoint, json=payload, headers=self.headers)
            try:
                return request.status_code, request.json()
            except ValueError as ex:
                print ex
                return request.status_code, dict({"error": request.reason})
        except:
            print_exc()
            return 500, dict({"error":"Internal server error"})


    def execute(self, payment_token):
        """Execute a billing agreement after customer confirmation

        Usage::
            >>> from api.paypal import paypal
            >>> agreement = paypal.BillingAgreement("your_authorization_bearer_token")
            >>> (http_status, response_json) = agreement.execute("payment_token")

        :param payment_token: the payment_token provided from the paypal, i.e. EC-xxxxxxxxxxx
        :type payment_token: string
        :returns: the HTTP status and the response body (if any)
        :rtype: tuple(integer, dictionary)
        """
        try:
            endpoint = str(self.__base_map__['sandbox']) + str(self.__endpoint_map__['billing_agreement'])
            endpoint += "/" + str(payment_token) + "/" + "agreement-execute"
            request = requests.post(endpoint, data=None, headers=self.headers)
            try:
                return request.status_code, request.json()
            except ValueError as ex:
                print ex
                return request.status_code, dict({"error": request.reason})
        except:
            return 500, dict({"error":"Internal server error"})