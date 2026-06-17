from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("admin/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/blacklist/", views.blacklist_admin, name="blacklist_admin"),
    path("admin/user/<int:pk>/", views.admin_user_detail, name="admin_user_detail"),
    path("admin/user/<int:pk>/toggle-blacklist/", views.admin_toggle_blacklist, name="admin_toggle_blacklist"),
    path("bibliothecaire/", views.bibliothecaire_dashboard, name="bibliothecaire_dashboard"),
    path("paiements-attente/", views.paiements_manuels_attente, name="paiements_manuels_attente"),
    path("valider-paiement/<int:pk>/", views.valider_paiement_manuel, name="valider_paiement_manuel"),
    path("paiements-attente/", views.paiements_manuels_attente, name="paiements_manuels_attente"),
    path("valider-paiement/<int:pk>/", views.valider_paiement_manuel, name="valider_paiement_manuel"),
    path("admin/bibliothecaire/<int:pk>/", views.admin_bibliothecaire_detail, name="admin_bibliothecaire_detail"),



    path("bibliothecaire/notifications/", views.bibliothecaire_notifications, name="bibliothecaire_notifications"),

    path("api/rechercher-utilisateurs/", views.api_rechercher_utilisateurs, name="api_rechercher_utilisateurs"),
]