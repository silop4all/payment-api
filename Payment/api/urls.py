from django.conf.urls import patterns, url, include
from api import views

endpoints = patterns(
    '',
    # listener
    url(r'^notifications/webhooks$', views.WebHook.as_view(),                        name="webhook_notifications"),
    
    # wrap paypal endpoints
    url(r'^payments/payment$', views.PaymentCreateApiView.as_view(), name="create_payment"),
    url(r'^payments/billing-plans$', views.BillingPlanCreateApiView.as_view(), name="create_billing_plan"),
    url(r'^payments/billing-plans/(?P<plan_id>[A-Z0-9\-]{10,32})$', views.BillingPlanActivateApiView.as_view(), name="activate_billing_plan"),
    url(r'^payments/billing-agreements$', views.BillingAgreementCreateApiView.as_view(),  name="create_billing_agreement"),
    url(r'^payments/billing-agreements/(?P<payment_token>[A-Z0-9\-]{10,32})/agreement-execute$', views.BillingAgreementExecuteApiView.as_view(), name="execute_billing_agreement"),

    # Reporting endpoints
    url(r'^reports/billing-agreements$', views.BillingAgreementsRetrieveApiView.as_view(), name="retrieve_billing_agreement"),
    url(r'^reports/payments$', views.PaymentsRetrieveApiView.as_view(), name="retrieve_payments"),

    #Show payment details 
    url(r'^payments/payment/(?P<payment_token>[A-Z0-9\-]{10,32})$', views.PaymentShowDetailsApiView.as_view(), name="show_payment_details"),
    url(r'^payments/payment/(?P<payment_token>[A-Z0-9\-]{10,32})/execute$', views.PaymentExecuteApiView.as_view(), name="execute_payment"),
)
