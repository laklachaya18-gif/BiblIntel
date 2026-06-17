from django.db import models
from users.models import User


class Notification(models.Model):
    TYPE_CHOICES = [
        ("retour_proche", "Retour proche"),
        ("retard", "Retard"),
        ("validation", "Validation emprunt"),
        ("refus", "Refus emprunt"),
        ("disponible", "Livre disponible"),
        ("blacklist", "Blacklist"),
        ("paiement_manuel", "Paiement manuel"),
    ]

    utilisateur = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    type_notification = models.CharField(max_length=20, choices=TYPE_CHOICES)
    titre = models.CharField(max_length=255)
    message = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date_creation"]
