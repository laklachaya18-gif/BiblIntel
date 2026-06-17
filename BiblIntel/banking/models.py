from django.db import models
from users.models import User

class CompteBancaire(models.Model):
    """
    Compte bancaire fictif pour tester le paiement en ligne des amendes.
    Dans un vrai projet, on utiliserait une API de paiement (Stripe, PayTech, etc.)
    """
    utilisateur = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name="compte_bancaire"
    )
    solde = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=500.00,  # Solde fictif de départ pour les tests
        help_text="Solde disponible en dirhams (DH)"
    )
    numero_carte = models.CharField(
        max_length=16, 
        blank=True, 
        null=True,
        help_text="Numéro de carte bancaire (16 chiffres)"
    )
    date_expiration = models.CharField(
        max_length=5, 
        blank=True, 
        null=True,
        help_text="Format MM/YY"
    )
    cryptogramme = models.CharField(
        max_length=3, 
        blank=True, 
        null=True,
        help_text="CVV/CVC (3 chiffres)"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Compte bancaire"
        verbose_name_plural = "Comptes bancaires"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"Compte de {self.utilisateur.username} - {self.solde} DH"

    def debiter(self, montant):
        from decimal import Decimal
        montant_decimal = Decimal(str(montant))
        if self.solde >= montant_decimal:
            self.solde -= montant_decimal
            self.save(update_fields=['solde', 'date_modification'])
            return True
        return False
         
    def crediter(self, montant):
        from decimal import Decimal
        montant_decimal = Decimal(str(montant))
        self.solde += montant_decimal
        self.save(update_fields=['solde', 'date_modification'])
        return True

    def a_solde_suffisant(self, montant):
        """Vérifie si le solde est suffisant"""
        return self.solde >= montant


class Transaction(models.Model):
    """
    Historique des transactions pour traçabilité
    """
    TYPE_CHOICES = [
        ("paiement_amende", "Paiement d'amende"),
        ("rechargement", "Rechargement du compte"),
        ("remboursement", "Remboursement"),
    ]
    
    STATUT_CHOICES = [
        ("en_attente", "En attente"),
        ("reussie", "Réussie"),
        ("echouee", "Échouée"),
        ("annulee", "Annulée"),
    ]
    
    compte = models.ForeignKey(
        CompteBancaire, 
        on_delete=models.CASCADE, 
        related_name="transactions"
    )
    type_transaction = models.CharField(max_length=20, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_attente")
    reference = models.CharField(max_length=50, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ["-date_creation"]
    
    def __str__(self):
        return f"{self.get_type_transaction_display()} - {self.montant} DH - {self.get_statut_display()}"
    
    def save(self, *args, **kwargs):
        if not self.reference:
            # Générer une référence unique
            import uuid
            self.reference = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
# banking/models.py - Ajouter à la fin du fichier

class CompteEntreprise(models.Model):
    """Compte bancaire de l'entreprise (où vont les amendes)"""
    nom = models.CharField(max_length=100, default="BiblIntel - Compte principal")
    solde = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Compte entreprise"
        verbose_name_plural = "Comptes entreprise"
    
    def __str__(self):
        return f"{self.nom} - {self.solde} DH"
    def crediter(self, montant):
        from decimal import Decimal
        montant_decimal = Decimal(str(montant))
        self.solde += montant_decimal
        self.save(update_fields=['solde', 'date_modification'])
        return True
    def debiter(self, montant):
        from decimal import Decimal
        montant_decimal = Decimal(str(montant))
        if self.solde >= montant_decimal:
            self.solde -= montant_decimal
            self.save(update_fields=['solde', 'date_modification'])
            return True
        return False
         