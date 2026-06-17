from django.db import models
from django.conf import settings


class Categorie(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sous_categories",
    )

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"


class Livre(models.Model):
    
    gain_salaire_base = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gain_salaire_bonus_note = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gain_salaire_emprunts = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    STATUT_CHOICES = [
        ("disponible", "Disponible"),
        ("emprunte", "Emprunté"),
        ("reserve", "Réservé"),
        ("archive", "Archivé"),
    ]

    titre = models.CharField(max_length=255)
    auteur = models.CharField(max_length=255)
    resume = models.TextField()

    categories = models.ManyToManyField(Categorie, blank=True, related_name="livres")

    filiere_cible = models.CharField(max_length=100, blank=True, null=True)

    # PDF DU LIVRE
    fichier_pdf = models.FileField(upload_to="livres/pdfs/", blank=True, null=True)

    # IMAGE DE COUVERTURE
    couverture = models.ImageField(
        upload_to="livres/couvertures/", blank=True, null=True
    )

    tags = models.CharField(
        max_length=500, blank=True, help_text="Mots-clés séparés par des virgules"
    )

    nombre_pages = models.PositiveIntegerField(default=0)

    langue = models.CharField(max_length=50, default="Français")

    date_ajout = models.DateTimeField(auto_now_add=True)

    date_modification = models.DateTimeField(auto_now=True)

    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default="disponible"
    )

    nombre_emprunts = models.PositiveIntegerField(default=0)

    note_moyenne = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

    # MUSIQUE D'AMBIANCE (optionnel)
    musique_ambiance = models.FileField(
        upload_to='livres/musiques/',
        null=True,
        blank=True,
        help_text="Fichier audio (MP3) pour la musique d'ambiance du livre"
    )
    max_emprunts_simultanes = models.PositiveIntegerField(default=1)
    ajoute_par = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="livres_ajoutes_par"
    )    
    bibliothecaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="livres_ajoutes_bibliothecaire"
    )
        
    
    def mettre_a_jour_salaire_bibliothecaire(self):
        """Met à jour le salaire du bibliothécaire lié à ce livre"""
        if not self.bibliothecaire:
            return
        
        # Calcul du gain total pour ce livre
        gain_total = self.gain_salaire_base + self.gain_salaire_bonus_note + self.gain_salaire_emprunts
        
        # Mettre à jour le salaire du bibliothécaire
        self.bibliothecaire.salaire_total = sum(
            livre.gain_salaire_base + livre.gain_salaire_bonus_note + livre.gain_salaire_emprunts
            for livre in Livre.objects.filter(bibliothecaire=self.bibliothecaire)
        )
        self.bibliothecaire.save()
    def __str__(self):
        return self.titre

    class Meta:
        ordering = ["-date_ajout"]
        verbose_name = "Livre"
        verbose_name_plural = "Livres"
        # ⚠️ NE PAS METTRE musique_ambiance ICI !!!

class Avis(models.Model):

    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name="avis")

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    note = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])

    commentaire = models.TextField(blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilisateur} - {self.livre} ({self.note}/5)"

    class Meta:
        unique_together = ["livre", "utilisateur"]
        verbose_name = "Avis"
        verbose_name_plural = "Avis"
class UserBookmark(models.Model):
    """Marque-page utilisateur pour un livre"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name='bookmarks')
    page = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'livre']
    
    def __str__(self):
        return f"{self.user.username} - {self.livre.titre} - page {self.page}"


class UserNote(models.Model):
    """Notes personnelles de l'utilisateur pour un livre"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notes')
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name='notes')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'livre']
    
    def __str__(self):
        return f"{self.user.username} - {self.livre.titre}"


class UserWord(models.Model):
    """Mots recherchés par l'utilisateur dans un livre"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='words')
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name='words')
    word = models.CharField(max_length=255)
    definition = models.TextField(blank=True)
    searched_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'livre', 'word']
        ordering = ['-searched_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.livre.titre} - {self.word}"
