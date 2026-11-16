"""Roles: two permission groups, plus the helper every admin uses to decide what a login may see."""
from django.contrib.auth.models import Group, Permission

GROUP_NATIONAL = "National officers"
GROUP_DISTRICT = "District officers"

NATIONAL_APPS = {"registry", "finance"}
# District officers can capture structure, members and leaders for their own district.
DISTRICT_EDIT = {("registry", m) for m in ("circuit", "society", "member", "officebearer")}
DISTRICT_VIEW = {("registry", "district"), ("finance", "levyassessment"), ("finance", "levypayment")}


def ensure_groups():
    nat, _ = Group.objects.get_or_create(name=GROUP_NATIONAL)
    dis, _ = Group.objects.get_or_create(name=GROUP_DISTRICT)
    perms = Permission.objects.select_related("content_type")
    nat_p = [p for p in perms if p.content_type.app_label in NATIONAL_APPS or (p.content_type.app_label == "auth" and p.content_type.model in ("user", "group"))]
    dis_p = []
    for p in perms:
        key = (p.content_type.app_label, p.content_type.model)
        verb = p.codename.split("_")[0]
        if key in DISTRICT_EDIT and verb in ("add", "change", "view"):   # no delete: records are retired, not erased
            dis_p.append(p)
        elif key in DISTRICT_VIEW and verb == "view":
            dis_p.append(p)
    nat.permissions.set(nat_p)
    dis.permissions.set(dis_p)


NONE = object()   # a login with no profile sees nothing


def district_of(user):
    """None -> sees everything (superuser / national). District instance -> that district only. NONE -> nothing."""
    if not user.is_authenticated:
        return NONE
    if user.is_superuser:
        return None
    profile = getattr(user, "profile", None)
    if profile is None:
        return NONE
    if profile.role == "national":
        return None
    return profile.district or NONE
