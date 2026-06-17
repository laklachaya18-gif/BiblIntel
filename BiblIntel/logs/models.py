from django.db import models
from users.models import User


class LogAction(models.Model):
    TYPE_CHOICES = [
        ("connexion", "Connexion"),
        ("deconnexion", "Déconnexion"),
        ("crud_livre", "CRUD Livre"),
        ("crud_user", "CRUD Utilisateur"),
        ("emprunt", "Emprunt"),
        ("retour", "Retour"),
        ("blacklist", "Blacklist"),
        ("reservation", "Réservation"),
        ("paiement", "Paiement"),
    ]

    utilisateur = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    type_action = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField()
    date_action = models.DateTimeField(auto_now_add=True)
    temps_utilisation = models.IntegerField(default=0)
    ip_adresse = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ["-date_action"]
