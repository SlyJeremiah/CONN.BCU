from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from registry.models import District


class LevyAssessment(models.Model):
    """The levy a district owes for a year."""
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="levies")
    year = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-year", "district__name"]
        constraints = [models.UniqueConstraint(fields=["district", "year"], name="uniq_levy_per_district_year")]

    @property
    def paid(self):
        return self.payments.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    @property
    def balance(self):
        return self.amount - self.paid

    @property
    def status(self):
        if self.paid <= 0:
            return "Not paid"
        return "Paid in full" if self.balance <= 0 else "Part paid"

    def __str__(self):
        return f"{self.district} {self.year}"


class LevyPayment(models.Model):
    CASH, ECOCASH, BANK, OTHER = "cash", "ecocash", "bank", "other"
    METHODS = [(CASH, "Cash"), (ECOCASH, "EcoCash"), (BANK, "Bank transfer"), (OTHER, "Other")]

    assessment = models.ForeignKey(LevyAssessment, on_delete=models.PROTECT, related_name="payments")
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHODS, default=ECOCASH)
    reference = models.CharField(max_length=100, blank=True, help_text="Receipt number or transaction reference")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False)
    notes = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.assessment.district} {self.amount} on {self.date}"
