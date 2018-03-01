# -*- coding: utf-8 -*-

from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, filters, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

import sys
import json
import logging
import logging.handlers
from traceback import print_exc
from urlparse import urlparse
import requests
import datetime
import time

# project specific
from api.openam import OpenamAuth
from api.models import (
    RESOURCE_TYPES,
    BillingPlan,
    BillingPlanPaymentDefinition,
    BillingAgreement,
    Event,
    Sale,
    Refund,
    Payment,
    PaymentTransaction,
    Authorization,
    Capture,
    PaymentTransactionLog
)
from api import utilities
from api import serializers
from api.paypal import paypal


log = logging.getLogger(__name__)


class PaymentCreateApiView(APIView):
    """
        ---
        POST:
            omit_parameters:
              - form
            parameters:
              - name: Payment
                description: Payment related to a service
                paramType: body
                type: json
                required: true
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
                type: string
                required: true
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header
                type: string
                required: true
              - name: Paypal-Access-Token
                description: The access_token in paypal
                paramType: header
                type: string
                required: true

            type:
              id:
                required: true
                type: string
              intent:
                required: true
                type: string
                enum:
                    - sale
                    - authorization
              state:
                required: true
                type: string
              payer:
                required: true
                type: object
                properties:
                    type:
                        payment_method:
                            required: true
                            type: string
              create_time:
                required: true
                type: string
                format: date-time

            responseMessages:
              - code: 201
                message: Created
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error

            consumes:
              - application/json
            produces:
              - application/json
    """
    def post(self, request):
        """Create a payment via the Paypal Payments API 

        Use the endpoint: POST /v1/payments/payment
        """
        try:
            # Validate headers
            (headers_status, headers_message) = validateRequest(self.request.META)
            if int(headers_status) != 200:
                return Response(data=headers_message, status=headers_status)

            # Load the payment payload
            payload = json.loads(json.dumps(request.data))

            if type(payload) is not dict:
                log.warn( "OpenAM client %s has sent invalid payment payload" % self.request.META.get('HTTP_OPENAM_CLIENT'))
                return Response(data={"error": "Invalid json format", "status": status.HTTP_400_BAD_REQUEST}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the payment in paypal
            payment = paypal.Payment(self.request.META.get('HTTP_PAYPAL_ACCESS_TOKEN', None))
            (http_status, paypal_payment) = payment.create(payload)
            if int(http_status) != 201:
                log.error("OpenAM client %s failed to create a Paypal payment: HTTP status %d and message %s " %\
                    (self.request.META.get('HTTP_OPENAM_CLIENT'), http_status, json.dumps(paypal_payment)))
                return Response(data=paypal_payment, status=http_status)

            # Register the payment details in database
            approval_url = None
            for link in paypal_payment['links']:
                if link['rel'] == "approval_url":
                    approval_url = link['href']
                    break
                
            payment_id = insertPayment(self.request.META.get('HTTP_OPENAM_CLIENT'), payload, approval_url, paypal_payment)
            if payment_id < 0:
                return Response(data={"error": "Error in payment insertion"}, status=status.HTTP_400_BAD_REQUEST)
            for paypal_transaction in paypal_payment['transactions']:
                transaction_id = insertPaymentTransaction(payment_id, paypal_transaction)

            log.info("OpenAM client %s has created a payment on demand from user having token '%s*****' with id %s" %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14], paypal_payment['id']) )
            return Response(
                data={"id": payment_id, "payment": utilities.object2dict(paypal_payment, False)}, 
                status=status.HTTP_201_CREATED
            )
        except Exception as ex:
            print_exc()
            log.error("OpenAM client '%s' has failed to create a payment on demand from user having token '%s*****'" %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14]))
            log.error(str(ex))
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillingPlanCreateApiView(APIView):
    """
        ---
        POST:
            omit_parameters:
              - form
            parameters:
              - name: Billing plan
                description: Billing plan for a service
                paramType: body
                type: json
                required: true
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
                type: string
                required: true
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header
                type: string
                required: true
              - name: Paypal-Access-Token
                description: The access_token in paypal
                paramType: header
                type: string
                required: true

            responseMessages:
              - code: 201
                message: Created
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error

            consumes:
              - application/json
            produces:
              - application/json
    """
    def post(self, request):
        """Create a billing plan for recurring payments via the Paypal Billing Plan API

        Use the endpoint: POST /v1/payments/billing-plans
        """
        try:
            # Validate headers
            (headers_status, headers_message) = validateRequest(self.request.META)
            if int(headers_status) != 200:
                return Response(data=headers_message, status=headers_status)

            # Load the plan payload
            payload = self.request.data
            if not utilities.isJson(json.dumps(payload)) or type(payload) is not dict:
                log.warn( "OpenAM client %s has sent invalid billing plan payload" % self.request.META.get('HTTP_OPENAM_CLIENT'))
                return Response(
                    data={"error": "Invalid json format", "status": status.HTTP_400_BAD_REQUEST}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create a billing plan in paypal
            plan = paypal.BillingPlan(self.request.META.get('HTTP_PAYPAL_ACCESS_TOKEN', None))
            (http_status, paypal_billing_plan) = plan.create(payload)
            if int(http_status) != 201:
                log.error("OpenAM client %s failed to create a Paypal billing plan: HTTP status %d and message %s " %\
                    (self.request.META.get('HTTP_OPENAM_CLIENT'), http_status, json.dumps(paypal_billing_plan)))
                return Response(data=paypal_billing_plan, status=http_status)

            # Insert the billing plan into database
            billing_plan_id = insertBillingplan(paypal_billing_plan, self.request.META.get('HTTP_OPENAM_CLIENT'))
            if billing_plan_id < 0:
                return Response(
                    data={"error": "Error in billing plan insertion"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Insert a list of payment definitions into database 
            for paypal_payment_definition in paypal_billing_plan['payment_definitions']:
                payment_definition = insertBillingPlanPaymentDefinition(paypal_payment_definition, billing_plan_id)

            log.info("OpenAM client %s has created a billing plan on demand from user having token '%s*****' with id %s" %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14], paypal_billing_plan['id']) )
            return Response(
                data={"id": billing_plan_id, "plan": utilities.object2dict(paypal_billing_plan, False)}, 
                status=status.HTTP_201_CREATED
            )
        except Exception as ex:
            log.error("OpenAM client '%s' has failed to create a billing plan on demand from user having token '%s*****'" %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14]))
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillingPlanActivateApiView(APIView):
    """
        ---
        PATCH:
            omit_parameters:
              - form
            parameters:
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
                type: string
                required: true
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header
                type: string
                required: true
              - name: Paypal-Access-Token
                description: The access_token in paypal
                paramType: header
                type: string
                required: true
              - name: plan_id
                description: P-xxxxxxxxxxx
                paramType: path
                type: string
                required: true

            responseMessages:
              - code: 200
                message: OK
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error

            consumes:
              - application/json
            produces:
              - application/json
    """
    def patch(self, request, plan_id):
        """Activate an existing billing plan via the Paypal Billing Plan API
        """
        try:
            # Validate headers
            (headers_status, headers_message) = validateRequest(self.request.META)
            if int(headers_status) != 200:
                return Response(data=headers_message, status=headers_status)

            # Activate billing plan in Paypal
            plan = paypal.BillingPlan(self.request.META.get('HTTP_PAYPAL_ACCESS_TOKEN', None))
            (http_status, paypal_billing_plan) = plan.activate(plan_id)
            if http_status == 200:
                log.info("OpenAM client '%s' has activated the billing plan '%s'" %\
                    (self.request.META.get('HTTP_OPENAM_CLIENT'), plan_id))
            else:
                log.error("OpenAM client '%s' has failed to activate the billing plan '%s': http status %d and message %s" %\
                    (self.request.META.get('HTTP_OPENAM_CLIENT'), plan_id, http_status, json.dumps(paypal_billing_plan)))

            return Response(data=paypal_billing_plan, status=http_status) 
        except Exception as ex:
            log.error("OpenAM client '%s' has failed to activate the billing plan '%s'" %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), plan_id))
            log.error(str(ex))
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillingAgreementCreateApiView(APIView):
    """
        ---
        POST:
            omit_parameters:
              - form
            parameters:
              - name: Billing agreement
                description: Billing agreement for a service
                paramType: body
                type: json
                required: true
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
                type: string
                required: true
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header
                type: string
                required: true
              - name: Paypal-Access-Token
                description: The access_token in paypal
                paramType: header
                type: string
                required: true

            responseMessages:
              - code: 201
                message: Created
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error

            consumes:
              - application/json
            produces:
              - application/json
    """
    def post(self, request):
        """Create a billing agreement via the Paypal Billing Agreements API

        Use the endpoint: POST /v1/payments/billing-agreements
        """
        try:
            # Validate headers
            (headers_status, headers_message) = validateRequest(self.request.META)
            if int(headers_status) != 200:
                return Response(data=headers_message, status=headers_status)

            # Load agreement payload
            payload = json.loads(json.dumps(request.data))
            import ast
            payload = ast.literal_eval(payload)

            if not utilities.isJson(json.dumps(payload)) or type(payload) is not dict:
                log.warn( "No valid billing agreement payload from the openAM client %s" % self.request.META.get('HTTP_OPENAM_CLIENT'))
                return Response(
                    data={"error": "Invalid json format", "status": status.HTTP_400_BAD_REQUEST}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create a billing agreement in paypal
            agreement = paypal.BillingAgreement(self.request.META.get('HTTP_PAYPAL_ACCESS_TOKEN', None))
            (http_status, paypal_billing_agreement) = agreement.create(payload)
            if int(http_status) != 201:
                log.error("Paypal error in the attempt of billing agreement creation: HTTP status %d and message %s " % (http_status, json.dumps(paypal_billing_agreement)))
                return Response(data=paypal_billing_agreement, status=http_status)

            # Insert the billing agreement into database
            billing_agreement_id = insertBillingAgreement(paypal_billing_agreement, self.request.META.get('HTTP_OPENAM_CLIENT'))
            if billing_agreement_id < 0:
                return Response(
                    data={"error": "Error in billing agreement insertion"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            log.info("OpenAM client '%s' has created a billing agreement on behalf of user with token '%s*****' for plan '%s'." %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14], paypal_billing_agreement['plan']['id']) )
            return Response(
                data={"id": billing_agreement_id, "agreement": utilities.object2dict(paypal_billing_agreement, False)}, 
                status=status.HTTP_201_CREATED
            )
        except Exception, ex:
            log.error("OpenAM client '%s' has failed to create a billing agreement triggered by user with token '%s*****' for plan '%s'." %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14], paypal_billing_agreement['plan']['id']) )
            log.error(str(ex))
            return Response(data={"error": str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillingAgreementExecuteApiView(APIView):
    """
        ---
        POST:
            omit_parameters:
              - form
            parameters:
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
                type: string
                required: true
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header
                type: string
                required: true
              - name: Paypal-Access-Token
                description: The access_token in paypal
                paramType: header
                type: string
                required: true
              - name: payment_token
                description: EC-xxxxxxx
                paramType: path
                type: string
                required: true

            responseMessages:
              - code: 200
                message: OK
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error

            consumes:
              - application/json
            produces:
              - application/json
    """
    def post(self, request, payment_token):
        """Execute the approved billing agreement via the Paypal Billing Agreements API 

        Use the endpoint: POST /v1/payments/billing-agreements/{payment_token}/agreement-execute
        """
        try:
            # Validate headers
            (headers_status, headers_message) = validateRequest(self.request.META)
            if int(headers_status) != 200:
                return Response(data=headers_message, status=headers_status)
            
            # Execute the agreement among provider and customer
            agreement = paypal.BillingAgreement(self.request.META.get('HTTP_PAYPAL_ACCESS_TOKEN', None))
            (http_status, paypal_billing_agreement) = agreement.execute(payment_token)
            if int(http_status) not in [200, 201]:
                log.error("Paypal error in the attempt of billing agreement execution: HTTP status %d and message %s " % (http_status, json.dumps(paypal_billing_agreement)))
                return Response(data=paypal_billing_agreement, status=http_status)

            # Update agreement in database
            if "id" in paypal_billing_agreement:
                billing_agreement = BillingAgreement.objects.get(payment_token=payment_token, agreement_id__isnull=True)
                if updateBillingAgreement(billing_agreement.id, paypal_billing_agreement) < 0:
                    return Response(
                        data={"error": "Error in billing agreement execution"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

            log.info("OpenAM client '%s' has executed a billing agreement with id=%s on behalf of user with token '%s*****'" %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), paypal_billing_agreement['id'], self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14]) )
            return Response(
                data={"id": billing_agreement.id, "agreement": utilities.object2dict(paypal_billing_agreement, False)},
                status=status.HTTP_200_OK
            )
        except Exception, ex:
            print_exc()
            log.error("OpenAM client '%s' has failed to execute the billing agreement %s on behalf of user with token '%s*****' for plan '%s'." %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), payment_token, self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14]))
            log.error(str(ex))
            return Response(data={"error": str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebHook(APIView):
    """Listener for Paypal events

    Receives event notifications from the Paypal and store them in db according to their resource type
    """

    def post(self, request, *args):

        # filter notifications
        user_agent = self.request.META.get("HTTP_USER_AGENT", None)

        if len(self.request.data):
            print json.dumps(self.request.data, indent=4)
            print "\n\n"

        # retrieve notification
        payload = self.request.data
        resource_type = payload.get("resource_type").lower()
        log.info("Paypal has sent a notification with type=%s" % resource_type)

        if not Event.objects.filter(event_id=payload.get("id")).count():
            event = Event(
                event_id=payload.get("id"),
                resource_type=payload.get("resource_type"),
                event_type=payload.get("event_type"),
                json=str(self.request.data),
            )
            event.save()

        if resource_type in ["plan"]:
            resource = payload.get("resource")
            if resource['state'].lower() not in ["created"]:
                try:
                    plan = BillingPlan.objects.get(plan_id=resource["id"])
                    if plan.state.lower() != "deleted" :
                        if not updateBillingPlan(plan.id, resource):
                            return Response(
                                data={"error": "Error in billing plan update"},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                        for paypal_payment_definition in resource['payment_definitions']:
                            definition = BillingPlanPaymentDefinition.objects.get(definition_id=paypal_payment_definition["id"])
                            updateBillingPlanPaymentDefinition(definition.id, paypal_payment_definition)

                        log.info("Paypal has updated the billing plan having id=%s" % (resource["id"], resource['state']))
                        return Response(data={"resource": "plan", "id": plan.id}, status=status.HTTP_200_OK)

                    raise Exception("Unhandled plan notification")
                except Exception as ex:
                    log.error("Paypal has failed to update the billing plan having id=%s" % (resource["id"], resource['state']))
                    log.error(str(ex))
                    return Response(data={"error": "error", "id": plan.id}, status=status.HTTP_400_BAD_REQUEST)

        if resource_type in ["agreement"]:
            resource = payload.get("resource")
            try:
                agreement = BillingAgreement.objects.get(agreement_id=resource['id'])
                if agreement.state.lower() != "cancelled":
                    if not updateBillingAgreement(agreement.id, resource):
                        return Response(
                            data={"error": "Error in billing agreement update"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    log.info("Paypal has updated the billing agreement having id=%s, state=%s" % (resource['id'], resource['state']))
                    return Response(data={"resource": "agreement", "id": resource['id']}, status=status.HTTP_200_OK)

                raise Exception("Unhandled agreement notification")
            except Exception as ex:
                log.error("Paypal has failed to update the billing agreement having id=%s" % (resource["id"]))
                log.error(str(ex))
                return Response(data={"error": "error", "id": resource['id']}, status=status.HTTP_400_BAD_REQUEST)

        if resource_type in ['sale']:
            resource = payload.get("resource")
            try:
                sale = Sale.objects.filter(sale_id=resource["id"])
                if sale.count() == 1:
                    if updateSale(sale[0].id, resource) == True:
                        log.info("Paypal has updated the sale with id=%s, state=%s" % (sale[0].id, sale[0].state))
                        return Response(data={"resource": "sale"}, status=status.HTTP_200_OK)
                else:
                    sale_id = insertSale(resource)
                    log.info("Paypal has inserted a sale with id=%s" % (sale_id))
                    return Response(data={"resource": "sale"}, status=status.HTTP_201_CREATED)

                raise Exception("Unhandled sale notification")
            except Exception as ex:
                log.error("Paypal has failed to insert/update a sale")
                log.error(str(ex))
                return Response(data={"resource": "sale"}, status=status.HTTP_400_BAD_REQUEST)

        if resource_type in ["authorization"]:
            resource = payload.get("resource")
            try:
                authorization = Authorization.objects.filter(authorization_id=resource["id"])
                if authorization.count():
                    if updateSale(authorization[0].id, resource) == True:
                        log.info("Paypal has updated the authorization payment with id=%s, state=%s" % (authorization[0].id, authorization[0].state))
                        return Response(data={"resource": "authorization", "id": authorization[0].id}, status=status.HTTP_200_OK)
                else:
                    authorization_id = insertAuthorization(resource)
                    log.info("Paypal has inserted an authorization with id=%s" % (authorization_id))
                    return Response(data={"resource": resource_type, "id": authorization_id}, status=status.HTTP_201_CREATED)

                raise Exception("Unhandled authorize notification")
            except Exception as ex:
                log.error("Paypal has failed to insert/update an authorization")
                log.error(str(ex))
                return Response(data={"resource": "authorization"}, status=status.HTTP_400_BAD_REQUEST)

        if resource_type in ["capture"]:
            resource = payload.get("resource")
            try:
                capture = Capture.objects.filter(capture_id=resource["id"])
                if capture.count() == 1:
                    if updateCapture(capture.id, resource) == True:
                        log.info("Paypal has updated the capture with id=%s, state=%s" % (capture[0].id, capture[0].state))
                        return Response(data={"resource": resource_type}, status=status.HTTP_200_OK)
                else:
                    capture_id = insertCapture(resource)
                    log.info("Paypal has sent a capture with id=%s" % (resource['id']))
                    return Response(data={"resource": resource_type}, status=status.HTTP_201_CREATED)
                    
                raise Exception("Unhandled capture notification")
            except Exception as ex:
                log.error("Paypal has failed to insert/update a capture")
                log.error(str(ex))
                return Response(data={"resource": "capture"}, status=status.HTTP_400_BAD_REQUEST)



        if resource_type in ["refund"]:
            resource = payload.get("resource")
            try:
                refund = Refund.objects.filter(refund_id=resource["id"])    
                if refund.count() == 1:
                    if updateRefund(refund[0].id, resource) == True:
                        log.info("Paypal has updated the refund with id=%s, state=%s" % (refund[0].id, refund[0].state))
                        return Response(data={"resource": "refund"}, status=status.HTTP_200_OK)
                else:
                    refund_id = insertRefund(resource)
                    log.info("Paypal has inserted a refund with id=%s" % (resource["id"]))
                    return Response(data={"resource": "refund"}, status=status.HTTP_200_OK)

                raise Exception("Unhandled refund notification")
            except Exception as ex: 
                log.error("Paypal has failed to insert/update a refund")
                log.error(str(ex))
                return Response(data={"resource": "refund"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data={}, status=status.HTTP_200_OK)




# test endpoint for reporting
class BillingAgreementsRetrieveApiView(generics.ListAPIView):
    """
        Retrieve a list of billing agreements
        ---
        GET:
            omit_parameters:
              - form
            parameters:
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header

            responseMessages:
              - code: 200
                message: OK
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error

            consumes:
              - application/json
            produces:
              - application/json
    """

    serializer_class = serializers.BillingAgreementSerializer

    def get_queryset(self):
        """Retrieve the billing agreements per application and specific user
        """
        agreements_list = [10]
        agreements = BillingAgreement.objects.filter(pk__in=set(list(agreements_list)))
        return agreements


class PaymentsRetrieveApiView(generics.ListAPIView):
    """
        Retrieve a list of payments
        ---
        GET:
            omit_parameters:
              - form
            parameters:
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header

            responseMessages:
              - code: 200
                message: OK
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error

            consumes:
              - application/json
            produces:
              - application/json
    """

    serializer_class = serializers.PaymentSerializer

    def get_queryset(self):
        """Retrieve the payments per application and specific user
        """
        payments_list = [8]
        return Payment.objects.filter(pk__in=set(list(payments_list)))





def validateRequest(headers):
    """Validate the HTTP_OPENAM_CLIENT, HTTP_OPENAM_CLIENT_TOKEN and\
    HTTP_PAYPAL_ACCESS_TOKEN headers of the request

    :param headers: the headers of the request
    :type headers: dictionary
    :returns: the HTTP status and the relative message after the validation of headers
    :rtype: tuple(integer, dictionary)
    """
    try:
        openam_client = headers.get('HTTP_OPENAM_CLIENT', None)
        openam_access_token = headers.get('HTTP_OPENAM_CLIENT_TOKEN', None)
        paypal_access_token = headers.get('HTTP_PAYPAL_ACCESS_TOKEN', None)

        if openam_client == None:
            log.info("HTTP_OPENAM_CLIENT header is missing")
            return 400, {"error": "OPENAM_CLIENT (client id) of application is missing. It is provided from OpenAM."}
        if  openam_access_token == None:
            log.info("HTTP_OPENAM_CLIENT_TOKEN header is missing")
            return 400, {"error": "OPENAM_CLIENT_TOKEN of user is missing. It is provided from OpenAM after successful user authentication"}
        if paypal_access_token == None:
            log.info("HTTP_PAYPAL_ACCESS_TOKEN header is missing")
            return 400, {"error": "PAYPAL_ACCESS_TOKEN is missing"}

        # Validate user access token in OpenAM
        ows = OpenamAuth()
        openam_status, openam_response = ows.validateAccessToken(openam_access_token)
        if int(openam_status) != 200:
            log.info("Failed user authentication in OpenAM: HTTP status %d and message: %s" % (openam_status, openam_response))
            return openam_status, json.loads(openam_response)

        # Validate authorization token in Paypal
        token = paypal.Token(paypal_access_token)
        paypal_status, paypal_response = token.validate()
        if int(paypal_status) != 200:
            log.info("Failed authentication in Paypal: HTTP status %d and message: %s" % (paypal_status, paypal_response))
            return paypal_status, json.loads(json.dumps(paypal_response))

        return 200, dict()
    except Exception as ex:
        log.error("%s" % str(ex))
        return 500, {"error": "Internal server error"}

def insertPayment(client_id, payload, approval_url, paypal_payment):
    """Create a new payment entry

    :param client_id: The application's client_id according to OpenAM
    :type client_id: string
    :param payload: Part of requested payload
    :type payload: dict
    :param approval_url: The approval URL for current payment
    :type approval_url: string
    :param paypal_payment: Paypal payment
    :type paypal_payment: object
    :returns: the payment ID if it has created or -1 in any other case
    :rtype: integer
    """
    try:
        payment = Payment(
            client_id=client_id,
            pay_id=paypal_payment["id"],
            intent=paypal_payment["intent"],
            state=paypal_payment["state"],
            payment_method=paypal_payment['payer']["payment_method"],
            note_to_payer=paypal_payment["note_to_payer"],
            approval_url=approval_url,
            return_url=payload["redirect_urls"]["return_url"] if "return_url" in payload["redirect_urls"] else None,
            cancel_url=payload["redirect_urls"]["cancel_url"] if "cancel_url" in payload["redirect_urls"] else None,
            json=json.dumps(utilities.object2dict(paypal_payment, False)),
            create_time=paypal_payment["create_time"],
            update_time=paypal_payment["create_time"]
        )
        payment.save()
        return payment.id
    except Exception as ex:
        log.error("Error in payment insertion: %s" % str(ex))
        return -1

def insertPaymentTransaction(payment_id, paypal_transaction):
    """Create a new payment  transaction entry

    :param payment_id: The primary key of the relative payment
    :type payment_id: integer
    :param paypal_transaction: Part of Paypal payment
    :type paypal_transaction: object
    :returns: the payment ID if it has created or -1 in any other case
    :rtype: integer
    """
    try:
        transaction = PaymentTransaction(
            payment_id=payment_id,
            amount_value=paypal_transaction['amount']['total'],
            amount_currency=paypal_transaction['amount']['currency'],
            amount_details=json.dumps(utilities.object2dict(paypal_transaction['amount']['details'], False)) if 'details' in paypal_transaction['amount'] else '{}',
            description=paypal_transaction['description'] if 'description' in paypal_transaction else None,
            custom=paypal_transaction['custom'] if 'custom' in paypal_transaction else None,
            invoice_number=paypal_transaction['invoice_number'] if 'invoice_number' in paypal_transaction else None,
            soft_descriptor=paypal_transaction['soft_descriptor'] if 'soft_descriptor' in paypal_transaction else None,
            item_list=json.dumps(utilities.object2dict(paypal_transaction['item_list'], False)),
            json=json.dumps(utilities.object2dict(paypal_transaction, False))
        )
        transaction.save()
        return transaction.id
    except Exception as ex:
        log.error("Error in payment transaction insertion: %s" % str(ex))
        return -1

def insertBillingplan(paypal_billing_plan, client_id):
    """Create a new billing plan entry

    :param paypal_billing_plan: Paypal billing plan
    :type paypal_billing_plan: object
    :param client_id: the application's client_id provided by OpenAM
    :type client_id: string
    :returns: the billing plan ID if it has created or -1 in any other case
    :rtype: integer
    """
    try:
        try:
            merchant_preferences_fee_value = paypal_billing_plan['merchant_preferences']['setup_fee']['value']
        except:
            merchant_preferences_fee_value = None
        try:
            merchant_preferences_fee_currency = paypal_billing_plan['merchant_preferences']['setup_fee']['currency']
        except:
            merchant_preferences_fee_currency = None
        try:
            return_url = paypal_billing_plan['merchant_preferences']['return_url']
        except:
            return_url = None
        try:
            cancel_url = paypal_billing_plan['merchant_preferences']['cancel_url']
        except:
            cancel_url = None

        billing_plan = BillingPlan(
            client_id=client_id,
            plan_id=paypal_billing_plan['id'],
            name=paypal_billing_plan['name'],
            description=paypal_billing_plan['description'],
            type=paypal_billing_plan['type'],
            state=paypal_billing_plan['state'],
            merchant_preferences_fee_value = merchant_preferences_fee_value,
            merchant_preferences_fee_currency =merchant_preferences_fee_currency,
            return_url=return_url,
            cancel_url=cancel_url,
            json=json.dumps(utilities.object2dict(paypal_billing_plan, False)),
            create_time=paypal_billing_plan["create_time"],
            update_time=paypal_billing_plan["create_time"]
        )
        billing_plan.save()

        return billing_plan.id
    except Exception as ex:
        log.error("Error in billing plan insertion: %s" % str(ex))
        return -1

def updateBillingPlan(pk, paypal_billing_plan):
    """Update an existing billing plan entry

    :param pk: the primary key of the billing plan
    :type pk: integer 
    :param paypal_billing_plan: Paypal billing plan
    :type paypal_billing_plan: object
    :returns: True for successful update or False in any other case
    :rtype: bool
    """
    try:
        try:
            merchant_preferences_fee_value = paypal_billing_plan['merchant_preferences']['setup_fee']['value']
        except:
            merchant_preferences_fee_value = None
        try:
            merchant_preferences_fee_currency = paypal_billing_plan['merchant_preferences']['setup_fee']['currency']
        except:
            merchant_preferences_fee_currency = None
        try:
            return_url = paypal_billing_plan['merchant_preferences']['return_url']
        except:
            return_url = None
        try:
            cancel_url = paypal_billing_plan['merchant_preferences']['cancel_url']
        except:
            cancel_url = None

        # update plan
        BillingPlan.objects.filter(pk=pk).update(
            name=paypal_billing_plan['name'],
            description=paypal_billing_plan['description'],
            type=paypal_billing_plan['type'],
            state=paypal_billing_plan['state'],
            merchant_preferences_fee_value = merchant_preferences_fee_value,
            merchant_preferences_fee_currency =merchant_preferences_fee_currency,
            return_url=return_url,
            cancel_url=cancel_url,
            json=json.dumps(utilities.object2dict(paypal_billing_plan, False)),
            update_time=paypal_billing_plan["update_time"]
        )
        return True
    except Exception as ex:
        log.error("Error in billing plan modification (is:=%d): %s" % (pk, str(ex)) )
        return False

def insertBillingPlanPaymentDefinition(paypal_payment_definition, billing_plan_id):
    """Create a new billing plan payment definition 

    :param paypal_payment_definition: Paypal billing plan payment definition
    :type paypal_payment_definition: object
    :param billing_plan_id: ID of the associated billing plan
    :type billing_plan_id: integer
    :returns: the billing plan payment definition ID if it has created or -1 in any other case
    :rtype: integer
    """
    try:
        try:
            frequency_interval = paypal_payment_definition['frequency_interval']
        except:
            frequency_interval = None
        try:
            cycles = paypal_payment_definition['cycles']
        except:
            cycles = None
        try:
            charge_models = paypal_payment_definition['charge_models']
        except:
            charge_models = dict()
        try:
            amount_value = paypal_payment_definition['amount']['value']
        except:
            amount_value = None
        try:
            amount_currency = paypal_payment_definition['amount']['currency']
        except:
            amount_currency = None

        payment_definition = BillingPlanPaymentDefinition(
            billing_plan_id=billing_plan_id,
            definition_id=paypal_payment_definition['id'],
            name=paypal_payment_definition['name'],
            type=paypal_payment_definition['type'],
            frequency=paypal_payment_definition['frequency'],
            frequency_interval=frequency_interval,
            cycles=cycles,
            charge_models=json.dumps(utilities.object2dict(charge_models, False)),
            amount_value=amount_value,
            amount_currency=amount_currency,
            json=json.dumps(utilities.object2dict(paypal_payment_definition, False))
        )
        payment_definition.save()
        return payment_definition.id
    except Exception as ex:
        log.error("Error in billing plan's payment definition insertion: %s" % str(ex))
        return -1

def updateBillingPlanPaymentDefinition(pk, paypal_payment_definition):
    """Update an existing payment definition of a billing plan

    :param pk: the primary key of the payment definition (associated with a billing plan)
    :type pk: integer 
    :param paypal_payment_definition: Paypal billing plan payment definition
    :type paypal_payment_definition: object
    :returns: True for successful update or False in any other case
    :rtype: bool
    """
    try:
        try:
            frequency_interval = paypal_payment_definition['frequency_interval']
        except:
            frequency_interval = None
        try:
            cycles = paypal_payment_definition['cycles']
        except:
            cycles = None
        try:
            charge_models = paypal_payment_definition['charge_models']
        except:
            charge_models = dict()
        try:
            amount_value = paypal_payment_definition['amount']['value']
        except:
            amount_value = None
        try:
            amount_currency = paypal_payment_definition['amount']['currency']
        except:
            amount_currency = None

        BillingPlanPaymentDefinition.objects.filter(pk=pk).update(
            name=paypal_payment_definition['name'],
            type=paypal_payment_definition['type'],
            frequency=paypal_payment_definition['frequency'],
            frequency_interval=frequency_interval,
            cycles=cycles,
            charge_models=json.dumps(utilities.object2dict(charge_models, False)),
            amount_value=amount_value,
            amount_currency=amount_currency,
            json=json.dumps(utilities.object2dict(paypal_payment_definition, False))
        )
        return True
    except Exception as ex:
        log.error("Error in billing plan's payment definition modification (pk:=%d): %s" % (pk, str(ex)) )
        return False

def insertBillingAgreement(paypal_billing_agreement, client_id):
    """Create a new billing agreement (related to existing plan)

    :param paypal_billing_agreement: Paypal billing agreement
    :type paypal_billing_agreement: object
    :param client_id: The application's client_id provided by OpenAM
    :type client_id: string
    :returns: the billing agreement ID if it has created or -1 in any other case
    :rtype: integer
    """
    try:
        try:
            payer_id = paypal_billing_agreement['payer']['payer_info']['payer_id']
        except:
            payer_id = None
        try:
            payer_email = paypal_billing_agreement['payer']['payer_info']['email']
        except:
            payer_email = None
        try:
            payer_status = paypal_billing_agreement['payer']['status']
        except:
            payer_status = None

        payment_token = None
        for link in paypal_billing_agreement['links']:
            if link['rel'] == "approval_url":
                approval_url = link['href']
                l = urlparse(link['href'])
                payment_token = l.query.split('&')[-1].split('=')[-1]
                break

        agreement = BillingAgreement(
            client_id = client_id,
            agreement_id = None,
            payment_token=payment_token,
            name = paypal_billing_agreement['name'],
            description = paypal_billing_agreement['description'],
            plan_id = BillingPlan.objects.get(plan_id=paypal_billing_agreement['plan']['id']).id,
            payment_method = None, 
            payer_id = payer_id,
            payer_email = payer_email,
            payer_status = None,
            num_cycles_completed = None,
            num_cycles_remaining = None,
            failed_payment_count = None,
            json = json.dumps(utilities.object2dict(paypal_billing_agreement, False)),
            start_date=paypal_billing_agreement['start_date']
        )
        agreement.save()

        return agreement.id
    except Exception as ex:
        log.error("Error in billing agreement insertion: %s" % str(ex))
        return -1

def updateBillingAgreement(pk, paypal_billing_agreement):
    """Update the billing agreement with the primary key pk

    :param pk: ID of the associated billing agreement
    :type pk: integer
    :param paypal_billing_agreement: Paypal billing agreement
    :type paypal_billing_agreement: object
    :returns: True for success update; False in any other case
    :rtype: bool
    """
    try:
        try:
            payer_id = paypal_billing_agreement['payer']['payer_info']['payer_id']
        except:
            payer_id = None
        try:
            payer_email = paypal_billing_agreement['payer']['payer_info']['email']
        except:
            payer_email = None
        try:
            payer_status = paypal_billing_agreement['payer']['status']
        except:
            payer_status = None
        try:
            num_cycles_completed = paypal_billing_agreement.get('agreement_details', {}).get('num_cycles_completed', None)
        except:
            num_cycles_completed = None
        try:
            num_cycles_remaining = paypal_billing_agreement.get('agreement_details', {}).get('num_cycles_remaining', None)
        except:
            num_cycles_remaining = None
        try:
            failed_payment_count = paypal_billing_agreement.get('agreement_details', {}).get('failed_payment_count', None)
        except:
            failed_payment_count = None

        agreement = BillingAgreement.objects.filter(pk=pk).update(
            agreement_id = paypal_billing_agreement['id'],
            description = paypal_billing_agreement['description'],
            state = paypal_billing_agreement.get('state', None),
            payment_method = paypal_billing_agreement['payer']['payment_method'],
            payer_id = payer_id,
            payer_email = payer_email,
            payer_status = payer_status,
            num_cycles_completed = num_cycles_completed,
            num_cycles_remaining = num_cycles_remaining,
            failed_payment_count = failed_payment_count,
            json = json.dumps(utilities.object2dict(paypal_billing_agreement, False))
        )
        return True
    except Exception as ex:
        log.error("Error in billing agreement modification (pk:=%d): %s" % (pk, str(ex)) )
        return False

def insertSale(paypal_sale):
    """Create a new sale. It is associated either with a billing agreement or a payment.

    :param paypal_sale: Paypal payment as sale intent
    :type paypal_sale: object
    :returns: the sale ID if it has created or -1 in any other case
    :rtype: integer
    """
    try:
        sale = Sale(
            sale_id=paypal_sale['id'],
            amount_value=paypal_sale.get('amount', {}).get('total', None),
            amount_currency=paypal_sale.get('amount', {}).get('currency', None),
            state=paypal_sale['state'],
            transaction_value=paypal_sale.get('transaction_fee', {}).get('value', None),
            transaction_currency=paypal_sale.get('transaction_fee', {}).get('currency', None),
            billing_agreement_id=paypal_sale.get('billing_agreement_id', None),
            payment_mode=paypal_sale['payment_mode'],
            parent_payment=paypal_sale.get('parent_payment', None),
            reason_code=paypal_sale.get('reason_code', None),
            protection_eligibility=paypal_sale.get('protection_eligibility', None),
            protection_eligibility_type=paypal_sale.get('protection_eligibility_type', None),
            json=json.dumps(utilities.object2dict(paypal_sale, False)),
            create_time=paypal_sale["create_time"],
            update_time=paypal_sale["update_time"]
        )
        sale.save()
        return sale.sale_id
    except Exception as ex:
        log.error("Error in sale insertion: %s" % str(ex))
        return -1

def updateSale(pk, paypal_sale):
    """Update the sale with a specific primary key

    :param pk: ID of the associated sale
    :type pk: integer
    :param paypal_sale: Paypal sale
    :type paypal_sale: object
    :returns: True for success update; False in any other case
    :rtype: bool
    """
    try:
        Sale.objects.filter(pk=pk).update(
            amount_value=paypal_sale['amount']['total'],
            amount_currency=paypal_sale['amount']['currency'],
            state=paypal_sale['state'],
            transaction_value=paypal_sale['transaction_fee']['value'] if 'transaction_fee' in paypal_sale else None,
            transaction_currency=paypal_sale['transaction_fee']['currency'] if 'transaction_fee' in paypal_sale else None,
            billing_agreement_id=paypal_sale['billing_agreement_id'] if 'billing_agreement_id' in paypal_sale else None,
            payment_mode=paypal_sale['payment_mode'],
            parent_payment=paypal_sale['parent_payment'] if 'parent_payment' in paypal_sale else None,
            reason_code=paypal_sale['reason_code'] if 'reason_code' in paypal_sale else None,
            protection_eligibility=paypal_sale['protection_eligibility'] if 'protection_eligibility' in paypal_sale else None,
            protection_eligibility_type=paypal_sale['protection_eligibility_type'] if 'protection_eligibility_type' in paypal_sale else None,
            json=json.dumps(utilities.object2dict(paypal_sale, False)),
            create_time=paypal_sale["create_time"],
            update_time=paypal_sale["update_time"]
        )
        return True
    except Exception as ex:
        log.error("An exception has been arisen in the modification of the sale_id=%s. %s" % (paypal_sale['id'], str(ex)))
        return False

def insertAuthorization(paypal_authorization):
    """Create a new authorization. It is associated with a future payment.

    :param paypal_authorization: Paypal payment as authorization intent
    :type paypal_authorization: dictionary
    :returns: the authorization ID if it has created or -1 in any other case
    :rtype: integer
    """
    try:
        authorization = Authorization(
            authorization_id=paypal_authorization['id'],
            amount_value=paypal_authorization.get('amount', {}).get('total', None),
            amount_currency=paypal_authorization.get('amount', {}).get('currency', None),
            state=paypal_authorization['state'],
            transaction_value=paypal_authorization.get('transaction_fee', {}).get('value', None),
            transaction_currency=paypal_authorization.get('transaction_fee', {}).get('currency', None),
            payment_mode=paypal_authorization['payment_mode'],
            parent_payment=paypal_authorization.get('parent_payment', None),
            reason_code=paypal_authorization.get('reason_code', None),
            protection_eligibility=paypal_authorization.get('protection_eligibility', None),
            protection_eligibility_type=paypal_authorization.get('protection_eligibility_type', None),
            json=json.dumps(utilities.object2dict(paypal_authorization, False)),
            valid_until=paypal_authorization["valid_until"],
            create_time=paypal_authorization["create_time"],
            update_time=paypal_authorization["update_time"]
        )
        authorization.save()
        return authorization.authorization_id
    except Exception as ex:
        log.error("Error in authorization insertion: %s" % str(ex))
        return -1

def updateAuthorization(pk, paypal_authorization):
    """Update the authorization with a specific primary key

    :param pk: ID of the associated authorization
    :type pk: integer
    :param paypal_authorization: Paypal authorization
    :type paypal_authorization: object
    :returns: True for success update; False in any other case
    :rtype: bool
    """
    try:
        Authorization.objects.filter(pk=pk).update(
            amount_value=paypal_authorization['amount']['total'],
            amount_currency=paypal_authorization['amount']['currency'],
            state=paypal_authorization['state'],
            transaction_value=paypal_authorization['transaction_fee']['value'] if 'transaction_fee' in paypal_authorization else None,
            transaction_currency=paypal_authorization['transaction_fee']['currency'] if 'transaction_fee' in paypal_authorization else None,
            payment_mode=paypal_authorization['payment_mode'],
            parent_payment=paypal_authorization['parent_payment'] if 'parent_payment' in paypal_authorization else None,
            reason_code=paypal_authorization['reason_code'] if 'reason_code' in paypal_authorization else None,
            protection_eligibility=paypal_authorization['protection_eligibility'] if 'protection_eligibility' in paypal_authorization else None,
            protection_eligibility_type=paypal_authorization['protection_eligibility_type'] if 'protection_eligibility_type' in paypal_authorization else None,
            json=json.dumps(utilities.object2dict(paypal_authorization, False)),
            valid_until=paypal_authorization["valid_until"],
            create_time=paypal_authorization["create_time"],
            update_time=paypal_authorization["update_time"]
        )
        return True
    except Exception as ex:
        log.error("Error in authorization modification (pk:=%d): %s" % (pk, str(ex)) )
        return False


def insertCapture(paypal_capture):
    """Insert a capture for an authorization

    :param paypal_capture: Paypal capture
    :type paypal_capture: dictionary
    :returns: The capture id on success; Otherwise, -1 
    :rtype: integer
    """
    try:
        capture = Capture(
            capture_id=paypal_capture.get('id', None),
            amount_value=paypal_capture.get('amount', {}).get('total', None),
            amount_currency=paypal_capture.get('amount', {}).get('currency', None),
            state=paypal_capture['state'],
            transaction_fee_value=paypal_capture.get('transaction_fee', {}).get('value', None),
            transaction_fee_currency=paypal_capture.get('transaction_fee', {}).get('currency', None),
            is_final_capture=paypal_capture.get('is_final_capture', False),
            reason_code=paypal_capture.get('reasonCode', None),
            parent_payment=paypal_capture.get('parent_payment', None),
            json=json.dumps(utilities.object2dict(paypal_capture, False)),
            create_time=paypal_capture['create_time'],
            update_time=paypal_capture.get('update_time', paypal_capture['create_time'])
        )
        capture.save()
        return capture.id
    except Exception as ex:
        log.error("Error in capture insertion: %s" % str(ex))
        return -1

def updateCapture(pk, paypal_capture):
    """Update an existing capture (associated with an authorization payment)

    :param pk: The capture id
    :type pk: integer
    :param paypal_capture: Paypal capture
    :type paypal_capture: dictionary
    :returns: True for success update; False in any other case
    :rtype: bool
    """
    try:
        capture = Capture.objects.filter(pk=pk).update(
            amount_value=paypal_capture.get('amount', {}).get('total', None),
            amount_currency=paypal_capture.get('amount', {}).get('currency', None),
            state=paypal_capture['state'],
            transaction_fee_value=paypal_capture.get('transaction_fee', {}).get('value', None),
            transaction_fee_currency=paypal_capture.get('transaction_fee', {}).get('currency', None),
            is_final_capture=paypal_capture.get('is_final_capture', False),
            reason_code=paypal_capture.get('reasonCode', None),
            parent_payment=paypal_capture.get('parent_payment', None),
            json=json.dumps(utilities.object2dict(paypal_capture, False)),
            create_time=paypal_capture['create_time'],
            update_time=paypal_capture.get('update_time', paypal_capture['create_time'])
        )
        return True
    except Exception as ex:
        log.error("Error in capture modification: %s" % str(ex))
        return False

def insertRefund(paypal_refund):
    """Store a refund action. It is associated either with a billing agreement or a payment transaction.

    :param paypal_refund: Paypal refund
    :type paypal_refund: dictionary
    :returns: the refund ID if it has created or -1 in any other case
    :rtype: integer
    """
    try:
        refund = Refund(
            sale_id=paypal_refund.get('sale_id', None),
            capture_id=paypal_refund.get('capture_id', None),
            description=paypal_refund.get('description', None),
            amount_value=paypal_refund.get('amount', {}).get('total', None),
            amount_currency=paypal_refund.get('amount', {}).get('currency', None),
            state=paypal_refund['state'],
            reason=paypal_refund.get('reason', None),
            parent_payment=paypal_refund.get('parent_payment', None),
            invoice_number=paypal_refund.get('invoice_number', None),
            custom=paypal_refund.get('custom', None),
            json=json.dumps(utilities.object2dict(paypal_refund, False)),
            create_time=paypal_refund['create_time'],
            update_time=paypal_refund.get('update_time', paypal_refund['create_time'])
        )
        refund.save()
        return refund.id
    except Exception as ex:
        log.error("Error in refund insertion: %s" % str(ex))
        return -1

def updateRefund(pk, paypal_refund):
    """Update the a refund

    :param pk: ID of refund entry
    :type pk: integer    
    :param paypal_refund: Paypal refund
    :type paypal_refund: dictionary
    :returns: True for update or False in any other case
    :rtype: bool
    """

    try:
        refund = Refund.objects.filter(pk=pk).update(
            description=paypal_refund.get('description', None),
            amount_value=paypal_refund.get('amount', {}).get('total', None),
            amount_currency=paypal_refund.get('amount', {}).get('currency', None),
            state=paypal_refund['state'],
            reason=paypal_refund.get('reason', None),
            parent_payment=paypal_refund.get('parent_payment', None),
            invoice_number=paypal_refund.get('invoice_number', None),
            custom=paypal_refund.get('custom', None),
            json=json.dumps(utilities.object2dict(paypal_refund, False)),
            create_time=paypal_refund['create_time'],
            update_time=paypal_refund.get('update_time', paypal_refund['create_time'])
        )
        refund.save()
        return True
    except Exception as ex:
        log.error("Error in refund modification: %s" % str(ex))
        return False


class PaymentShowDetailsApiView(APIView):
    """
        Payment details
        ---
        GET:
            omit_parameters:
              - form
            parameters:
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header
              - name: Paypal-Access-Token
                description: The access_token in paypal
                paramType: header
              - name: authorization
                paramType: header
                required: true
            responseMessages:
              - code: 200
                message: Success
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error
            consumes:
              - application/json
            produces:
              - application/json

    """
    def get(self, request, payment_token):
        """
        Show payment details via the Paypal Payments API 

        Use the endpoint: GET /v1/payments/payment
        """
        try:
            if 'HTTP_AUTHORIZATION' in request.META:
                auth = request.META['HTTP_AUTHORIZATION'].split()
                if len(auth) == 2:
                    if auth[0].lower() == "bearer":
                        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer '+ auth[1]}
                        id = insertPaymentTransactionLog(payment_token, "info", None)
                        paypal_response = requests.get('https://api.sandbox.paypal.com/v1/payments/payment/' + payment_token, headers=headers)
                        paypal_data = paypal_response.json()
                        updatePaymentTransactionLog(id, json.dumps(paypal_data))
                        return Response(paypal_data, status = paypal_response.status_code)
            return Response(data={"error": auth}, status = status.HTTP_400_BAD_REQUEST)
        except Exception as ex:
            log.error("PaymentShowDetailsApiView: Error: %s" % str(ex))
            raise ex
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PaymentExecuteApiView(APIView):
    """
        Execute Payment
        ---
        POST:
            omit_parameters:
              - form
            parameters:
              - name: Openam-Client
                description: The application's client_id in OpenAM
                paramType: header
                type: string
                required: true
              - name: Openam-Client-Token
                description: The user's access_token in the integrated with OpenAM application
                paramType: header
                type: string
                required: true
              - name: Paypal-Access-Token
                description: The access_token in paypal
                paramType: header
                type: string
                required: true
              - name: payment_token
                description: PAY-xxxxxxxxxxx
                paramType: path
                type: string
                required: true                

            responseMessages:
              - code: 200
                message: Success
              - code: 204
                message: No content
              - code: 301
                message: Moved permanently
              - code: 400
                message: Bad Request
              - code: 401
                message: Unauthorized
              - code: 403
                message: Forbidden
              - code: 404
                message: Not found
              - code: 500
                message: Internal Server Error
            consumes:
              - application/json
            produces:
              - application/json

    """
    def post(self, request, payment_token):
        """
        Show payment details via the Paypal Payments API 

        Use the endpoint: POST /v1/payments/payment
        """
        #try:
        #    if 'HTTP_AUTHORIZATION' in request.META:
        #        auth = request.META['HTTP_AUTHORIZATION'].split()
        #        if len(auth) == 2:
        #            if auth[0].lower() == "bearer":
        #                headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer '+ auth[1]}
        #                json_data = json.dumps(self.request.data)
        #                id = insertPaymentTransactionLog(payment_token, "execute", json_data )
        #                paypal_response = requests.post('https://api.sandbox.paypal.com/v1/payments/payment/' + payment_token +'/execute', headers=headers, data=json_data)
        #                paypal_data = paypal_response.json()
        #                updatePaymentTransactionLog(id, json.dumps(paypal_data))
        #                return Response(paypal_data, status = paypal_response.status_code)
        #    return Response(data={"error": auth}, status = status.HTTP_400_BAD_REQUEST)
        #except Exception as ex:
        #    log.error("PaymentShowDetailsApiView: Error: %s" % str(ex))
        #    raise ex
        #    return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            # Validate headers
            (headers_status, headers_message) = validateRequest(self.request.META)
            if int(headers_status) != 200:
                return Response(data=headers_message, status=headers_status)

            # Load the payment payload
            payload = json.loads(json.dumps(request.data))
            log.debug(payload)

            if type(payload) is not dict:
                log.warn( "OpenAM client %s has sent invalid payment payload" % self.request.META.get('HTTP_OPENAM_CLIENT'))
                return Response(data={"error": "Invalid json format", "status": status.HTTP_400_BAD_REQUEST}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the payment in paypal
            payment = paypal.Payment(self.request.META.get('HTTP_PAYPAL_ACCESS_TOKEN', None))
            (http_status, paypal_payment) = payment.execute(payment_token, payload)
            if int(http_status) != 200:
                log.error("OpenAM client %s failed to execeute the Paypal payment: HTTP status %d and message %s " %\
                    (self.request.META.get('HTTP_OPENAM_CLIENT'), http_status, json.dumps(paypal_payment)))
                return Response(data=paypal_payment, status=http_status)

            return Response(
                data=utilities.object2dict(paypal_payment, False), 
                status=status.HTTP_200_OK
            )
        except Exception as ex:
            print_exc()
            log.error("OpenAM client '%s' has failed to create a payment on demand from user having token '%s*****'" %\
                 (self.request.META.get('HTTP_OPENAM_CLIENT'), self.request.META.get('HTTP_OPENAM_CLIENT_TOKEN')[0:14]))
            log.error(str(ex))
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def insertPaymentTransactionLog(_payment_id, _transaction_type, request):
    try:
        logEntry = PaymentTransactionLog(
            payment_id=_payment_id,
            transaction_type=_transaction_type,
            request_json=request,
            create_time=datetime.datetime.utcnow(),
            update_time=datetime.datetime.utcnow()
        )
        logEntry.save()
        return logEntry.id
    except Exception as ex:
        log.error("Error in insertPaymentTransactionLog: %s" % str(ex))
        raise ex
        return -1


def updatePaymentTransactionLog(pk, response):

    try:
        PaymentTransactionLog.objects.filter(pk=pk).update(
            response_json=response,
            update_time=datetime.datetime.utcnow()
        )
        return True
    except Exception as ex:
        log.error("Error in updatePaymentTransactionLog: %s" % str(ex))
        raise ex
        return False
