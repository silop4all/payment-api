# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import ugettext as _


RESOURCE_TYPES = [
    "agreement", # !Agreement
    "plan"
    "refund",
    "sale",
    "payment",
    "capture",
    "authorization",
]

BILLING_PLAN_TYPES = [
    "FIXED",
    "INFINITE"
]

BILLING_PLAN_FREQUENCY = [
    'day',
    'month',
    'week',
    'year'
]

BILLING_PLAN_STATES = [
    "CREATED",
    "ACTIVE",
    "INACTIVE",
    "DELETED"
]

BILLING_AGREEMENT_STATES = [
    "Active",
    "Cancelled",
    "Completed",
    "Created",
    "Pending",
    "Reactivated",
    "Suspended"
]

BILLING_AGREEMENT_PAYMENT_METHOD = [
    "credit_card",
    "paypal"
]

SALE_STATES = [
    "completed",
    "partially_refused",
    "pending",
    "refunded",
    "denied"
]

SALE_PAYMENT_MODE = [
    "INSTANT_TRANSFER",
    "MANUAL_BANK_TRANSFER",
    "DELAYED_TRANSFER",
    "ECHECK"
]

REFUND_STATES = [
    "pending",
    "completed",
    "failed"
]

PAYMENT_INTENTS = [
    "sale",
    "authorize",
    "order"
]

PAYMENT_STATES = [
    "created",
    "approved",
    "failed"
]


class ResourceType(models.Model):
    """
    Keep the Paypal resource types
    """
    type = models.CharField(max_length=32, blank=False, null=False)
    
    class Meta :
        verbose_name = _("Resource Type")
        verbose_name_plural = _("Resource Types")

    def __unicode__(self):
        """ Get the type """
        return "%d" % (self.type)


class EventType(models.Model):
    """
    Keep the Paypal event types
    """
    type = models.CharField(max_length=32, blank=False, null=False)
    
    class Meta :
        verbose_name = _("Event Type")
        verbose_name_plural = _("Event Types")

    def __unicode__(self):
        """ Get the event type """
        return "%d" % (self.type)


class Event(models.Model):
    """
    Keep the webhook events
    """
    event_id = models.CharField(max_length=64, null=False, blank=False)
    resource_type = models.CharField(max_length=32, null=False, blank=False)
    event_type = models.CharField(max_length=80, null=False, blank=False)
    json = models.TextField()
    create_date = models.DateTimeField(auto_now_add=True)

    class Meta :
        db_table = "webhook_event"
        verbose_name = _("Event")
        verbose_name_plural = _("Events")

    def __unicode__(self):
        """ Get the title """
        return "%d (%d - %d)" % (self.event_id, self.resource_type, self.event_type)


class BillingPlan(models.Model):
    """
    Keep the billing plans
    """
    client_id = models.CharField(max_length=128, null=False, blank=False, help_text="username of the application in OpenAM")
    plan_id = models.CharField(max_length=32, null=False, blank=False, unique=True, help_text="resource.id")
    name = models.CharField(max_length=128, null=False, blank=False)
    description = models.CharField(max_length=128, null=False, blank=False)
    type = models.CharField(max_length=20, null=False, blank=False)
    state = models.CharField(max_length=20, null=False, blank=False)
    merchant_preferences_fee_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="merchant_preferences.setup_fee.value")
    merchant_preferences_fee_currency = models.CharField(max_length=8, null=True, blank=True, help_text="merchant_preferences.setup_fee.currency")
    return_url = models.URLField(max_length=1000, null=False, blank=False)
    cancel_url = models.URLField(max_length=1000, null=False, blank=False)
    notify_url = models.URLField(max_length=1000, null=True, blank=True, help_text="reserved for future usage")
    json = models.TextField()
    create_time = models.DateTimeField()
    update_time = models.DateTimeField()
    
    class Meta :
        db_table = "billing_plan"
        verbose_name = _("Billing Plan")
        verbose_name_plural = _("Billing Plans")

    def __unicode__(self):
        """ Get the title """
        return "%d - %d" % (self.p_id, self.name)


class BillingPlanPaymentDefinition(models.Model):
    """
    Keep the payment definition included in a billing plan
    """
    billing_plan = models.ForeignKey(BillingPlan, on_delete=models.CASCADE)
    definition_id = models.CharField(max_length=128, null=False, blank=False)
    name = models.CharField(max_length=128, null=False, blank=False)
    type = models.CharField(max_length=10, null=False, blank=False)
    frequency = models.CharField(max_length=10, null=False, blank=False, help_text="BILLING_PLAN_FREQUENCY")
    frequency_interval = models.CharField(max_length=2, null=True, blank=True)
    cycles = models.CharField(max_length=3, null=True, blank=True)
    charge_models = models.CharField(max_length=255, null=False, blank=False)
    amount_value = models.DecimalField(max_digits=12, decimal_places=4, help_text="payment_definitions[i].charge_models[j].amount.total")
    amount_currency = models.CharField(max_length=8, null=False, blank=False, help_text="payment_definitions[i].charge_models[j].amount.currency")
    json = models.TextField()
    
    class Meta :
        db_table = "billing_plan_payment_definition"
        verbose_name = _("Payment Definition for Billing Plan")
        verbose_name_plural = _("Payment Definitions for Billing Plan")

    def __unicode__(self):
        """ Get the title """
        return "%d (%d)" % (self.definition_id, self.billing_plan.plan_id)


class BillingAgreement(models.Model):
    """
    Keep the billing agreement held among provider and buyer for a recurring payment
    """
    client_id = models.CharField(max_length=128, null=False, blank=False, help_text="username of the application in OpenAM")
    agreement_id = models.CharField(max_length=128, null=True, blank=True, unique=True, help_text="resource.id")
    payment_token = models.CharField(max_length=128, null=False, blank=False, help_text="EC-xxxx")
    name = models.CharField(max_length=128, null=False, blank=False)
    description = models.CharField(max_length=128, null=False, blank=False)
    state = models.CharField(max_length=128, null=True, blank=True, help_text="resource.state")
    plan = models.ForeignKey(BillingPlan)
    payment_method = models.CharField(max_length=32, null=True, blank=True)
    payer_id = models.CharField(max_length=64, null=True, blank=True)
    payer_email = models.EmailField(max_length=64, null=True, blank=True)
    payer_status = models.CharField(max_length=32, null=True, blank=True)
    num_cycles_completed = models.IntegerField(null=True, blank=True,)
    num_cycles_remaining = models.IntegerField(null=True, blank=True,)
    failed_payment_count = models.IntegerField(null=True, blank=True,)
    json = models.TextField()
    start_date = models.DateTimeField()
    
    class Meta :
        db_table = "billing_agreement"
        verbose_name = _("Billing Agreement")
        verbose_name_plural = _("Billing Agreements")

    def __unicode__(self):
        """ Get the Billing agreement """
        return "%d (%d - %d)" % (self.agreement_id, self.payer_email, self.state)


class Payment(models.Model):
    """Keep the payment transactions:
        1. sale
        2. authorize
        3. order
    """
    client_id = models.CharField(max_length=128, null=False, blank=False, help_text="username of the application in OpenAM")
    pay_id = models.CharField(max_length=128, null=False, help_text="id from paypal api, PAY-xxx")
    intent = models.CharField(max_length=16, null=False, blank=False)
    state = models.CharField(max_length=10, null=False, blank=False)
    payment_method = models.CharField(max_length=64, null=False, blank=False, default="paypal")
    note_to_payer = models.CharField(max_length=165, null=False, blank=False)
    approval_url = models.URLField(max_length=400, null=True, blank=True, help_text="application oriented")
    return_url = models.URLField(max_length=400, null=False, blank=False)
    cancel_url = models.URLField(max_length=400, null=False, blank=False)
    json = models.TextField()
    create_time = models.DateTimeField()
    update_time = models.DateTimeField()

    class Meta :
        db_table = "payment"
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")

    def __unicode__(self):
        """ Get the payment descriptor """
        return "%d (%d , %d, %d)" % (self.pay_id, self.intent, self.state, self.client_id)


class PaymentTransaction(models.Model):
    """
    Keep the transaction included in the payment request
    """
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    amount_value = models.DecimalField(max_digits=12, decimal_places=4, help_text="transactions[i].amount.total")
    amount_currency = models.CharField(max_length=8, null=False, blank=False, help_text="transactions[i].amount.currency")
    amount_details = models.TextField(max_length=500, help_text="JSON format")
    description = models.CharField(max_length=127, null=False, blank=False)
    custom = models.CharField(max_length=127, null=True, blank=True)
    invoice_number = models.CharField(max_length=127, null=True, blank=True)
    soft_descriptor = models.CharField(max_length=22, null=True, blank=True)
    item_list = models.TextField(max_length=500)
    json = models.TextField(max_length=2000)

    class Meta :
        db_table = "payment_transaction"
        verbose_name = _("Payment Transaction")
        verbose_name_plural = _("Payment Transactions")

    def __unicode__(self):
        """ Get the transaction descriptor """
        return "%d (%f)" % (self.payment.pay_id, self.id)


class Sale(models.Model):
    """
    Keep the sale details (either in case of payment or billing agreement)
    """

    sale_id = models.CharField(max_length=96, null=False, blank=False, unique=True, help_text="resource.id")
    amount_value = models.DecimalField(max_digits=12, decimal_places=4, help_text="resource.amount.total")
    amount_currency = models.CharField(max_length=8, null=False, blank=False, help_text="resource.amount.currency")
    state = models.CharField(max_length=32, null=False, blank=False)
    transaction_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, help_text="resource.transaction_fee.value")
    transaction_currency = models.CharField(max_length=8, null=True, blank=False, help_text="resource.transaction_fee.currency")
    billing_agreement_id = models.CharField(max_length=128, null=True, default=None)
    payment_mode = models.CharField(max_length=32, null=True, default=None)
    parent_payment = models.CharField(max_length=128, null=True, default=None)
    reason_code = models.CharField(max_length=128, null=True, default=None)
    protection_eligibility = models.CharField(max_length=32, null=True, default=None)
    protection_eligibility_type = models.CharField(max_length=128, null=True, default=None)
    json = models.TextField()
    create_time = models.DateTimeField()
    update_time = models.DateTimeField()

    class Meta :
        db_table = "sale"
        verbose_name = _("Sale")
        verbose_name_plural = _("Sales")

    def __unicode__(self):
        """ Get the sale descriptor """
        if self.billing_agreement_id != None:
            return "%d -%d (%d)" % (self.sale_id, self.state, self.billing_agreement_id)
        return "%d -%d (%d)" % (self.sale_id, self.state, self.parent_payment)


class Authorization(models.Model):
    """
    Keep the sale details (either in case of payment or billing agreement)
    """

    authorization_id = models.CharField(max_length=96, null=False, blank=False, unique=True, help_text="resource.id")
    amount_value = models.DecimalField(max_digits=12, decimal_places=4, help_text="resource.amount.total")
    amount_currency = models.CharField(max_length=8, null=False, blank=False, help_text="resource.amount.currency")
    state = models.CharField(max_length=32, null=False, blank=False)
    transaction_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="resource.transaction_fee.value")
    transaction_currency = models.CharField(max_length=8, null=True, blank=True, help_text="resource.transaction_fee.currency")
    payment_mode = models.CharField(max_length=32, null=True, blank=True, default=None)
    parent_payment = models.CharField(max_length=128, null=True, blank=True, default=None)
    reason_code = models.CharField(max_length=128, null=True, default=None)
    protection_eligibility = models.CharField(max_length=32, null=True, default=None)
    protection_eligibility_type = models.CharField(max_length=128, null=True, default=None)
    json = models.TextField()
    valid_until = models.DateTimeField()
    create_time = models.DateTimeField()
    update_time = models.DateTimeField()

    class Meta :
        db_table = "authorization"
        verbose_name = _("Authorization")
        verbose_name_plural = _("Authorization")

    def __unicode__(self):
        """ Get the authorization descriptor """
        return "%s -%s (%s)" % (self.sale_id, self.state, self.parent_payment)


class Capture(models.Model):
    """Keep a capture 
    """
    capture_id = models.CharField(max_length=96, null=False, blank=False, unique=True)
    amount_value = models.DecimalField(max_digits=12, decimal_places=4)
    amount_currency = models.CharField(max_length=8, null=False, blank=False)
    is_final_capture = models.BooleanField(blank=False, null=False)
    state = models.CharField(max_length=32, null=False, blank=False)
    reason_code = models.CharField(max_length=128, blank=True, null=True)
    parent_payment = models.CharField(max_length=128, null=False, blank=False)
    transaction_fee_value = models.DecimalField(max_digits=12, decimal_places=4)
    transaction_fee_currency =  models.CharField(max_length=8, null=False, blank=False)
    json = models.TextField()
    create_time = models.DateTimeField()
    update_time = models.DateTimeField()

    class Meta :
        db_table = "capture"
        verbose_name = _("Capture")
        verbose_name_plural = _("Captures")

    def __unicode__(self):
        return "%s - %s" % (self.authorization_id, self.parent_payment)


class Refund(models.Model):
    """
    Keep the refunded sales, billing agreement transactions or captures
    """

    refund_id = models.CharField(max_length=32, null=False, blank=False, unique=True, help_text="resource.id")
    sale_id = models.CharField(max_length=96, null=True, blank=False, help_text="resource<sale>.id")
    capture_id = models.CharField(max_length=96, null=True, blank=False, help_text="resource<capture>.id")
    description = models.TextField(max_length=1000, null=True)
    amount_value = models.DecimalField(max_digits=12, decimal_places=4, help_text="resource.amount.total")
    amount_currency = models.CharField(max_length=8, null=False, blank=False, help_text="resource.amount.currency")
    state = models.CharField(max_length=32, null=False, blank=False)
    reason = models.CharField(max_length=255, null=True)
    parent_payment = models.CharField(max_length=128, null=True)
    invoice_number = models.CharField(max_length=128, null=True, blank=False, help_text="resource.invoice_number")
    custom = models.CharField(max_length=255, null=True)
    json = models.TextField()
    create_time = models.DateTimeField()
    update_time = models.DateTimeField()


    class Meta :
        db_table = "refund"
        verbose_name = _("Refund")
        verbose_name_plural = _("Refunds")


    def __unicode__(self):
        """ Get the refund descriptor """
        if self.sale_id != None:
            return "%d -%d (%d)" % (self.refund_id, self.state, self.sale_id)
        return "%d -%d (%d)" % (self.refund_id, self.state, self.capture_id)


class PaymentTransactionLog(models.Model):

    payment_id = models.CharField(max_length=96, null=False, blank=False, help_text="payment id")
    transaction_type = models.CharField(max_length=45, null=False, blank=False, help_text="transaction type")
    request_json = models.TextField(null=True)
    response_json = models.TextField(null=True)
    create_time = models.DateTimeField()
    update_time = models.DateTimeField()

    class Meta :
        db_table = "payment_transaction_log"
        verbose_name = _("PaymentTransactionLog")
        verbose_name_plural = _("PaymentTransactionLog")

    def __unicode__(self):
        return "%s - %s" % (self.payment_id, transaction.type)

