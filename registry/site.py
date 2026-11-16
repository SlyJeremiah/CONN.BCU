from django.conf import settings
from django.contrib import admin
from django.db.models import Count, Q

from .roles import NONE, district_of


class BCUAdminSite(admin.AdminSite):
    site_header = "BCU National Database"
    site_title = "BCU Database"
    index_title = "Dashboard"

    def password_change(self, request, extra_context=None):
        response = super().password_change(request, extra_context)
        if request.method == "POST" and response.status_code == 302:   # a successful change clears the first-login requirement
            from .models import Profile
            Profile.objects.filter(user=request.user).update(must_change_password=False)
        return response

    def index(self, request, extra_context=None):
        from finance.models import LevyAssessment
        from .models import District, Member, OfficeBearer

        d = district_of(request.user)
        year = settings.CURRENT_LEVY_YEAR
        districts = District.objects.all() if d is None else (District.objects.none() if d is NONE else District.objects.filter(pk=d.pk))
        rows, tot = [], dict(circuits=0, societies=0, members=0, leaders=0, assessed=0, paid=0)
        for dist in districts.annotate(
                n_circuits=Count("circuits", distinct=True),
                n_societies=Count("circuits__societies", distinct=True),
                n_members=Count("circuits__societies__members", filter=Q(circuits__societies__members__status="active"), distinct=True)):
            leaders = OfficeBearer.objects.filter(is_current=True).filter(
                Q(district=dist) | Q(circuit__district=dist) | Q(society__circuit__district=dist)).count()
            a = LevyAssessment.objects.filter(district=dist, year=year).first()
            assessed, paid = (a.amount, a.paid) if a else (0, 0)
            rows.append(dict(name=dist.name, circuits=dist.n_circuits, societies=dist.n_societies, members=dist.n_members,
                             leaders=leaders, assessed=assessed, paid=paid, balance=assessed - paid))
            for k, v in (("circuits", dist.n_circuits), ("societies", dist.n_societies), ("members", dist.n_members),
                         ("leaders", leaders), ("assessed", assessed), ("paid", paid)):
                tot[k] += v
        tot["balance"] = tot["assessed"] - tot["paid"]
        no_consent = Member.objects.filter(status="active", consent_recorded=False)
        if d is not None:
            no_consent = no_consent.none() if d is NONE else no_consent.filter(society__circuit__district=d)
        ctx = {"rows": rows, "totals": tot, "levy_year": year, "scoped": d is not None,
               "no_consent": no_consent.count(), "district_name": getattr(d, "name", "")}
        return super().index(request, {**ctx, **(extra_context or {})})
