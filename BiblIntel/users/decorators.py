from django.shortcuts import redirect
from django.contrib import messages

def fonctionnaire_required(view_func):

    def wrapper(request, *args, **kwargs):

        if request.user.status != "fonctionnaire":
            messages.error(request, "Accès réservé.")
            return redirect("users:home")

        return view_func(request, *args, **kwargs)

    return wrapper