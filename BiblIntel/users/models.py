from django.contrib.auth.models import AbstractUser
from django.db import models
from django.shortcuts import redirect

class User(AbstractUser):
    STATUS_CHOICES = [
        ("etudiant", "Étudiant"),
        ("enseignant", "Enseignant"),
        ("bibliothecaire", "Bibliothécaire"),  # ✅ Anciennement "fonctionnaire"
        ("personne", "Personne normale"),
        ("employeur", "Employeur"),  # ✅ NOUVEAU RÔLE
        ("admin", "Administrateur"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="personne"
    )
    
    # ===== CHAMPS EXISTANTS =====
    filiere = models.CharField(max_length=100, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    date_naissance = models.DateField(blank=True, null=True)
    photo_profil = models.ImageField(upload_to="profiles/", blank=True, null=True)
    points_fidelite = models.PositiveIntegerField(default=0)
    est_blackliste = models.BooleanField(default=False)
    date_blacklist = models.DateTimeField(blank=True, null=True)
    raison_blacklist = models.TextField(blank=True, null=True)
    date_inscription = models.DateTimeField(auto_now_add=True)
    derniere_connexion = models.DateTimeField(blank=True, null=True)
    
    # ===== NOUVEAUX CHAMPS POUR BIBLIOTHÉCAIRE (SALAIRE) =====
    salaire_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rib = models.CharField(max_length=50, blank=True, null=True, help_text="RIB pour virement salaire")
    
    # ===== NOUVEAUX CHAMPS POUR RECOMMANDATIONS PERSONNALISÉES =====
    domaine_professionnel = models.CharField(max_length=100, blank=True, null=True)  # pour employeur
    matiere_enseignee = models.CharField(max_length=100, blank=True, null=True)  # pour enseignant
    
    # ===== RELATIONS D'AUTH =====
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="biblintel_user_groups",
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="biblintel_user_permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )
    
    # ===== CATÉGORIES PRÉFÉRÉES =====
    categories_preferees = models.ManyToManyField(
        "books.Categorie",
        blank=True
    )
    est_valide = models.BooleanField(default=False, help_text="Compte validé par l'admin", null=True)
    date_demande_validation = models.DateTimeField(blank=True, null=True)
    def save(self, *args, **kwargs):
        # ✅ Admin : pas de points de fidélité
        if self.is_staff or self.status == "admin":
            self.points_fidelite = 0
        
        # ✅ Bibliothécaire : pas de points de fidélité non plus
        if self.status == "bibliothecaire":
            self.points_fidelite = 0
        
        # ✅ Ancienne vérification (gardée pour compatibilité)
        if self.status == "fonctionnaire":
            self.points_fidelite = 0
            
        super().save(*args, **kwargs)

    # ✅ Decorator pour bibliothécaire (anciennement fonctionnaire_required)
    def bibliothecaire_required(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.status != "bibliothecaire":
                return redirect("users:home")
            return view_func(request, *args, **kwargs)
        return wrapper

    # ✅ Garder l'ancien nom pour compatibilité (optionnel)
    fonctionnaire_required = bibliothecaire_required

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"


class CategoryPreference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey("books.Categorie", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "category")

    def __str__(self):
        return f"{self.user.username} -> {self.category.nom}"