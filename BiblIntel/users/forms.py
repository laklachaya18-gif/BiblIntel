from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from books.models import Categorie

class UserRegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")
    email = forms.EmailField(required=True, label="Email")
    status = forms.ChoiceField(choices=User.STATUS_CHOICES, label="Statut")
    
    # ===== CHAMPS COMMUNS =====
    filiere = forms.CharField(max_length=100, required=False, label="Filière (pour étudiant)")
    telephone = forms.CharField(max_length=20, required=False, label="Téléphone")
    date_naissance = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date de naissance"
    )
    photo_profil = forms.ImageField(required=False, label="Photo de profil")
    
    # ===== NOUVEAUX CHAMPS POUR BIBLIOTHÉCAIRE =====
    rib = forms.CharField(
        max_length=50, 
        required=False, 
        label="RIB (obligatoire pour bibliothécaire)",
        help_text="Relevé d'identité bancaire pour les virements de salaire"
    )
    
    # ===== NOUVEAUX CHAMPS POUR EMPLOYEUR =====
    domaine_professionnel = forms.CharField(
        max_length=100, 
        required=False, 
        label="Domaine professionnel (obligatoire pour employeur)",
        help_text="Ex: Finance, Santé, Industrie, Éducation..."
    )
    
    # ===== NOUVEAUX CHAMPS POUR ENSEIGNANT =====
    matiere_enseignee = forms.CharField(
        max_length=100, 
        required=False, 
        label="Matière enseignée (obligatoire pour enseignant)",
        help_text="Ex: Mathématiques, Physique, Informatique..."
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Mot de passe"}),
        label="Mot de passe"
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirmer le mot de passe"}),
        label="Confirmer mot de passe"
    )
    
    categories_preferees = forms.ModelMultipleChoiceField(
        queryset=Categorie.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Catégories préférées",
        help_text="Sélectionnez les catégories de livres que vous aimez lire (recommandations personnalisées)"
    )
    
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "status",
            "filiere",
            "domaine_professionnel",
            "matiere_enseignee",
            "rib",
            "telephone",
            "date_naissance",
            "photo_profil",
            "password1",
            "password2",
            "categories_preferees",
        ]

    # ===== VALIDATION EMAIL UNIQUE =====
    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError("❌ Cet email existe déjà.")
        return email

    # ===== VALIDATION MOT DE PASSE FORT =====
    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        validate_password(password)
        return password

    # ===== VALIDATION GLOBALE =====
    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        status = cleaned_data.get("status")

        # Vérifier que les mots de passe correspondent
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "❌ Les mots de passe ne correspondent pas.")
        if status == "bibliothecaire":
            rib = cleaned_data.get("rib")
            if not rib:
                self.add_error("rib", "Le RIB est obligatoire pour un bibliothécaire")
            cleaned_data["categories_preferees"] = []
            # ✅ On ne valide pas automatiquement le compte
            cleaned_data["est_valide"] = False
        # ===== VALIDATIONS SELON LE RÔLE =====
        
        # Bibliothécaire : RIB obligatoire
        if status == "bibliothecaire":
            rib = cleaned_data.get("rib")
            if not rib:
                self.add_error("rib", "Le RIB est obligatoire pour un bibliothécaire")
            # Supprimer les catégories préférées pour bibliothécaire
            cleaned_data["categories_preferees"] = []
        
        # Employeur : domaine professionnel obligatoire
        elif status == "employeur":
            domaine = cleaned_data.get("domaine_professionnel")
            if not domaine:
                self.add_error("domaine_professionnel", "Le domaine professionnel est obligatoire pour un employeur")
        
        # Enseignant : matière enseignée obligatoire
        elif status == "enseignant":
            matiere = cleaned_data.get("matiere_enseignee")
            if not matiere:
                self.add_error("matiere_enseignee", "La matière enseignée est obligatoire pour un enseignant")
        
        # Étudiant : pas de validation spécifique (filière optionnelle mais recommandée)
        # Personne normale : pas de validation spécifique
        
        # Admin : pas de catégories préférées
        if status == "admin":
            cleaned_data["categories_preferees"] = []

        return cleaned_data


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nom d'utilisateur"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Mot de passe"
        })
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "telephone",
            "filiere",
            "domaine_professionnel",
            "matiere_enseignee",
            "rib",
            "photo_profil",
            "date_naissance",
        ]
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "filiere": "Filière",
            "domaine_professionnel": "Domaine professionnel",
            "matiere_enseignee": "Matière enseignée",
            "rib": "RIB",
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personnaliser les champs selon le rôle de l'utilisateur (optionnel)
        # On peut cacher certains champs si l'utilisateur n'a pas le rôle correspondant
        pass


class UserEditForm(forms.ModelForm):
    """Formulaire pour l'admin ou le bibliothécaire pour modifier un utilisateur"""
    
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "status",
            "filiere",
            "domaine_professionnel",
            "matiere_enseignee",
            "rib",
            "telephone",
            "date_naissance",
            "photo_profil",
            "est_blackliste",
            "points_fidelite",
        ]
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        
        # Validations similaires à UserRegisterForm
        if status == "bibliothecaire" and not cleaned_data.get("rib"):
            self.add_error("rib", "Le RIB est obligatoire pour un bibliothécaire")
        
        elif status == "employeur" and not cleaned_data.get("domaine_professionnel"):
            self.add_error("domaine_professionnel", "Le domaine professionnel est obligatoire pour un employeur")
        
        elif status == "enseignant" and not cleaned_data.get("matiere_enseignee"):
            self.add_error("matiere_enseignee", "La matière enseignée est obligatoire pour un enseignant")
        
        return cleaned_data