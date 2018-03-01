
from rest_framework import serializers
from api import models
import json


class BillingAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BillingAgreement
        fields = ('id', 'json' )


class PaymentSerializer(serializers.ModelSerializer):

    payment = serializers.SerializerMethodField()

    def get_payment(self, object):
        print type(object.json)
        return json.loads(object.json)

    class Meta:
        model = models.Payment
        fields = ('id', 'payment', )


