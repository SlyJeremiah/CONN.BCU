"""Row-level scoping: a district officer only ever sees, opens or edits records in their own district."""
import csv

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

from .roles import NONE, district_of


class DistrictScoped:
    district_lookup = None      # ORM path from this model to its District
    fk_limits = {}              # {field name: ORM filter path to the district} for dropdown choices

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        d = district_of(request.user)
        if d is None:
            return qs
        if d is NONE:
            return qs.none()
        return self.scope(qs, d)

    @staticmethod
    def _match(path, d):
        """A lookup ending in 'pk' compares ids, so it needs the district's id; other paths take the District itself."""
        return d.pk if path == "pk" else d

    def scope(self, qs, d):
        return qs.filter(**{self.district_lookup: self._match(self.district_lookup, d)})

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        d = district_of(request.user)
        path = self.fk_limits.get(db_field.name)
        if d is not None and path:
            model = db_field.remote_field.model
            kwargs["queryset"] = model._default_manager.none() if d is NONE else model._default_manager.filter(**{path: self._match(path, d)})
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def obj_district(self, obj):
        raise NotImplementedError

    def save_model(self, request, obj, form, change):
        d = district_of(request.user)
        if d is not None:                       # never trust the form: re-check the record's district on save
            if d is NONE or self.obj_district(obj) != d:
                raise PermissionDenied("You can only record data for your own district.")
        super().save_model(request, obj, form, change)


class CsvExport:
    csv_fields = ()
    csv_name = "export"

    def export_csv(self, request, queryset):
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{self.csv_name}.csv"'
        w = csv.writer(resp)
        w.writerow([f.replace("__", " ").replace("_", " ").title() for f in self.csv_fields])
        for obj in queryset:
            row = []
            for f in self.csv_fields:
                v = obj
                for part in f.split("__"):
                    v = getattr(v, part, "") if v is not None else ""
                    if callable(v):
                        v = v()
                row.append("" if v is None else v)
            w.writerow(row)
        return resp

    export_csv.short_description = "Export selected to CSV"
