from django.contrib import admin

from registry.scoping import CsvExport, DistrictScoped

from .models import LevyAssessment, LevyPayment


class PaymentInline(admin.TabularInline):
    model = LevyPayment
    extra = 0
    fields = ("date", "amount", "method", "reference", "notes")


@admin.register(LevyAssessment)
class LevyAssessmentAdmin(DistrictScoped, admin.ModelAdmin):
    list_display = ("district", "year", "amount", "paid_display", "balance_display", "status", "due_date")
    list_filter = ("year", "district")
    inlines = [PaymentInline]
    district_lookup = "district"

    @admin.display(description="Paid")
    def paid_display(self, obj):
        return f"{obj.paid:.2f}"

    @admin.display(description="Balance")
    def balance_display(self, obj):
        return f"{obj.balance:.2f}"

    def obj_district(self, obj):
        return obj.district

    def save_formset(self, request, form, formset, change):
        for inst in formset.save(commit=False):
            if isinstance(inst, LevyPayment) and not inst.pk:
                inst.received_by = request.user
            inst.save()
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()


@admin.register(LevyPayment)
class LevyPaymentAdmin(DistrictScoped, CsvExport, admin.ModelAdmin):
    list_display = ("date", "assessment", "amount", "method", "reference")
    list_filter = ("method", "assessment__year", "assessment__district")
    date_hierarchy = "date"
    district_lookup = "assessment__district"
    actions = ["export_csv"]
    csv_name = "levy-payments"
    csv_fields = ("date", "assessment__district__name", "assessment__year", "amount", "method", "reference")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)

    def obj_district(self, obj):
        return obj.assessment.district
