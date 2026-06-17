from django import forms
from .models import Livre, Avis, Categorie


class LivreForm(forms.ModelForm):
    max_emprunts_simultanes = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Nombre max d'emprunts simultanés *",
        help_text="Combien de personnes peuvent emprunter ce livre en même temps (FIFO si dépassé)",
        widget=forms.NumberInput(attrs={"min": "1"}),
    )

    class Meta:
        model = Livre
        fields = [
            "titre",
            "auteur",
            "resume",
            "categories",
            "filiere_cible",
            "fichier_pdf",
            "couverture",
            "tags",
            "nombre_pages",
            "langue",
            "statut",
            "musique_ambiance",
            "max_emprunts_simultanes",
        ]
        widgets = {
            "resume": forms.Textarea(attrs={"rows": 5}),
            "tags": forms.TextInput(attrs={"placeholder": "tag1, tag2, tag3"}),
            "categories": forms.CheckboxSelectMultiple(),
        }

    def clean_max_emprunts_simultanes(self):
        val = self.cleaned_data.get("max_emprunts_simultanes")
        if val is None or val < 1:
            raise forms.ValidationError("La valeur doit être au moins 1.")
        return val

    def save(self, commit=True):
        livre = super().save(commit=False)
        # S'assurer que ajoute_par est géré en vue
        if commit:
            livre.save()
            self.save_m2m()
        return livre


class AvisForm(forms.ModelForm):
    class Meta:
        model = Avis
        fields = ["note", "commentaire"]
        widgets = {
            "note": forms.RadioSelect(choices=[(i, i) for i in range(1, 6)]),
            "commentaire": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Votre commentaire..."}
            ),
        }
