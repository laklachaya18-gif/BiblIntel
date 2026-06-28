from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncHour, TruncDate
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json

from books.models import Livre, Categorie
from users.models import User
from borrowings.models import Emprunt, Reservation
from logs.models import LogAction
from notifications.models import Notification  
from banking.models import CompteEntreprise
from borrowings.views import _check_blacklist

from django.http import JsonResponse

@login_required
def bibliothecaire_notifications(request):
    """Interface des notifications pour bibliothécaire"""
    if request.user.status != "bibliothecaire" and not request.user.is_staff:
        messages.error(request, "Accès réservé aux bibliothécaires.")
        return redirect("users:home")
    
    user = request.user
    
    # Paiements manuels en attente
    paiements_attente = Emprunt.objects.filter(
        demande_paiement_manuel=True,
        est_payee=False,
        amende_totale__gt=0
    ).select_related('utilisateur', 'livre')

    
    # Historique des gains du bibliothécaire
    livres_ajoutes = Livre.objects.filter(bibliothecaire=user)
    
    total_gains_base = sum(l.gain_salaire_base for l in livres_ajoutes)
    total_gains_bonus = sum(l.gain_salaire_bonus_note for l in livres_ajoutes)
    total_gains_emprunts = sum(l.gain_salaire_emprunts for l in livres_ajoutes)
    
    # Construire l'historique des gains
    historique_gains = []
    for livre in livres_ajoutes.order_by('-date_ajout')[:20]:
        if livre.gain_salaire_base > 0:
            historique_gains.append({
                'date': livre.date_ajout,
                'livre_titre': livre.titre,
                'type': 'base',
                'montant': float(livre.gain_salaire_base)
            })
        if livre.gain_salaire_bonus_note > 0:
            historique_gains.append({
                'date': livre.date_modification,
                'livre_titre': livre.titre,
                'type': 'bonus',
                'montant': float(livre.gain_salaire_bonus_note)
            })
        if livre.gain_salaire_emprunts > 0:
            historique_gains.append({
                'date': livre.date_modification,
                'livre_titre': livre.titre,
                'type': 'emprunt',
                'montant': float(livre.gain_salaire_emprunts)
            })
    
    # Trier par date décroissante
    historique_gains.sort(key=lambda x: x['date'], reverse=True)
    
    # Notifications du bibliothécaire
    notifications = Notification.objects.filter(
        utilisateur=user
    ).order_by('-date_creation')[:20]
    
    context = {
        'paiements_attente': paiements_attente,
        'historique_gains': historique_gains,
        'salaire_total': user.salaire_total,
        'total_gains_base': total_gains_base,
        'total_gains_bonus': total_gains_bonus,
        'total_gains_emprunts': total_gains_emprunts,
        'notifications': notifications,
    }
    
    return render(request, 'dashboard/bibliothecaire_notifications.html', context)


@login_required
def api_rechercher_utilisateurs(request):
    """API de recherche d'utilisateurs pour les bibliothécaires"""
    if request.user.status != "bibliothecaire" and not request.user.is_staff:
        return JsonResponse({'error': 'Accès non autorisé'}, status=403)
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
    users = User.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(username__icontains=query) |
        Q(email__icontains=query)
    ).exclude(status='bibliothecaire').exclude(is_staff=True)[:20]
    
    resultats = []
    for user in users:
        # Calculer le total des amendes impayées
        emprunts = Emprunt.objects.filter(utilisateur=user, est_payee=False)
        total_amendes = sum(e.amende_totale for e in emprunts if e.amende_totale)
        
        resultats.append({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'status_display': user.get_status_display(),
            'total_amendes': float(total_amendes),
        })
    
    return JsonResponse({'users': resultats})
@login_required
def admin_user_detail(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("users:home")

    user_detail = get_object_or_404(User, pk=pk)
    emprunts = Emprunt.objects.filter(utilisateur=user_detail)
    reservations = Reservation.objects.filter(utilisateur=user_detail, est_active=True)
    emprunts_en_cours = emprunts.filter(statut__in=["en_cours", "retard"]).count()
    
    return render(request, "dashboard/admin_user_detail.html", {
        'user_detail': user_detail,
        'emprunts': emprunts,
        'reservations': reservations,
        'emprunts_en_cours': emprunts_en_cours,
    })

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("users:home")

    users_normaux = User.objects.filter(is_staff=False)
    emprunts_tous = Emprunt.objects.exclude(utilisateur__is_staff=True)

    # ── Compteurs KPI ──────────────────────────────────────────────────────
    total_livres = Livre.objects.count()
    total_utilisateurs = users_normaux.count()
    emprunts_en_cours = emprunts_tous.filter(statut__in=["en_cours", "approuve"]).count()
    retards = emprunts_tous.filter(statut="retard").count()
    blacklistes = users_normaux.filter(est_blackliste=True).count()
    en_attente_fifo = emprunts_tous.filter(statut="en_attente").count()

    amendes_qs = emprunts_tous.filter(est_payee=False, amende_totale__gt=0)
    total_amendes = sum(e.amende_totale for e in amendes_qs)

    # ── Répartition utilisateurs par rôle (camembert) ─────────────────────
    roles_data = {
        "Étudiant": users_normaux.filter(status="etudiant").count(),
        "Enseignant": users_normaux.filter(status="enseignant").count(),
        "Bibliothécaire": users_normaux.filter(status="bibliothecaire").count(),  # ✅ corrigé
        "Employeur": users_normaux.filter(status="employeur").count(),  # ✅ NOUVEAU
        "Personne normale": users_normaux.filter(status="personne").count(),
    }

    # ── Activité horaire (7 derniers jours) ───────────────────────────────
    sept_jours_ago = timezone.now() - timedelta(days=7)
    logs_par_heure = (
        LogAction.objects.filter(
            date_action__gte=sept_jours_ago,
            type_action="connexion"
        )
        .annotate(heure=TruncHour("date_action"))
        .values("heure")
        .annotate(nb=Count("id"))
        .order_by("heure")[:48]
    )
    activite_labels = [str(l["heure"].strftime("%d/%m %Hh")) if l["heure"] else "?" for l in logs_par_heure]
    activite_data = [l["nb"] for l in logs_par_heure]

    # ── Livres par catégorie ───────────────────────────────────────────────
    cats = Categorie.objects.annotate(nb_livres=Count("livres")).filter(nb_livres__gt=0).order_by("-nb_livres")[:8]
    cats_labels = [c.nom for c in cats]
    cats_data = [c.nb_livres for c in cats]

    # ── Top livres empruntés ───────────────────────────────────────────────
    top_livres = Livre.objects.annotate(nb=Count("emprunts")).order_by("-nb")[:8]
    top_livres_labels = [l.titre[:20] for l in top_livres]
    top_livres_data = [l.nb for l in top_livres]

    # ── Emprunts par mois (6 derniers mois) ───────────────────────────────
    six_mois_ago = timezone.now() - timedelta(days=180)
    emprunts_par_jour = (
        emprunts_tous.filter(date_demande__gte=six_mois_ago)
        .annotate(jour=TruncDate("date_demande"))
        .values("jour")
        .annotate(nb=Count("id"))
        .order_by("jour")
    )
    emp_labels = [str(e["jour"].strftime("%d/%m")) for e in emprunts_par_jour]
    emp_data = [e["nb"] for e in emprunts_par_jour]

    # ── Table bibliothécaires (anciennement fonctionnaires) ───────────────
    bibliothecaires = (
    users_normaux.filter(status="bibliothecaire")
    .annotate(
        nb_livres_ajoutes=Count("livres_ajoutes_bibliothecaire", distinct=True),
        total_gains_base=Sum("livres_ajoutes_bibliothecaire__gain_salaire_base"),
        total_gains_bonus=Sum("livres_ajoutes_bibliothecaire__gain_salaire_bonus_note"),
        total_gains_emprunts=Sum("livres_ajoutes_bibliothecaire__gain_salaire_emprunts")
    )
    .order_by("-salaire_total")
)
    for biblio in bibliothecaires:
        biblio.total_gains = (biblio.total_gains_base or 0) + (biblio.total_gains_bonus or 0) + (biblio.total_gains_emprunts or 0)
    # ── Listes existantes ─────────────────────────────────────────────────
    livres_populaires = Livre.objects.annotate(nb_emprunts_total=Count("emprunts")).order_by("-nb_emprunts_total")[:5]
    utilisateurs_actifs = users_normaux.annotate(nb_emprunts=Count("emprunts")).order_by("-nb_emprunts")[:5]
    
    # ✅ Exclure les bibliothécaires du classement fidélité
    classement_fidelite = users_normaux.exclude(status="bibliothecaire").order_by("-points_fidelite")[:5]
    
    derniers_emprunts = emprunts_tous.select_related("utilisateur", "livre").order_by("-date_demande")[:10]
    emprunts_retard = emprunts_tous.filter(statut="retard").select_related("utilisateur", "livre")[:10]
    
    actions_bibliothecaires = LogAction.objects.filter(
        type_action="crud_livre",
        utilisateur__status="bibliothecaire",
        utilisateur__is_staff=False
    ).select_related("utilisateur").order_by("-date_action")[:50]
    
    stats = {
        "total_livres": total_livres,
        "total_utilisateurs": total_utilisateurs,
        "emprunts_en_cours": emprunts_en_cours,
        "retards": retards,
        "blacklistes": blacklistes,
        "total_amendes": total_amendes,
        "en_attente_fifo": en_attente_fifo,
        "roles_labels": json.dumps(list(roles_data.keys())),
        "roles_data": json.dumps(list(roles_data.values())),
        "activite_labels": json.dumps(activite_labels),
        "activite_data": json.dumps(activite_data),
        "cats_labels": json.dumps(cats_labels),
        "cats_data": json.dumps(cats_data),
        "top_livres_labels": json.dumps(top_livres_labels),
        "top_livres_data": json.dumps(top_livres_data),
        "emp_labels": json.dumps(emp_labels),
        "emp_data": json.dumps(emp_data),
        "fonctionnaires": bibliothecaires,  # ✅ gardé pour compatibilité template
        "bibliothecaires": bibliothecaires,  # ✅ nouveau nom
        "livres_populaires": livres_populaires,
        "utilisateurs_actifs": utilisateurs_actifs,
        "classement_fidelite": classement_fidelite,
        "derniers_emprunts": derniers_emprunts,
        "emprunts_retard": emprunts_retard,
        "actions_fonctionnaires": actions_bibliothecaires,  # ✅ gardé pour compatibilité template
        "actions_bibliothecaires": actions_bibliothecaires,  # ✅ nouveau nom
    }
    
    return render(request, "dashboard/admin_dashboard.html", stats)

@login_required
def admin_bibliothecaire_detail(request, pk):
    """Vue admin pour voir le détail du salaire d'un bibliothécaire"""
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("users:home")
    
    bibliothecaire = get_object_or_404(User, pk=pk, status="bibliothecaire")
    
    # Récupérer tous les livres ajoutés par ce bibliothécaire
    livres = Livre.objects.filter(bibliothecaire=bibliothecaire).order_by("-date_ajout")

    # Calculer les totaux
    total_gains_base = sum(l.gain_salaire_base for l in livres)
    total_gains_bonus = sum(l.gain_salaire_bonus_note for l in livres)
    total_gains_emprunts = sum(l.gain_salaire_emprunts for l in livres)
    
    # Historique des actions (logs)
    historique_actions = LogAction.objects.filter(
        utilisateur=bibliothecaire,
        type_action="crud_livre"
    ).order_by("-date_action")[:50]
    
    context = {
        "bibliothecaire": bibliothecaire,
        "livres": livres,
        "total_livres": livres.count(),
        "total_emprunts": sum(l.nombre_emprunts for l in livres),
        "total_gains_base": total_gains_base,
        "total_gains_bonus": total_gains_bonus,
        "total_gains_emprunts": total_gains_emprunts,
        "salaire_total": bibliothecaire.salaire_total,
        "historique_actions": historique_actions,
    }
    
    return render(request, "dashboard/admin_bibliothecaire_detail.html", context)
@login_required
def admin_toggle_blacklist(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("users:home")

    user = get_object_or_404(User, pk=pk)
    user.est_blackliste = not user.est_blackliste
    user.save()

    status = "ajouté à" if user.est_blackliste else "retiré de"
    messages.success(request, f"Utilisateur {user.username} {status} la blacklist.")
    return redirect("dashboard:admin_user_detail", pk=pk)


@login_required
def blacklist_admin(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("users:home")

    blacklistes = User.objects.filter(is_staff=False, est_blackliste=True)
    return render(request, "dashboard/blacklist.html", {"blacklistes": blacklistes})
@login_required
def bibliothecaire_dashboard(request):
    """Dashboard pour les bibliothécaires : salaire, livres ajoutés, statistiques"""
    
    # Vérifier que l'utilisateur est un bibliothécaire
    if request.user.status != "bibliothecaire":
        messages.error(request, "Accès réservé aux bibliothécaires.")
        return redirect("users:home")
    
    user = request.user
    
    # Récupérer tous les livres ajoutés par ce bibliothécaire
    livres_ajoutes = Livre.objects.filter(bibliothecaire=user).order_by("-date_ajout")

    
    # Statistiques
    stats = {
        "total_livres_ajoutes": livres_ajoutes.count(),
        "total_emprunts_sur_livres": sum(livre.nombre_emprunts for livre in livres_ajoutes),
        "total_gains_base": sum(livre.gain_salaire_base for livre in livres_ajoutes),
        "total_gains_bonus": sum(livre.gain_salaire_bonus_note for livre in livres_ajoutes),
        "total_gains_emprunts": sum(livre.gain_salaire_emprunts for livre in livres_ajoutes),
        "salaire_total": user.salaire_total,
        "rib": user.rib,
    }
    
    # Classement des livres par popularité
    livres_populaires = livres_ajoutes.order_by("-nombre_emprunts")[:10]
    
    # Derniers livres ajoutés
    derniers_livres = livres_ajoutes[:10]
    
    # Livres avec bonus de note (note moyenne > 4)
    livres_bonus = livres_ajoutes.filter(gain_salaire_bonus_note__gt=0)
    
    context = {
        "user": user,
        "stats": stats,
        "livres_ajoutes": livres_ajoutes,
        "livres_populaires": livres_populaires,
        "derniers_livres": derniers_livres,
        "livres_bonus": livres_bonus,
    }
    
    return render(request, "dashboard/bibliothecaire_dashboard.html", context)
# ==================== PAIEMENTS MANUELS POUR BIBLIOTHÉCAIRE ====================


@login_required
def paiements_manuels_attente(request):
    """Liste des demandes de paiement manuel en attente (pour bibliothécaire)"""
    
    if request.user.status != "bibliothecaire" and not request.user.is_staff:
        messages.error(request, "Accès réservé aux bibliothécaires.")
        return redirect("users:home")
    
    demandes = Emprunt.objects.filter(
        demande_paiement_manuel=True,
        est_payee=False,
        amende_totale__gt=0
    ).select_related('utilisateur', 'livre')
    
    if request.user.is_staff:
        pass
    
    # ✅ Bibliothécaire : voir TOUS les paiements (pas de filtre)
    # Pour tester, commente le filtre :
    
    return render(request, 'dashboard/paiements_attente.html', {'demandes': demandes})
    
@login_required
def valider_paiement_manuel(request, pk):
    """Validation d'une demande de paiement manuel par le bibliothécaire"""
    
    if request.user.status != "bibliothecaire" and not request.user.is_staff:
        messages.error(request, "Accès réservé aux bibliothécaires.")
        return redirect("users:home")
    
    emprunt = get_object_or_404(Emprunt, pk=pk, demande_paiement_manuel=True, est_payee=False)
    
    if request.method == "POST":
        # Appliquer réduction si 100+ points
        montant = float(emprunt.amende_totale)
        
        if emprunt.utilisateur.points_fidelite >= 100 and emprunt.utilisateur.status != "bibliothecaire":
            montant = round(montant * 0.5, 2)
            emprunt.utilisateur.points_fidelite -= 100
            emprunt.utilisateur.save()
            messages.info(request, f"Réduction 50% appliquée ! Montant final : {montant} DH")
        
        # Valider le paiement
        emprunt.est_payee = True
        emprunt.amende_totale = montant
        emprunt.demande_paiement_manuel = False
        emprunt.paiement_valide_par = request.user
        emprunt.paiement_valide_le = timezone.now()
        emprunt.save()
        
        # Notification à l'utilisateur
        Notification.objects.create(
            utilisateur=emprunt.utilisateur,
            type_notification="validation",
            titre="✅ Paiement manuel validé",
            message=f"Votre paiement de {montant} DH pour '{emprunt.livre.titre}' a été validé par {request.user.first_name}."
        )
        
        # Vérifier si la blacklist peut être levée
        from borrowings.views import _check_blacklist
        _check_blacklist(emprunt.utilisateur)
        
        messages.success(request, f"✅ Paiement de {montant} DH validé pour {emprunt.utilisateur.first_name}.")
        return redirect("dashboard:paiements_manuels_attente")
    
    return render(request, 'dashboard/valider_paiement.html', {'emprunt': emprunt})