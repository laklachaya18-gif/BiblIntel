from django.db import models
from django.utils import timezone
from users.models import User
from books.models import Livre


class Emprunt(models.Model):

    STATUT_CHOICES = [
        ("en_attente", "En attente"),
        ("approuve", "Approuvé"),
        ("en_cours", "En cours"),
        ("retourne", "Retourné"),
        ("retard", "En retard"),
        ("refuse", "Refusé"),
    ]

    utilisateur = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="emprunts"
    )
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name="emprunts")

    date_demande = models.DateTimeField(auto_now_add=True)
    date_approbation = models.DateTimeField(null=True, blank=True)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_retour_prevue = models.DateField(null=True, blank=True)
    date_retour_effective = models.DateTimeField(null=True, blank=True)

    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default="en_attente"
    )
    position_file = models.PositiveIntegerField(default=0)
    a_prolonge = models.BooleanField(default=False)
    nombre_prolongations = models.PositiveSmallIntegerField(default=0)

    amende_totale = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    est_payee = models.BooleanField(default=False)

    derniere_page_lue = models.IntegerField(null=True, blank=True)
    demande_paiement_manuel = models.BooleanField(default=False)
    paiement_valide_par = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paiements_valides'
    )
    paiement_valide_le = models.DateTimeField(null=True, blank=True)

    def approuver(self):
        self.statut = "en_cours"
        self.date_approbation = timezone.now()
        self.date_debut = timezone.now()
        self.save()

    def calculer_retard(self):
        if self.date_retour_prevue:
        # Si le livre est retourné, on utilise la date de retour effective
            if self.date_retour_effective:
                date_a_comparer = self.date_retour_effective.date()
            else:
                date_a_comparer = timezone.now().date()
        
            if date_a_comparer > self.date_retour_prevue:
                return (date_a_comparer - self.date_retour_prevue).days
        return 0

    def calculer_amende(self):
        return self.calculer_retard() * 10
    def save(self, *args, **kwargs):
        if self.statut in ("en_cours", "retard"):
            if self.calculer_retard() > 0:
                self.statut = "retard"
            elif self.statut == "retard":
                self.statut = "en_cours"  # remet à jour si retard levé
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.utilisateur} - {self.livre} ({self.statut})"


class Reservation(models.Model):
    utilisateur = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reservations"
    )
    livre = models.ForeignKey(
        Livre, on_delete=models.CASCADE, related_name="reservations"
    )

    date_reservation = models.DateTimeField(auto_now_add=True)
    position_file = models.PositiveIntegerField(default=1)
    est_active = models.BooleanField(default=True)
    notification_envoyee = models.BooleanField(default=False)

    class Meta:
        ordering = ["date_reservation"]

    def __str__(self):
        return f"{self.utilisateur} - {self.livre}"
