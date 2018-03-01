# -*- coding: utf-8 -*-

__base_map__ = {
    #"live": "https://api.paypal.com",
    "sandbox": "https://api.sandbox.paypal.com",
    # PayPal sandbox endpoint that will only support acceptable TLS version
    #"security-test-sandbox": "https://test-api.sandbox.paypal.com"
}

__endpoint_map__ = {
    "authentication": "/v1/oauth2/token",
    "payment": "/v1/payments/payment",
    "billing_plan": "/v1/payments/billing-plans",
    "billing_agreement": "/v1/payments/billing-agreements"
}