from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChange:
    """An officer given a starting password must choose their own before doing anything else."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = request.user
        if u.is_authenticated and not u.is_superuser:
            profile = getattr(u, "profile", None)
            if profile is not None and profile.must_change_password:
                allowed = {reverse("admin:password_change"), reverse("admin:password_change_done"), reverse("admin:logout")}
                if request.path not in allowed and not request.path.startswith("/static/"):
                    messages.info(request, "Please choose your own password to continue.")
                    return redirect("admin:password_change")
        return self.get_response(request)
