from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from .models import Emprunt, Reservation
from books.models import Livre
from users.models import User
from notifications.models import Notification
from logs.models import LogAction
from banking.models import CompteBancaire
import json 
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import io
from banking.models import CompteEntreprise


# ==================== FONCTIONS UTILITAIRES ====================

def _log(user, type_action, description, request=None):
    ip = None
    if request:
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = x_forwarded.split(",")[0] if x_forwarded else request.META.get("REMOTE_ADDR")
    LogAction.objects.create(
        utilisateur=user,
        type_action=type_action,
        description=description,
        ip_adresse=ip,
    )

def _notif(user, type_notif, titre, message):
    Notification.objects.create(
        utilisateur=user, type_notification=type_notif, titre=titre, message=message
    )

def _check_blacklist(user):
    """Vérifie si l'utilisateur doit être blacklisté ou retiré de la blacklist"""
    emprunts_actifs = Emprunt.objects.filter(utilisateur=user, statut__in=["en_cours", "retard"])
    retards = emprunts_actifs.filter(statut="retard").count()
    amendes_vieilles = Emprunt.objects.filter(
        utilisateur=user,
        est_payee=False,
        statut="retard",
        date_retour_effective__lt=timezone.now() - timedelta(days=30),
    ).exists()
    total_amendes = sum(
        e.amende_totale for e in Emprunt.objects.filter(utilisateur=user, est_payee=False)
        if e.amende_totale and e.amende_totale > 0
    )
    should_blacklist = retards >= 3 or amendes_vieilles or total_amendes > 100

    if should_blacklist and not user.est_blackliste:
        user.est_blackliste = True
        if retards >= 3:
            user.raison_blacklist = f"{retards} retards simultanés"
        elif amendes_vieilles:
            user.raison_blacklist = "Amendes impayées depuis plus de 30 jours"
        else:
            user.raison_blacklist = f"Amendes impayées dépassant 100 DH ({total_amendes} DH)"
        user.date_blacklist = timezone.now()
        user.save()
        _notif(user, "blacklist", "⚠️ Vous avez été blacklisté", f"Raison : {user.raison_blacklist}")
        _log(user, "blacklist", f"Blacklist auto : {user.raison_blacklist}")
    elif not should_blacklist and user.est_blackliste:
        user.est_blackliste = False
        user.raison_blacklist = None
        user.date_blacklist = None
        user.save()
        _notif(user, "validation", "✅ Blacklist levée", "Votre compte est réactivé. Vous pouvez à nouveau emprunter des livres.")
        _log(user, "blacklist", "Retrait automatique de la blacklist")

def _attribuer_points(user, emprunt):
    """Attribue des points de fidélité à l'utilisateur"""
    if user.status == "bibliothecaire":
        return 0, "bibliothecaire - aucun point"

    now = timezone.now().date()
    retour_prevu = emprunt.date_retour_prevue
    debut = emprunt.date_debut.date() if emprunt.date_debut else None
    jours_emprunt = (now - debut).days if debut else 0

    if retour_prevu and now > retour_prevu:
        return 0, "retour en retard - aucun point"

    if jours_emprunt < 25:
        return 0, "retour avant 25 jours d'emprunt - aucun point"

    if now < retour_prevu:
        pts = 30
        raison = "retour avant délai (après 25 jours)"
    else:
        pts = 10
        raison = "retour dans les délais"

    a_avis = emprunt.livre.avis.filter(utilisateur=user).exists()
    if a_avis:
        pts += 20
        raison += " + avis/notation"

    user.points_fidelite += pts
    user.save()
    return pts, raison

def _verifier_eligibilite_emprunt(user, livre, request):
    """Vérifie si l'utilisateur peut emprunter un livre"""
    _check_blacklist(user)
    if user.est_blackliste:
        _notif(user, "refus", "Emprunt refusé", f'Emprunt de "{livre.titre}" refusé : vous êtes blacklisté.')
        return False, f"Vous êtes sur liste noire ({user.raison_blacklist})."

    emprunts_en_cours = Emprunt.objects.filter(utilisateur=user, statut__in=["en_cours", "approuve", "retard"]).count()
    if emprunts_en_cours >= 3:
        _notif(user, "refus", "Emprunt refusé", f'Emprunt de "{livre.titre}" refusé : limite de 3 emprunts atteinte.')
        return False, "Limite de 3 emprunts simultanés atteinte."

    amendes = Emprunt.objects.filter(utilisateur=user, est_payee=False)
    total_amendes = sum(e.amende_totale for e in amendes if e.amende_totale and e.amende_totale > 0)
    if total_amendes > 100:
        _notif(user, "refus", "Emprunt refusé", f'Emprunt de "{livre.titre}" refusé : amendes impayées ({total_amendes} DH).')
        return False, f"Amendes impayées ({total_amendes} DH). Emprunt bloqué."

    return True, None


# ==================== PAGES D'AMENDES ====================

@login_required
def mes_amendes(request):
    """Page dédiée aux amendes de l'utilisateur connecté"""
    tous_les_emprunts = Emprunt.objects.filter(utilisateur=request.user).order_by('-date_demande')
    
    amendes_impayees = [e for e in tous_les_emprunts if e.amende_totale > 0 and not e.est_payee]
    amendes_payees = [e for e in tous_les_emprunts if e.amende_totale > 0 and e.est_payee]
    
    # Amendes payables (livre retourné ET non payée)
    amendes_payables = [e for e in amendes_impayees if e.statut == "retourne"]
    total_payables = sum(e.amende_totale for e in amendes_payables)
    
    total_impayees = sum(e.amende_totale for e in amendes_impayees)
    total_payees = sum(e.amende_totale for e in amendes_payees)
    nombre_retards = len([e for e in tous_les_emprunts if e.statut == "retard"])
    
    reduction_disponible = request.user.points_fidelite >= 100 and request.user.status != "bibliothecaire"
    
    message_alerte = None
    if total_impayees > 100:
        message_alerte = "⚠️ Vos amendes dépassent 100 DH. Vos emprunts sont bloqués jusqu'à régularisation."
    elif total_impayees > 50:
        message_alerte = "⚠️ Attention : vos amendes approchent du seuil de blocage (100 DH)."
    
    chart_data = {
        'labels': ['Payées', 'Impayées'],
        'data': [float(total_payees), float(total_impayees)],
        'colors': ['#34d399', '#f87171']
    }
    
    return render(request, 'borrowings/mes_amendes.html', {
        'amendes_impayees': amendes_impayees,
        'amendes_payees': amendes_payees,
        'amendes_payables': amendes_payables,
        'total_payables': total_payables,
        'total_impayees': total_impayees,
        'total_payees': total_payees,
        'nombre_retards': nombre_retards,
        'reduction_disponible': reduction_disponible,
        'message_alerte': message_alerte,
        'points_utilisateur': request.user.points_fidelite,
        'chart_data': json.dumps(chart_data),
    })

@login_required
def export_amendes_pdf(request):
    """Exporte l'historique des amendes en PDF"""
    emprunts = Emprunt.objects.filter(utilisateur=request.user, amende_totale__gt=0).order_by('-date_demande')
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(2*cm, height - 2*cm, "Historique de mes amendes")
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, height - 2.5*cm, f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}")
    
    data = [["Livre", "Date emprunt", "Retour prévu", "Amende", "Statut"]]
    for emp in emprunts:
        data.append([
            emp.livre.titre[:40],
            emp.date_demande.strftime("%d/%m/%Y"),
            emp.date_retour_prevue.strftime("%d/%m/%Y") if emp.date_retour_prevue else "-",
            f"{emp.amende_totale} DH",
            "Payée" if emp.est_payee else "Impayée"
        ])
    
    table = Table(data, colWidths=[6*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6366f1')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#cbd5e1')),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#334155')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    table.wrapOn(p, width - 4*cm, height - 6*cm)
    table.drawOn(p, 2*cm, height - 6*cm - len(data)*0.6*cm)
    
    total_impayees = sum(e.amende_totale for e in emprunts if not e.est_payee)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2*cm, 5*cm, f"Total des amendes impayées : {total_impayees} DH")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="mes_amendes_{timezone.now().strftime("%Y%m%d")}.pdf"'
    return response

@login_required
def payer_amende_en_ligne(request, pk):
    """Paiement en ligne d'une amende individuelle"""
    emprunt = get_object_or_404(Emprunt, pk=pk, utilisateur=request.user)
    
    if emprunt.statut != "retourne":
        messages.error(request, "❌ Vous devez d'abord retourner le livre avant de pouvoir payer l'amende.")
        return redirect("borrowings:emprunt_list")
    
    if emprunt.est_payee:
        messages.info(request, "Cette amende est déjà payée.")
        return redirect("borrowings:emprunt_list")
    
    if emprunt.amende_totale <= 0:
        messages.info(request, "Aucune amende à payer.")
        return redirect("borrowings:emprunt_list")
    
    if request.method == "POST":
        numero = request.POST.get("numero_carte")
        expiration = request.POST.get("expiration")
        cvv = request.POST.get("cvv")
        
        compte, created = CompteBancaire.objects.get_or_create(
            
            utilisateur=request.user,
            defaults={
                "solde": 500,
                "numero_carte": numero,
                "date_expiration": expiration,
                "cryptogramme": cvv
            }
        )
        compte.refresh_from_db()
        montant = float(emprunt.amende_totale)
        
        if request.user.points_fidelite >= 100 and request.user.status != "bibliothecaire" and not request.user.is_staff:
            montant = round(montant * 0.5, 2)
            request.user.points_fidelite -= 100
            request.user.save()
            messages.info(request, f"Réduction 50% appliquée ! Montant : {montant} DH")
        
        if compte.debiter(montant):
            emprunt.est_payee = True
            emprunt.amende_totale = montant
            emprunt.save()
            
            compte_entreprise, created = CompteEntreprise.objects.get_or_create(
                id=1,
                defaults={'solde': 0, 'nom': 'BiblIntel - Compte principal'}
            )
            compte_entreprise.crediter(montant)
            
            Notification.objects.create(
                utilisateur=request.user,
                type_notification="validation",
                titre="✅ Amende payée en ligne",
                message=f"Paiement de {montant} DH effectué en ligne."
            )
            
            _check_blacklist(request.user)
            _log(request.user, "paiement", f"Paiement en ligne de {montant} DH - {emprunt.livre.titre}", request)
            messages.success(request, f"✅ Amende de {montant} DH payée en ligne !")
            return redirect("borrowings:mes_amendes")
        else:
            messages.error(request, "Solde insuffisant sur le compte bancaire fictif.")
            return redirect("borrowings:payer_amende_en_ligne", pk=pk)
    
    return render(request, "borrowings/paiement_en_ligne.html", {"emprunt": emprunt})
@login_required
def payer_amende_manuel(request, pk):
    """Demande de paiement manuel (l'utilisateur fait la demande)"""
    emprunt = get_object_or_404(Emprunt, pk=pk, utilisateur=request.user)
    
    if emprunt.statut != "retourne":
        messages.error(request, "❌ Vous devez d'abord retourner le livre avant de payer l'amende.")
        return redirect("borrowings:emprunt_list")
    
    if emprunt.est_payee:
        messages.info(request, "Cette amende est déjà payée.")
        return redirect("borrowings:emprunt_list")
    
    if emprunt.amende_totale <= 0:
        messages.info(request, "Aucune amende à payer.")
        return redirect("borrowings:emprunt_list")
    
    if request.method == "POST":
        montant = float(emprunt.amende_totale)
        
        # ✅ Appliquer réduction si 100+ points
        if request.user.points_fidelite >= 100 and request.user.status != "bibliothecaire" and not request.user.is_staff:
            montant = round(montant * 0.5, 2)
            request.user.points_fidelite -= 100
            request.user.save()
            messages.info(request, f"Réduction 50% appliquée ! Montant : {montant} DH")
        
        # ✅ NE PAS marquer comme payé immédiatement
        # On crée juste une demande de paiement manuel
        emprunt.demande_paiement_manuel = True
        emprunt.amende_totale = montant
        emprunt.save()
        
        # ✅ Notification aux bibliothécaires
        bibliothecaires = User.objects.filter(status="bibliothecaire")
        for biblio in bibliothecaires:
            Notification.objects.create(
                utilisateur=biblio,
                type_notification="paiement_manuel",
                titre="💰 Nouvelle demande de paiement manuel",
                message=f"{request.user.first_name} {request.user.last_name} a demandé le paiement de {montant} DH pour le livre '{emprunt.livre.titre}'."
            )
        
        messages.success(request, "✅ Demande envoyée ! Le bibliothécaire va valider votre paiement.")
        return redirect('borrowings:mes_amendes')
    
    date_limite = timezone.now().date() + timedelta(days=7)
    return render(request, "borrowings/paiement_manuel.html", {
        "emprunt": emprunt,
        "date_limite": date_limite
    })

@login_required
def payer_toutes_amendes(request):
    """Paiement groupé - redirige vers le choix du mode de paiement"""
    emprunts_impayes = Emprunt.objects.filter(
        utilisateur=request.user,
        est_payee=False,
        amende_totale__gt=0,
        statut="retourne"
    )
    
    if not emprunts_impayes.exists():
        messages.info(request, "Aucune amende à payer (les livres doivent d'abord être retournés).")
        return redirect("borrowings:mes_amendes")
    
    total_initial = sum(e.amende_totale for e in emprunts_impayes)
    
    if request.user.points_fidelite >= 100 and request.user.status != "bibliothecaire":
        total_a_payer = round(total_initial * 0.5, 2)
        request.user.points_fidelite -= 100
        request.user.save()
        messages.info(request, f"🎉 Réduction 50% appliquée ! Total : {total_a_payer} DH")
    else:
        total_a_payer = total_initial
    
    request.session['amendes_a_payer'] = [e.id for e in emprunts_impayes]
    return redirect("borrowings:payer_groupes_amendes")

@login_required
def payer_groupes_amendes(request):
    """Paiement groupé - formulaire de paiement en ligne"""
    emprunt_ids = request.session.get('amendes_a_payer', [])
    
    if not emprunt_ids:
        messages.error(request, "Aucune amende sélectionnée.")
        return redirect("borrowings:mes_amendes")
    
    emprunts = Emprunt.objects.filter(
        id__in=emprunt_ids, 
        utilisateur=request.user, 
        est_payee=False,
        statut="retourne"
    )
    
    if not emprunts.exists():
        messages.info(request, "Ces amendes ont déjà été payées ou les livres ne sont pas retournés.")
        return redirect("borrowings:mes_amendes")
    
    total = sum(e.amende_totale for e in emprunts)
    
    if request.method == "POST":
        numero = request.POST.get("numero_carte")
        expiration = request.POST.get("expiration")
        cvv = request.POST.get("cvv")
        
        compte, created = CompteBancaire.objects.get_or_create(
            
            utilisateur=request.user,
            defaults={
                "solde": 500,
                "numero_carte": numero,
                "date_expiration": expiration,
                "cryptogramme": cvv
            }
        )
        compte.refresh_from_db() 
        if compte.debiter(total):
            for emprunt in emprunts:
                emprunt.est_payee = True
                emprunt.save()
            
            compte_entreprise, created = CompteEntreprise.objects.get_or_create(
                id=1,
                defaults={'solde': 0, 'nom': 'BiblIntel - Compte principal'}
            )
            compte_entreprise.crediter(total)
            
            _check_blacklist(request.user)
            
            Notification.objects.create(
                utilisateur=request.user,
                type_notification="validation",
                titre="✅ Paiement groupé effectué",
                message=f"Vous avez payé {emprunts.count()} amende(s) pour un total de {total} DH."
            )
            
            messages.success(request, f"✅ {emprunts.count()} amende(s) payée(s) pour un total de {total} DH.")
            del request.session['amendes_a_payer']
            return redirect('borrowings:mes_amendes')
        else:
            messages.error(request, f"Solde insuffisant. Votre solde est de {compte.solde} DH.")
    
    return render(request, 'borrowings/paiement_groupes.html', {
        'emprunts': emprunts,
        'total': total,
    })

@login_required
def payer_amende(request, pk):
    """Paiement simple d'une amende (avec ou sans réduction)"""
    emprunt = get_object_or_404(Emprunt, pk=pk, utilisateur=request.user)
    
    if not emprunt.amende_totale or emprunt.amende_totale <= 0:
        messages.info(request, "Aucune amende à payer.")
        return redirect("borrowings:emprunt_list")
    
    if emprunt.est_payee:
        messages.info(request, "Cette amende est déjà payée.")
        return redirect("borrowings:emprunt_list")

    montant = float(emprunt.amende_totale)
    reduction_appliquee = False

    if request.user.points_fidelite >= 100:
        montant = round(montant * 0.5, 2)
        request.user.points_fidelite -= 100
        request.user.save()
        reduction_appliquee = True
        messages.info(request, f"Réduction 50% appliquée ! Montant : {montant} DH")

    emprunt.amende_totale = montant
    emprunt.est_payee = True
    emprunt.save()

    _check_blacklist(request.user)

    detail = " (réduction 50% fidélité)" if reduction_appliquee else ""
    _notif(request.user, "validation", "✅ Amende payée", f'Paiement de {montant} DH{detail} validé.')
    _log(request.user, "paiement", f'Paiement amende {montant} DH{detail} - "{emprunt.livre.titre}"', request)
    messages.success(request, f"✅ Amende de {montant} DH payée.")
    return redirect("borrowings:emprunt_list")
@login_required
def payer_toutes_amendes_manuel(request):
    """Paiement groupé MANUEL - demande de validation"""
    
    emprunts = Emprunt.objects.filter(
        utilisateur=request.user,
        est_payee=False,
        amende_totale__gt=0,
        statut="retourne"
    )
    
    if not emprunts.exists():
        messages.info(request, "Aucune amende à payer.")
        return redirect("borrowings:mes_amendes")
    
    total_initial = sum(e.amende_totale for e in emprunts)
    
    # Appliquer réduction si 100+ points
    if request.user.points_fidelite >= 100 and request.user.status != "bibliothecaire":
        total_a_payer = round(total_initial * 0.5, 2)
        request.user.points_fidelite -= 100
        request.user.save()
        montant = total_a_payer
        messages.info(request, f"🎉 Réduction 50% appliquée ! Total : {total_a_payer} DH")
    else:
        montant = total_initial
    
    # ✅ NE PAS marquer comme payé immédiatement
    # On crée juste une demande de paiement manuel pour chaque emprunt
    for emprunt in emprunts:
        emprunt.demande_paiement_manuel = True
        emprunt.amende_totale = montant if len(emprunts) == 1 else emprunt.amende_totale
        emprunt.save()
    
    # ✅ Notification aux bibliothécaires
    bibliothecaires = User.objects.filter(status="bibliothecaire")
    for biblio in bibliothecaires:
        Notification.objects.create(
            utilisateur=biblio,
            type_notification="paiement_manuel",
            titre="💰 Paiement groupé manuel",
            message=f"{request.user.first_name} {request.user.last_name} a demandé le paiement de {montant} DH pour {emprunts.count()} amende(s)."
        )
    
    messages.success(request, f"✅ Demande envoyée pour {emprunts.count()} amende(s) ! Le bibliothécaire va valider.")
    return redirect('borrowings:mes_amendes')
@login_required
def payer_toutes_amendes_en_ligne(request):
    """Paiement groupé EN LIGNE (carte bancaire) de toutes les amendes des livres retournés"""
    
    emprunts = Emprunt.objects.filter(
        utilisateur=request.user,
        est_payee=False,
        amende_totale__gt=0,
        statut="retourne"
    )
    
    if not emprunts.exists():
        messages.info(request, "Aucune amende à payer.")
        return redirect("borrowings:mes_amendes")
    
    total_initial = sum(e.amende_totale for e in emprunts)
    
    # Appliquer réduction si 100+ points
    if request.user.points_fidelite >= 100 and request.user.status != "bibliothecaire":
        total_a_payer = round(total_initial * 0.5, 2)
        request.user.points_fidelite -= 100
        request.user.save()
        montant = total_a_payer
        messages.info(request, f"🎉 Réduction 50% appliquée ! Total : {total_a_payer} DH")
    else:
        montant = total_initial
    
    if request.method == "POST":
        numero = request.POST.get("numero_carte")
        expiration = request.POST.get("expiration")
        cvv = request.POST.get("cvv")
        
        compte, created = CompteBancaire.objects.get_or_create(
            utilisateur=request.user,
            defaults={
                "solde": 500,
                "numero_carte": numero,
                "date_expiration": expiration,
                "cryptogramme": cvv
            }
        )
        compte.refresh_from_db()  
        if compte.debiter(montant):
            for emprunt in emprunts:
                emprunt.est_payee = True
                emprunt.save()
            
            compte_entreprise, created = CompteEntreprise.objects.get_or_create(
                id=1,
                defaults={'solde': 0, 'nom': 'BiblIntel - Compte principal'}
            )
            compte_entreprise.crediter(montant)
            
            Notification.objects.create(
                utilisateur=request.user,
                type_notification="validation",
                titre="✅ Paiement groupé effectué",
                message=f"Vous avez payé {emprunts.count()} amende(s) pour un total de {montant} DH."
            )
            
            _check_blacklist(request.user)
            messages.success(request, f"✅ {emprunts.count()} amende(s) payée(s) pour un total de {montant} DH.")
            return redirect('borrowings:mes_amendes')
        else:
            messages.error(request, f"Solde insuffisant. Votre solde est de {compte.solde} DH.")
    
    return render(request, "borrowings/paiement_groupes_en_ligne.html", {
        "emprunts": emprunts,
        "total": montant,
    })
@login_required
def amende_list(request):
    """Liste des amendes pour admin et bibliothécaire"""
    if not (request.user.is_staff or request.user.status == "bibliothecaire"):
        return redirect('users:home')
    
    emprunts = Emprunt.objects.filter(amende_totale__gt=0).select_related('utilisateur', 'livre')
    
    if request.user.status == "bibliothecaire" and not request.user.is_staff:
        livres_biblio = Livre.objects.filter(bibliothecaire=request.user)
        emprunts = emprunts.filter(livre__in=livres_biblio)
    
    statut = request.GET.get('statut', '')
    montant_min = request.GET.get('montant_min', '')
    montant_max = request.GET.get('montant_max', '')
    utilisateur = request.GET.get('utilisateur', '')
    
    if statut == 'impayee':
        emprunts = emprunts.filter(est_payee=False)
    elif statut == 'payee':
        emprunts = emprunts.filter(est_payee=True)
    
    if montant_min:
        emprunts = emprunts.filter(amende_totale__gte=montant_min)
    if montant_max:
        emprunts = emprunts.filter(amende_totale__lte=montant_max)
    if utilisateur:
        emprunts = emprunts.filter(utilisateur__username__icontains=utilisateur)
    
    total_amendes = sum(e.amende_totale for e in emprunts if not e.est_payee)
    est_bibliothecaire = request.user.status == "bibliothecaire" and not request.user.is_staff
    
    return render(request, 'borrowings/amende_list.html', {
        'emprunts': emprunts.order_by('-amende_totale'),
        'total_amendes': total_amendes,
        'est_bibliothecaire': est_bibliothecaire,
    })

@login_required
def bibliothecaire_valider_paiement(request, pk):
    """Validation d'un paiement par le bibliothécaire (après réception des espèces)"""
    if not (request.user.is_staff or request.user.status == "bibliothecaire"):
        messages.error(request, "Accès réservé aux bibliothécaires.")
        return redirect("users:home")
    
    emprunt = get_object_or_404(Emprunt, pk=pk, est_payee=False, amende_totale__gt=0)
    
    if request.user.status == "bibliothecaire" and not request.user.is_staff:
        if emprunt.livre.bibliothecaire != request.user:
            messages.error(request, "Vous ne pouvez pas valider cette amende (livre non ajouté par vous).")
            return redirect("borrowings:amende_list")
    
    if request.method == "POST":
        montant = float(emprunt.amende_totale)
        
        compte_entreprise, created = CompteEntreprise.objects.get_or_create(
            id=1,
            defaults={'solde': 0, 'nom': 'BiblIntel - Compte principal'}
        )
        compte_entreprise.crediter(montant)
        
        emprunt.est_payee = True
        emprunt.save()
        
        Notification.objects.create(
            utilisateur=emprunt.utilisateur,
            type_notification="validation",
            titre="✅ Amende payée",
            message=f"Votre amende de {montant} DH pour '{emprunt.livre.titre}' a été payée et validée par {request.user.first_name}."
        )
        
        _log(request.user, "paiement", f"Validation paiement {montant} DH - {emprunt.livre.titre}", request)
        _check_blacklist(emprunt.utilisateur)
        
        messages.success(request, f"✅ Paiement de {montant} DH validé pour {emprunt.utilisateur.first_name}.")
        return redirect("borrowings:amende_list")
    
    return render(request, 'borrowings/valider_paiement.html', {'emprunt': emprunt})


# ==================== EMPRUNTS ET RÉSERVATIONS ====================

@login_required
def emprunt_list(request):
    """Liste des emprunts"""
    est_bibliothecaire = request.user.status == "bibliothecaire"

    if request.user.is_staff or est_bibliothecaire:
        emprunts = Emprunt.objects.exclude(utilisateur__is_staff=True).select_related('utilisateur', 'livre')
    else:
        emprunts = Emprunt.objects.filter(utilisateur=request.user).select_related('livre')

    statut_filtre = request.GET.get('statut', '')
    if statut_filtre == 'en_cours':
        emprunts = emprunts.filter(statut='en_cours')
    elif statut_filtre == 'retard':
        emprunts = emprunts.filter(statut='retard')

    emprunts = emprunts.order_by('-date_demande')

    return render(request, 'borrowings/emprunt_list.html', {
        'emprunts': emprunts,
        'statut_actuel': statut_filtre,
        'est_admin': request.user.is_staff,
        'est_bibliothecaire': est_bibliothecaire,
    })

@login_required
def emprunt_create(request, livre_id):
    """Créer un emprunt"""
    livre = get_object_or_404(Livre, pk=livre_id)

    if request.user.is_staff or request.user.status == "admin":
        messages.error(request, "Les administrateurs ne peuvent pas emprunter.")
        return redirect("books:livre_detail", pk=livre_id)

    if request.user.status == "bibliothecaire":
        messages.error(request, "Les bibliothécaires ne peuvent pas emprunter.")
        return redirect("books:livre_detail", pk=livre_id)
    request.user.refresh_from_db()
    if request.user.est_blackliste:
        messages.error(request, f"❌ Vous êtes blacklisté. Raison : {request.user.raison_blacklist or 'Non spécifiée'}")
        return redirect("books:livre_detail", pk=livre_id)
    deja_emprunte = Emprunt.objects.filter(
        utilisateur=request.user,
        livre=livre,
        statut__in=["en_cours", "retard"]
        ).exists()

    if deja_emprunte:
        messages.error(request, f"❌ Vous avez déjà emprunté le livre '{livre.titre}'. Un même livre ne peut être emprunté qu'une seule fois.")
        return redirect("books:livre_detail", pk=livre_id)

    ok, err = _verifier_eligibilite_emprunt(request.user, livre, request)
    if not ok:
        messages.error(request, err)
        return redirect("books:livre_detail", pk=livre_id)

    actifs = Emprunt.objects.filter(livre=livre, statut__in=["en_cours", "approuve"]).count()

    if actifs >= livre.max_emprunts_simultanes or Reservation.objects.filter(livre=livre, est_active=True).exists():
        position = Emprunt.objects.filter(livre=livre, statut="en_attente").count() + 1
        Emprunt.objects.create(
            utilisateur=request.user, livre=livre, statut="en_attente",
            position_file=position, date_demande=timezone.now(),
        )
        messages.warning(request, f"File FIFO - position {position}")
        return redirect("borrowings:emprunt_list")

    Emprunt.objects.create(
        utilisateur=request.user, livre=livre, statut="en_cours",
        date_approbation=timezone.now(), date_debut=timezone.now(),
        date_retour_prevue=(timezone.now() + timedelta(days=30)).date(),
    )

    livre.nombre_emprunts += 1
    nouveaux_actifs = Emprunt.objects.filter(livre=livre, statut__in=["en_cours", "approuve"]).count()
    livre.statut = "emprunte" if nouveaux_actifs >= livre.max_emprunts_simultanes else "disponible"
    livre.save()

    if livre.bibliothecaire:
        livre.gain_salaire_emprunts += 5
        total_gains = sum(
            l.gain_salaire_base + l.gain_salaire_bonus_note + l.gain_salaire_emprunts
            for l in Livre.objects.filter(bibliothecaire=livre.bibliothecaire)
        )
        livre.bibliothecaire.salaire_total = total_gains
        livre.bibliothecaire.save()
        livre.save()

    _notif(request.user, "validation", "Emprunt approuvé", f'Emprunt de "{livre.titre}" approuvé.')
    _log(request.user, "emprunt", f'Emprunt : "{livre.titre}"', request)
    messages.success(request, "Emprunt effectué.")
    return redirect("borrowings:emprunt_list")

@login_required
def emprunt_prioritaire(request, livre_id):
    """Emprunt prioritaire (utilise 50 points)"""
    livre = get_object_or_404(Livre, pk=livre_id)
    
    if request.user.is_staff or request.user.status == "admin":
        messages.error(request, "Les administrateurs ne peuvent pas emprunter.")
        return redirect("books:livre_detail", pk=livre_id)

    if request.user.points_fidelite < 50:
        messages.error(request, f"Il faut 50 points (vous en avez {request.user.points_fidelite}).")
        return redirect("books:livre_detail", pk=livre_id)

    ok, err = _verifier_eligibilite_emprunt(request.user, livre, request)
    if not ok:
        messages.error(request, err)
        return redirect("books:livre_detail", pk=livre_id)

    if livre.statut != "disponible":
        messages.warning(request, "Ce livre n'est pas disponible.")
        return redirect("books:livre_detail", pk=livre_id)

    if request.method == "POST":
        date_retour_str = request.POST.get("date_retour")
        try:
            date_retour = date.fromisoformat(date_retour_str)
        except (ValueError, TypeError):
            messages.error(request, "Date invalide.")
            return render(request, "borrowings/emprunt_prioritaire.html", {"livre": livre})

        today = timezone.now().date()
        if date_retour <= today or date_retour > today + timedelta(days=60):
            messages.error(request, "Date invalide (entre 1 et 60 jours).")
            return render(request, "borrowings/emprunt_prioritaire.html", {"livre": livre})

        Emprunt.objects.create(
            utilisateur=request.user, livre=livre, statut="en_cours",
            date_approbation=timezone.now(), date_debut=timezone.now(),
            date_retour_prevue=date_retour,
        )
        livre.statut = "emprunte"
        livre.nombre_emprunts += 1
        livre.save()

        request.user.points_fidelite -= 50
        request.user.save()

        _notif(request.user, "validation", "Emprunt prioritaire accordé", f'Retour choisi : {date_retour}.')
        _log(request.user, "emprunt", f'Emprunt prioritaire (50 pts) : "{livre.titre}"', request)
        messages.success(request, f"Emprunt prioritaire accordé ! Retour : {date_retour}")
        return redirect("borrowings:emprunt_list")

    return render(request, "borrowings/emprunt_prioritaire.html", {
        "livre": livre,
        "points": request.user.points_fidelite,
        "date_min": (timezone.now() + timedelta(days=1)).date().isoformat(),
        "date_max": (timezone.now() + timedelta(days=60)).date().isoformat(),
    })

@login_required
def emprunt_retour(request, pk):
    """Retourner un livre"""
    emprunt = get_object_or_404(Emprunt, pk=pk, utilisateur=request.user)
    
    if emprunt.statut not in ["en_cours", "retard"]:
        messages.error(request, "Retour impossible.")
        return redirect("borrowings:emprunt_list")

    emprunt.date_retour_effective = timezone.now()
    retard = emprunt.calculer_retard()

    if retard > 0:
        emprunt.statut = "retourne"
        emprunt.amende_totale = retard * 10
        _notif(request.user, "validation", "⚠️ Retour avec retard", f'Amende : {emprunt.amende_totale} DH. Veuillez payer dans les plus brefs délais.')
    else:
        emprunt.statut = "retourne"
        pts, raison = _attribuer_points(request.user, emprunt)
        _notif(request.user, "validation", f"✅ Retour validé - +{pts} points", f"{raison}")

    emprunt.save()
    livre = emprunt.livre
    
    reservation = Reservation.objects.filter(livre=livre, est_active=True).order_by("date_reservation").first()

    if reservation:
        livre.statut = "reserve"
        reservation.notification_envoyee = True
        reservation.save()
        _notif(reservation.utilisateur, "disponible", "📚 Livre disponible !", f'Le livre "{livre.titre}" que vous avez réservé est maintenant disponible.')
    else:
        livre.statut = "disponible"

    livre.save()
    _log(request.user, "retour", f'Retour : "{livre.titre}"', request)
    _check_blacklist(request.user)
    messages.success(request, "Livre retourné avec succès.")
    return redirect("borrowings:emprunt_list")

@login_required
def emprunt_prolonger(request, pk):
    """Prolonger un emprunt (enseignant uniquement)"""
    emprunt = get_object_or_404(Emprunt, pk=pk, utilisateur=request.user)
    
    est_enseignant = request.user.status == "enseignant"
    
    if not est_enseignant:
        messages.error(request, "❌ Seuls les enseignants peuvent prolonger un emprunt.")
        return redirect("borrowings:emprunt_list")
    
    if emprunt.nombre_prolongations >= 1:
        messages.error(request, "❌ Vous avez déjà prolongé cet emprunt (une seule fois maximum).")
        return redirect("borrowings:emprunt_list")
    
    if emprunt.calculer_retard() > 0:
        messages.error(request, "❌ Impossible de prolonger un emprunt en retard.")
        return redirect("borrowings:emprunt_list")
    
    emprunt.date_retour_prevue += timedelta(days=7)
    emprunt.nombre_prolongations += 1
    emprunt.a_prolonge = True
    emprunt.save()
    
    _notif(request.user, "validation", "Prolongation accordée", 
           f'Nouvelle date de retour : {emprunt.date_retour_prevue}.')
    _log(request.user, "emprunt", f'Prolongation (enseignant) : "{emprunt.livre.titre}" +7j', request)
    
    messages.success(request, f"✅ Prolongation accordée ! Nouvelle date de retour : {emprunt.date_retour_prevue}")
    return redirect("borrowings:emprunt_list")

@login_required
def reservation_create(request, livre_id):
    """Créer une réservation"""
    livre = get_object_or_404(Livre, pk=livre_id)
    
    if request.user.is_staff or request.user.status == "admin":
        messages.error(request, "Les administrateurs ne peuvent pas réserver.")
        return redirect("books:livre_detail", pk=livre_id)

    if request.user.status == "bibliothecaire":
        messages.error(request, "Les bibliothécaires ne peuvent pas réserver.")
        return redirect("books:livre_detail", pk=livre_id)

    _check_blacklist(request.user)
    if request.user.est_blackliste:
        messages.error(request, "Vous êtes blacklisté.")
        return redirect("books:livre_detail", pk=livre_id)

    if livre.statut == "disponible":
        messages.info(request, "Ce livre est disponible, empruntez-le directement.")
        return redirect("books:livre_detail", pk=livre_id)

    if Reservation.objects.filter(utilisateur=request.user, livre=livre, est_active=True).exists():
        messages.warning(request, "Vous avez déjà réservé ce livre.")
        return redirect("books:livre_detail", pk=livre_id)

    position = Reservation.objects.filter(livre=livre, est_active=True).count() + 1
    Reservation.objects.create(utilisateur=request.user, livre=livre, position_file=position)

    _notif(request.user, "validation", "Réservation effectuée", f'Position dans la file : {position}.')
    _log(request.user, "reservation", f'Réservation : "{livre.titre}" - position {position}', request)
    messages.success(request, f"Réservation effectuée. Position : {position}")
    return redirect("books:livre_detail", pk=livre_id)

@login_required
def reservation_cancel(request, pk):
    """Annuler une réservation"""
    reservation = get_object_or_404(Reservation, pk=pk, utilisateur=request.user)
    livre_titre = reservation.livre.titre
    reservation.est_active = False
    reservation.save()

    remaining = Reservation.objects.filter(livre=reservation.livre, est_active=True).order_by("date_reservation")
    for i, res in enumerate(remaining, 1):
        res.position_file = i
        res.save()

    _log(request.user, "reservation", f'Annulation réservation : "{livre_titre}"', request)
    messages.success(request, "Réservation annulée.")
    return redirect("borrowings:mes_reservations")

@login_required
def mes_reservations(request):
    """Mes réservations"""
    if request.user.is_staff or request.user.status == "admin":
        messages.error(request, "Les administrateurs n'ont pas de réservations.")
        return redirect("dashboard:admin_dashboard")
    reservations = Reservation.objects.filter(utilisateur=request.user, est_active=True).order_by("date_reservation")
    return render(request, "borrowings/reservation_list.html", {"reservations": reservations})