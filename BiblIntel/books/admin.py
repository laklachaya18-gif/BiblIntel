from django.contrib import admin
from .models import Categorie, Livre, Avis

@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ["nom", "description"]
@admin.register(Livre)
class LivreAdmin(admin.ModelAdmin):
    list_display = ["titre", "auteur", "statut", "date_ajout", "nombre_emprunts"]
    list_filter = ["statut", "categories", "langue"]
    search_fields = ["titre", "auteur", "tags"]
    filter_horizontal = ["categories"]


@admin.register(Avis)
class AvisAdmin(admin.ModelAdmin):
    list_display = ["livre", "utilisateur", "note", "date_creation"]
