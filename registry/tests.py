from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from finance.models import LevyAssessment, LevyPayment
from .models import Circuit, District, Member, OfficeBearer, Profile, Society


def make_user(name, role, district=None):
    u = User.objects.create_user(name, f"{name}@example.org", "pw-long-enough-12")
    Profile.objects.create(user=u, role=role, district=district, must_change_password=False)
    return u


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.east = District.objects.get(name="Harare East")
        cls.kadoma = District.objects.get(name="Kadoma")
        cls.c_east = Circuit.objects.create(district=cls.east, name="Avondale")
        cls.c_kad = Circuit.objects.create(district=cls.kadoma, name="Kadoma Central")
        cls.s_east = Society.objects.create(circuit=cls.c_east, name="Avondale Society")
        cls.s_kad = Society.objects.create(circuit=cls.c_kad, name="Kadoma Society")
        cls.m_east = Member.objects.create(first_name="Tendai", last_name="Moyo", society=cls.s_east, date_of_birth=date(2000, 1, 1))
        cls.m_kad = Member.objects.create(first_name="Blessing", last_name="Ncube", society=cls.s_kad, date_of_birth=date(2000, 1, 1))
        cls.national = make_user("national", Profile.NATIONAL)
        cls.east_officer = make_user("east", Profile.DISTRICT, cls.east)


class SeedTests(TestCase):
    def test_eight_districts_and_2027_levies(self):
        self.assertEqual(District.objects.count(), 8)
        levies = LevyAssessment.objects.filter(year=2027)
        self.assertEqual(levies.count(), 8)
        self.assertEqual(sum(l.amount for l in levies), Decimal("840"))
        self.assertEqual(levies.get(district__name="Harare East").amount, Decimal("150"))


class ScopingTests(Base):
    def test_district_officer_sees_only_own_district(self):
        self.client.force_login(self.east_officer)
        r = self.client.get(reverse("admin:registry_member_changelist"))
        self.assertContains(r, "Moyo")
        self.assertNotContains(r, "Ncube")

    def test_district_officer_cannot_open_other_districts_record(self):
        self.client.force_login(self.east_officer)
        # Admin treats an out-of-scope id as "does not exist" and redirects; own records open normally.
        self.assertEqual(self.client.get(reverse("admin:registry_member_change", args=[self.m_kad.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("admin:registry_member_change", args=[self.m_east.pk])).status_code, 200)

    def test_national_sees_everything(self):
        self.client.force_login(self.national)
        r = self.client.get(reverse("admin:registry_member_changelist"))
        self.assertContains(r, "Moyo")
        self.assertContains(r, "Ncube")

    def test_district_officer_cannot_post_into_other_district(self):
        self.client.force_login(self.east_officer)
        data = {"first_name": "Sneaky", "last_name": "Entry", "society": self.s_kad.pk, "status": "active",
                "date_of_birth": "2000-01-01", "consent_recorded": "on"}
        r = self.client.post(reverse("admin:registry_member_add"), data)
        self.assertEqual(r.status_code, 200)                       # form shown again with an error: that society is not offered
        self.assertFalse(Member.objects.filter(last_name="Entry").exists())

    def test_district_officer_can_add_in_own_district(self):
        self.client.force_login(self.east_officer)
        data = {"first_name": "Farai", "last_name": "Dube", "society": self.s_east.pk, "status": "active",
                "date_of_birth": "2000-01-01", "consent_recorded": "on"}
        r = self.client.post(reverse("admin:registry_member_add"), data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Member.objects.get(last_name="Dube").created_by, self.east_officer)

    def test_district_officer_cannot_see_other_district_on_dashboard(self):
        self.client.force_login(self.east_officer)
        r = self.client.get(reverse("admin:index"))
        self.assertContains(r, "Harare East")
        self.assertNotContains(r, "Kadoma")

    def test_district_officer_pages_all_open(self):
        """Regression: the Districts list and every add form must open for a district officer (this crashed on Postgres)."""
        self.client.force_login(self.east_officer)
        r = self.client.get(reverse("admin:registry_district_changelist"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Harare East")
        self.assertNotContains(r, "Kadoma")
        for name in ["admin:registry_circuit_add", "admin:registry_society_add", "admin:registry_member_add", "admin:registry_officebearer_add"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_district_officer_forms_only_offer_own_district(self):
        self.client.force_login(self.east_officer)
        r = self.client.get(reverse("admin:registry_circuit_add"))
        districts = [str(d) for d in r.context["adminform"].form.fields["district"].queryset]
        self.assertEqual(districts, ["Harare East"])
        r = self.client.get(reverse("admin:registry_officebearer_add"))
        self.assertEqual([str(d) for d in r.context["adminform"].form.fields["district"].queryset], ["Harare East"])
        levels = [v for v, _ in r.context["adminform"].form.fields["level"].choices]
        self.assertNotIn("national", levels)

    def test_district_officer_cannot_add_districts_or_delete_members(self):
        self.client.force_login(self.east_officer)
        self.assertEqual(self.client.get(reverse("admin:registry_district_add")).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:registry_member_delete", args=[self.m_east.pk]), {"post": "yes"}).status_code, 403)

    def test_login_without_profile_sees_nothing(self):
        u = User.objects.create_user("plain", password="pw-long-enough-12", is_staff=True)
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("admin:registry_member_changelist")).status_code, 403)

    def test_anonymous_is_sent_to_login(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        r = self.client.get(reverse("admin:registry_member_changelist"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("login", r["Location"])

    def test_profile_makes_user_staff_with_group(self):
        self.assertTrue(self.east_officer.is_staff)
        self.assertEqual(list(self.east_officer.groups.values_list("name", flat=True)), ["District officers"])
        self.assertEqual(list(self.national.groups.values_list("name", flat=True)), ["National officers"])

    def test_csv_export_is_scoped(self):
        self.client.force_login(self.east_officer)
        r = self.client.post(reverse("admin:registry_member_changelist"),
                             {"action": "export_csv", "_selected_action": [self.m_east.pk, self.m_kad.pk]})
        body = r.content.decode()
        self.assertIn("Moyo", body)
        self.assertNotIn("Ncube", body)          # the Kadoma id is outside the officer's queryset, so it is ignored


class ModelRuleTests(Base):
    def test_minor_needs_guardian(self):
        kid = date.today() - timedelta(days=365 * 12)
        m = Member(first_name="Young", last_name="Boy", society=self.s_east, date_of_birth=kid)
        self.assertTrue(m.is_minor)
        with self.assertRaises(ValidationError):
            m.full_clean()
        m.guardian_name, m.guardian_phone = "Mrs Boy", "0770000000"
        m.full_clean()

    def test_age(self):
        today = date.today()
        m = Member(date_of_birth=date(today.year - 20, today.month, today.day))
        self.assertEqual(m.age, 20)

    def test_office_bearer_level_must_match_link(self):
        OfficeBearer(level="district", district=self.east, name="A", position="Chairperson").full_clean()
        with self.assertRaises(ValidationError):
            OfficeBearer(level="district", circuit=self.c_east, name="A", position="Chairperson").full_clean()
        with self.assertRaises(ValidationError):
            OfficeBearer(level="national", district=self.east, name="A", position="Chairperson").full_clean()
        OfficeBearer(level="national", name="National chair", position="Chairperson").full_clean()

    def test_leader_scoping(self):
        OfficeBearer.objects.create(level="district", district=self.east, name="East Chair", position="Chairperson")
        OfficeBearer.objects.create(level="society", society=self.s_kad, name="Kadoma Sec", position="Secretary")
        OfficeBearer.objects.create(level="national", name="National Chair", position="Chairperson")
        self.client.force_login(self.east_officer)
        r = self.client.get(reverse("admin:registry_officebearer_changelist"))
        self.assertContains(r, "East Chair")
        self.assertNotContains(r, "Kadoma Sec")
        self.assertNotContains(r, "National Chair")

    def test_levy_balance_and_status(self):
        a = LevyAssessment.objects.get(district=self.east, year=2027)
        self.assertEqual(a.status, "Not paid")
        LevyPayment.objects.create(assessment=a, date=date.today(), amount=Decimal("50"))
        self.assertEqual((a.paid, a.balance, a.status), (Decimal("50"), Decimal("100"), "Part paid"))
        LevyPayment.objects.create(assessment=a, date=date.today(), amount=Decimal("100"))
        self.assertEqual((a.balance, a.status), (Decimal("0"), "Paid in full"))

    def test_district_officer_cannot_record_levy_payment(self):
        a = LevyAssessment.objects.get(district=self.east, year=2027)
        self.client.force_login(self.east_officer)
        self.assertEqual(self.client.get(reverse("admin:finance_levypayment_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:finance_levyassessment_change", args=[a.pk])).status_code, 200)   # can view own levy
        other = LevyAssessment.objects.get(district=self.kadoma, year=2027)
        self.assertEqual(self.client.get(reverse("admin:finance_levyassessment_change", args=[other.pk])).status_code, 302)

    def test_national_records_payment_and_dashboard_balance(self):
        self.client.force_login(self.national)
        a = LevyAssessment.objects.get(district=self.east, year=2027)
        r = self.client.post(reverse("admin:finance_levypayment_add"),
                             {"assessment": a.pk, "date": date.today().isoformat(), "amount": "150", "method": "ecocash", "reference": "EC1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(LevyPayment.objects.get().received_by, self.national)
        self.assertContains(self.client.get(reverse("admin:index")), "690.00")      # 840 total minus 150 paid


class LoginsTests(Base):
    def test_command_creates_three_connexional_officers_once(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("create_national_officers", stdout=out)
        users = User.objects.filter(username__startswith="conn.")
        self.assertEqual(sorted(users.values_list("username", flat=True)), ["conn.minister", "conn.secretary", "conn.treasurer"])
        for u in users:
            self.assertEqual(u.profile.role, Profile.NATIONAL)
            self.assertTrue(u.profile.must_change_password)
            self.assertTrue(u.has_usable_password())
        self.assertIn("starting password", out.getvalue())
        out2 = StringIO()
        call_command("create_national_officers", stdout=out2)
        self.assertIn("already exists", out2.getvalue())
        self.assertNotIn("starting password", out2.getvalue())

    def test_first_login_forces_password_change_then_releases(self):
        u = User.objects.create_user("newbie", password="starting-pass-123")
        Profile.objects.create(user=u, role=Profile.DISTRICT, district=self.east)      # must_change_password defaults to True
        self.client.force_login(u)
        r = self.client.get(reverse("admin:registry_member_changelist"))
        self.assertRedirects(r, reverse("admin:password_change"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("admin:password_change")).status_code, 200)
        r = self.client.post(reverse("admin:password_change"),
                             {"old_password": "starting-pass-123", "new_password1": "My-own-password-77", "new_password2": "My-own-password-77"})
        self.assertEqual(r.status_code, 302)
        u.profile.refresh_from_db()
        self.assertFalse(u.profile.must_change_password)
        self.assertEqual(self.client.get(reverse("admin:registry_member_changelist")).status_code, 200)

    def test_national_officer_can_add_a_district_admin(self):
        self.client.force_login(self.national)
        west = District.objects.get(name="Harare West")
        data = {"username": "west.admin", "password1": "Starter-pass-8899", "password2": "Starter-pass-8899",
                "profile-TOTAL_FORMS": "1", "profile-INITIAL_FORMS": "0", "profile-MIN_NUM_FORMS": "0", "profile-MAX_NUM_FORMS": "1",
                "profile-0-role": "district", "profile-0-district": west.pk, "profile-0-must_change_password": "on"}
        r = self.client.post(reverse("admin:auth_user_add"), data)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context.get("adminform") and r.context["adminform"].form.errors)
        u = User.objects.get(username="west.admin")
        self.assertTrue(u.is_staff)
        self.assertEqual(u.profile.district, west)
        self.assertEqual(list(u.groups.values_list("name", flat=True)), ["District officers"])
        self.assertFalse(u.is_superuser)

    def test_national_officer_cannot_make_superusers_or_see_them(self):
        root = User.objects.create_superuser("root", "r@example.org", "x-long-root-pass-1")
        self.client.force_login(self.national)
        r = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertNotContains(r, "root")
        self.assertEqual(self.client.get(reverse("admin:auth_user_change", args=[root.pk])).status_code, 302)
