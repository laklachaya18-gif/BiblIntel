from django.contrib import admin
from .models import Emprunt, Reservation


@admin.register(Emprunt)
class EmpruntAdmin(admin.ModelAdmin):
    list_display = [
        "utilisateur",
        "livre",
        "statut",
        "date_demande",
        "date_retour_prevue",
    ]
    list_filter = ["statut", "date_demande"]
    search_fields = ["utilisateur__username", "livre__titre"]


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = [
        "utilisateur",
        "livre",
        "date_reservation",
        "position_file",
        "est_active",
    ]
    list_filter = ["est_active", "date_reservation"]
    search_fields = ["utilisateur__username", "livre__titre"]
