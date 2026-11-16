from datetime import date

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models


class District(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Circuit(models.Model):
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="circuits")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["district__name", "name"]
        constraints = [models.UniqueConstraint(fields=["district", "name"], name="uniq_circuit_per_district")]

    def __str__(self):
        return f"{self.name} ({self.district})"


class Society(models.Model):
    """A local BCU branch (society) in a congregation."""
    circuit = models.ForeignKey(Circuit, on_delete=models.PROTECT, related_name="societies")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=200, blank=True)
    established = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Year founded")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["circuit__district__name", "circuit__name", "name"]
        verbose_name_plural = "societies"
        constraints = [models.UniqueConstraint(fields=["circuit", "name"], name="uniq_society_per_circuit")]

    @property
    def district(self):
        return self.circuit.district

    def __str__(self):
        return f"{self.name} ({self.circuit.name})"


class Member(models.Model):
    ACTIVE, INACTIVE, TRANSFERRED, GRADUATED = "active", "inactive", "transferred", "graduated"
    STATUSES = [(ACTIVE, "Active"), (INACTIVE, "Inactive"), (TRANSFERRED, "Transferred"), (GRADUATED, "Moved to Men's Christian Union")]

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    date_of_birth = models.DateField(null=True, blank=True)
    society = models.ForeignKey(Society, on_delete=models.PROTECT, related_name="members")
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = models.CharField(max_length=30, blank=True)
    joined = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default=ACTIVE)
    consent_recorded = models.BooleanField(default=False, help_text="Guardian consent to keep this record (required for under-18s)")
    consent_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["last_name", "first_name"])]

    @property
    def district(self):
        return self.society.circuit.district

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        t = date.today()
        return t.year - self.date_of_birth.year - ((t.month, t.day) < (self.date_of_birth.month, self.date_of_birth.day))

    @property
    def is_minor(self):
        return self.age is not None and self.age < 18

    def clean(self):
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValidationError({"date_of_birth": "Date of birth cannot be in the future."})
        if self.is_minor and not (self.guardian_name and self.guardian_phone):
            raise ValidationError("Members under 18 need a guardian name and phone number.")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name


class OfficeBearer(models.Model):
    NATIONAL, DISTRICT, CIRCUIT, SOCIETY = "national", "district", "circuit", "society"
    LEVELS = [(NATIONAL, "Connexional (national)"), (DISTRICT, "District"), (CIRCUIT, "Circuit"), (SOCIETY, "Society")]
    POSITIONS = [(p, p) for p in ["Chairperson", "Vice Chairperson", "Secretary", "Vice Secretary", "Treasurer", "Organiser",
                                  "Chaplain", "Patron", "Minister in Charge", "Committee member", "Other"]]

    level = models.CharField(max_length=10, choices=LEVELS)
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.PROTECT, related_name="officers")
    circuit = models.ForeignKey(Circuit, null=True, blank=True, on_delete=models.PROTECT, related_name="officers")
    society = models.ForeignKey(Society, null=True, blank=True, on_delete=models.PROTECT, related_name="officers")
    member = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="offices",
                               help_text="Link to the member record, if they are a BCU member")
    name = models.CharField(max_length=150)
    position = models.CharField(max_length=40, choices=POSITIONS)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    term_start = models.DateField(null=True, blank=True)
    term_end = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        ordering = ["level", "district__name", "position", "name"]
        verbose_name = "leader"
        verbose_name_plural = "leaders and executives"

    @property
    def unit(self):
        return {self.NATIONAL: None, self.DISTRICT: self.district, self.CIRCUIT: self.circuit, self.SOCIETY: self.society}[self.level]

    @property
    def scope_district(self):
        u = self.unit
        if self.level == self.NATIONAL or u is None:
            return None
        return u if self.level == self.DISTRICT else (u.district if self.level == self.CIRCUIT else u.circuit.district)

    def clean(self):
        want = {self.NATIONAL: None, self.DISTRICT: "district", self.CIRCUIT: "circuit", self.SOCIETY: "society"}.get(self.level)
        given = [f for f in ("district", "circuit", "society") if getattr(self, f + "_id")]
        if want is None and given:
            raise ValidationError("A national office bearer is not tied to a district, circuit or society.")
        if want and given != [want]:
            raise ValidationError(f"A {self.level}-level office bearer must be linked to a {want}, and only to a {want}.")
        if self.term_start and self.term_end and self.term_end < self.term_start:
            raise ValidationError({"term_end": "The term cannot end before it starts."})

    def __str__(self):
        return f"{self.name}, {self.position}"


class Profile(models.Model):
    """Decides what a login may see: national officers see everything, district officers only their own district."""
    NATIONAL, DISTRICT = "national", "district"
    ROLES = [(NATIONAL, "National officer (sees all districts)"), (DISTRICT, "District officer (own district only)")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=ROLES, default=DISTRICT)
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.PROTECT, related_name="officer_logins")
    must_change_password = models.BooleanField(default=True, help_text="The officer must choose their own password at first login")

    def clean(self):
        if self.role == self.DISTRICT and not self.district_id:
            raise ValidationError({"district": "Choose the district this officer works for."})
        if self.role == self.NATIONAL and self.district_id:
            raise ValidationError({"district": "National officers are not tied to a district."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # A profile makes the login a staff user with the right group of permissions.
        from .roles import GROUP_DISTRICT, GROUP_NATIONAL, ensure_groups
        ensure_groups()
        user = self.user
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        wanted = GROUP_NATIONAL if self.role == self.NATIONAL else GROUP_DISTRICT
        user.groups.remove(*Group.objects.filter(name__in=[GROUP_NATIONAL, GROUP_DISTRICT]).exclude(name=wanted))
        user.groups.add(Group.objects.get(name=wanted))

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"
