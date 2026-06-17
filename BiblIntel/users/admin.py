from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        "username",
        "first_name",
        "last_name",
        "email",
        "status",
        "est_blackliste",
        "points_fidelite",
    ]
    list_filter = ["status", "est_blackliste", "is_staff", "is_active"]
    fieldsets = UserAdmin.fieldsets + (
        (
            "Informations supplémentaires",
            {
                "fields": (
                    "status",
                    "filiere",
                    "telephone",
                    "date_naissance",
                    "photo_profil",
                    "points_fidelite",
                    "est_blackliste",
                    "date_blacklist",
                    "raison_blacklist",
                )
            },
        ),
    )
