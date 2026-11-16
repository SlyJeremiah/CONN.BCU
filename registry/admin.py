from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Q

from .models import Circuit, District, Member, OfficeBearer, Profile, Society
from .roles import district_of
from .scoping import CsvExport, DistrictScoped


@admin.register(District)
class DistrictAdmin(DistrictScoped, admin.ModelAdmin):
    list_display = ("name", "circuits_count", "societies_count")
    search_fields = ("name",)
    district_lookup = "pk"

    @admin.display(description="Circuits")
    def circuits_count(self, obj):
        return obj.circuits.count()

    @admin.display(description="Societies")
    def societies_count(self, obj):
        return Society.objects.filter(circuit__district=obj).count()

    def obj_district(self, obj):
        return obj


@admin.register(Circuit)
class CircuitAdmin(DistrictScoped, admin.ModelAdmin):
    list_display = ("name", "district", "societies_count")
    list_filter = ("district",)
    search_fields = ("name",)
    district_lookup = "district"
    fk_limits = {"district": "pk"}

    @admin.display(description="Societies")
    def societies_count(self, obj):
        return obj.societies.count()

    def obj_district(self, obj):
        return obj.district


@admin.register(Society)
class SocietyAdmin(DistrictScoped, CsvExport, admin.ModelAdmin):
    list_display = ("name", "circuit", "district_name", "established", "is_active", "member_count")
    list_filter = ("is_active", "circuit__district", "circuit")
    search_fields = ("name", "circuit__name")
    district_lookup = "circuit__district"
    fk_limits = {"circuit": "district"}
    actions = ["export_csv"]
    csv_name = "societies"
    csv_fields = ("name", "circuit__name", "circuit__district__name", "address", "established", "is_active")

    @admin.display(description="District", ordering="circuit__district__name")
    def district_name(self, obj):
        return obj.circuit.district

    @admin.display(description="Active members")
    def member_count(self, obj):
        return obj.members.filter(status=Member.ACTIVE).count()

    def obj_district(self, obj):
        return obj.circuit.district


@admin.register(Member)
class MemberAdmin(DistrictScoped, CsvExport, admin.ModelAdmin):
    list_display = ("last_name", "first_name", "society", "district_name", "age", "status", "consent_recorded")
    list_filter = ("status", "consent_recorded", "society__circuit__district")
    search_fields = ("first_name", "last_name", "phone", "guardian_name")
    autocomplete_fields = ("society",)
    district_lookup = "society__circuit__district"
    fk_limits = {"society": "circuit__district"}
    actions = ["export_csv"]
    csv_name = "members"
    csv_fields = ("first_name", "last_name", "date_of_birth", "age", "society__name", "society__circuit__name",
                  "society__circuit__district__name", "phone", "guardian_name", "guardian_phone", "status", "consent_recorded")
    fieldsets = (
        ("Member", {"fields": ("first_name", "last_name", "date_of_birth", "society", "joined", "status")}),
        ("Contact", {"fields": ("phone", "email", "guardian_name", "guardian_phone")}),
        ("Consent and notes", {"fields": ("consent_recorded", "consent_date", "notes"),
                               "description": "Members under 18 need a guardian and recorded consent."}),
    )

    @admin.display(description="District", ordering="society__circuit__district__name")
    def district_name(self, obj):
        return obj.society.circuit.district

    def obj_district(self, obj):
        return obj.society.circuit.district

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(OfficeBearer)
class OfficeBearerAdmin(DistrictScoped, CsvExport, admin.ModelAdmin):
    list_display = ("name", "position", "level", "unit_name", "phone", "term_start", "term_end", "is_current")
    list_filter = ("level", "position", "is_current", "district")
    search_fields = ("name", "phone", "email")
    fk_limits = {"district": "pk", "circuit": "district", "society": "circuit__district", "member": "society__circuit__district"}
    actions = ["export_csv"]
    csv_name = "leaders"
    csv_fields = ("name", "position", "level", "unit_name", "phone", "email", "term_start", "term_end", "is_current")
    fieldsets = (
        ("Office", {"fields": ("level", "district", "circuit", "society", "position")}),
        ("Person", {"fields": ("name", "member", "phone", "email")}),
        ("Term", {"fields": ("term_start", "term_end", "is_current")}),
    )

    def scope(self, qs, d):
        return qs.filter(Q(district=d) | Q(circuit__district=d) | Q(society__circuit__district=d))

    @admin.display(description="Unit")
    def unit_name(self, obj):
        return obj.unit or "Connexional"

    def obj_district(self, obj):
        return obj.scope_district

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "level" and district_of(request.user) is not None:   # district officers cannot create national posts
            kwargs["choices"] = [c for c in OfficeBearer.LEVELS if c[0] != OfficeBearer.NATIONAL]
        return super().formfield_for_choice_field(db_field, request, **kwargs)


# ---- logins: attach a profile (role + district) to every user --------------------------------------
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 1
    max_num = 1
    verbose_name = "Access"
    verbose_name_plural = "Access (what this login can see)"


admin.site.unregister(User)


@admin.register(User)
class BCUUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "first_name", "last_name", "email", "role", "district", "is_active")

    @admin.display(description="Role")
    def role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, "profile") else "No access set"

    @admin.display(description="District")
    def district(self, obj):
        return obj.profile.district if hasattr(obj, "profile") else ""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(is_superuser=False)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:       # national officers manage logins, not superusers or raw permissions
            ro += ["is_superuser", "user_permissions", "groups", "is_staff"]
        return ro
