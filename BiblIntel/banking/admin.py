from django.contrib import admin
from .models import CompteBancaire, Transaction

@admin.register(CompteBancaire)
class CompteBancaireAdmin(admin.ModelAdmin):
    list_display = ["utilisateur", "solde", "date_creation"]
    search_fields = ["utilisateur__username", "utilisateur__email"]
    list_filter = ["date_creation"]
    readonly_fields = ["date_creation", "date_modification"]

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["reference", "compte", "type_transaction", "montant", "statut", "date_creation"]
    search_fields = ["reference", "compte__utilisateur__username"]
    list_filter = ["type_transaction", "statut", "date_creation"]
    readonly_fields = ["reference", "date_creation"]