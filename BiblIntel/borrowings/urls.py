from django.urls import path
from . import views

app_name = "borrowings"

urlpatterns = [
    # Emprunts
    path("", views.emprunt_list, name="emprunt_list"),
    path("create/<int:livre_id>/", views.emprunt_create, name="emprunt_create"),
    path("<int:pk>/return/", views.emprunt_retour, name="emprunt_retour"),
    path("<int:pk>/prolonger/", views.emprunt_prolonger, name="emprunt_prolonger"),
    path("<int:pk>/payer/", views.payer_amende, name="payer_amende"),
    # Réservations
    
    # ... autres URLs ...
    path("payer-toutes-amendes-manuel/", views.payer_toutes_amendes_manuel, name="payer_toutes_amendes_manuel"),
    path("payer-toutes-amendes-en-ligne/", views.payer_toutes_amendes_en_ligne, name="payer_toutes_amendes_en_ligne"),

    path(
        "reserver/<int:livre_id>/", views.reservation_create, name="reservation_create"
    ),
    path(
        "reservation/<int:pk>/cancel/",
        views.reservation_cancel,
        name="reservation_cancel",
    ),
    path("mes-reservations/", views.mes_reservations, name="mes_reservations"),
    # Points fidélité : emprunt avec date choisie (récompense 50 pts)
    path(
        "emprunt-prioritaire/<int:livre_id>/",
        views.emprunt_prioritaire,
        name="emprunt_prioritaire",
    ),
    path('amendes/', views.amende_list, name='amende_list'),
    path("payer-toutes-amendes/", views.payer_toutes_amendes, name="payer_toutes_amendes"),
    path("payer-groupes-amendes/", views.payer_groupes_amendes, name="payer_groupes_amendes"),
    path("mes-amendes/", views.mes_amendes, name="mes_amendes"),
    path("valider-paiement/<int:pk>/", views.bibliothecaire_valider_paiement, name="bibliothecaire_valider_paiement"),
    path("<int:pk>/payer-en-ligne/", views.payer_amende_en_ligne, name="payer_amende_en_ligne"),
    path("export-amendes-pdf/", views.export_amendes_pdf, name="export_amendes_pdf"),
    path("<int:pk>/payer-manuel/", views.payer_amende_manuel, name="payer_amende_manuel"),
]
