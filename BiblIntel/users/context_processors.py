from borrowings.models import Emprunt

def amendes_context(request):
    """Ajoute le total des amendes impayées à tous les templates"""
    total_amendes = 0
    if request.user.is_authenticated and not request.user.is_staff and request.user.status != "bibliothecaire":
        emprunts = Emprunt.objects.filter(utilisateur=request.user)
        total_amendes = sum(e.amende_totale for e in emprunts if e.amende_totale > 0 and not e.est_payee)
    
    return {
        'total_amendes_non_payees': total_amendes,
    }
def bibliothecaire_notifications_count(request):
    """Ajoute le nombre de paiements en attente pour les bibliothécaires"""
    count = 0
    if request.user.is_authenticated and request.user.status == "bibliothecaire":
        from borrowings.models import Emprunt
        from books.models import Livre
        livres_biblio = Livre.objects.filter(bibliothecaire=request.user)
        count = Emprunt.objects.filter(
            demande_paiement_manuel=True,
            est_payee=False,
            amende_totale__gt=0,
            livre__in=livres_biblio
        ).count()
    return {'paiements_attente_count': count}