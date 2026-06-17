"""
F7 — Système de notifications automatiques.

Lancer via : python manage.py envoyer_notifications
Planifier avec cron ou Windows Task Scheduler (toutes les heures ou tous les jours).

Exemple crontab Linux (exécution quotidienne à 8h) :
  0 8 * * * /chemin/vers/venv/bin/python /chemin/vers/BiblIntel/manage.py envoyer_notifications

Exemple Windows Task Scheduler :
  Action : python manage.py envoyer_notifications
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from borrowings.models import Emprunt
from notifications.models import Notification
from logs.models import LogAction
import logging

# Logger pour les logs système (pas d'affichage dans l'interface)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Envoie les notifications automatiques : rappels de retour, retards, amendes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Exécuter en mode silencieux (sans écriture dans LogAction)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Afficher les détails dans la console',
        )

    def handle(self, *args, **options):
        aujourd_hui = timezone.now().date()
        dans_2_jours = aujourd_hui + timedelta(days=2)
        mode_quiet = options['quiet']
        mode_verbose = options['verbose']

        nb_rappels = 0
        nb_retards = 0
        nb_amendes = 0
        nb_rappels_paiement = 0  # ✅ NOUVEAU : compteur pour paiement manuel

        # ─── 1. Rappel retour dans 2 jours ───────────────────────────────────
        emprunts_proches = Emprunt.objects.filter(
            statut="en_cours",
            date_retour_prevue=dans_2_jours,
        ).select_related("utilisateur", "livre")

        for emprunt in emprunts_proches:
            # Éviter les doublons : ne pas renvoyer si déjà notifié aujourd'hui
            deja_notifie = Notification.objects.filter(
                utilisateur=emprunt.utilisateur,
                type_notification="retour_proche",
                titre__icontains=emprunt.livre.titre,
                date_creation__date=aujourd_hui,
            ).exists()
            if not deja_notifie:
                Notification.objects.create(
                    utilisateur=emprunt.utilisateur,
                    type_notification="retour_proche",
                    titre="Rappel : retour dans 2 jours",
                    message=(
                        f'Le livre "{emprunt.livre.titre}" doit être retourné le '
                        f"{emprunt.date_retour_prevue}. Pensez à le retourner ou à le prolonger."
                    ),
                )
                nb_rappels += 1

        # ─── 2. Notification retard (1er jour et chaque jour suivant) ────────
        emprunts_en_retard = Emprunt.objects.filter(
            statut__in=["en_cours", "retard"],
            date_retour_prevue__lt=aujourd_hui,
        ).select_related("utilisateur", "livre")

        for emprunt in emprunts_en_retard:
            jours_retard = (aujourd_hui - emprunt.date_retour_prevue).days
            amende = jours_retard * 10

            # Mettre à jour statut et amende
            emprunt.statut = "retard"
            emprunt.amende_totale = amende
            emprunt.save()

            # Notifier chaque jour
            deja_notifie_aujourd_hui = Notification.objects.filter(
                utilisateur=emprunt.utilisateur,
                type_notification="retard",
                titre__icontains=emprunt.livre.titre,
                date_creation__date=aujourd_hui,
            ).exists()

            if not deja_notifie_aujourd_hui:
                Notification.objects.create(
                    utilisateur=emprunt.utilisateur,
                    type_notification="retard",
                    titre=f"Retard de {jours_retard} jour(s) !",
                    message=(
                        f'Le livre "{emprunt.livre.titre}" aurait dû être retourné le '
                        f"{emprunt.date_retour_prevue}. "
                        f"Retard : {jours_retard} jour(s). "
                        f"Amende actuelle : {amende} DH. Retournez-le dès que possible."
                    ),
                )
                nb_retards += 1

        # ─── 3. Alerte amendes impayées (> 100 DH) ───────────────────────────
        from users.models import User

        utilisateurs_avec_amendes = User.objects.filter(
            emprunts__est_payee=False,
            emprunts__amende_totale__gt=0,
        ).distinct()

        for user in utilisateurs_avec_amendes:
            total = sum(
                e.amende_totale
                for e in Emprunt.objects.filter(utilisateur=user, est_payee=False)
                if e.amende_totale
            )
            if total > 100:
                deja_notifie = Notification.objects.filter(
                    utilisateur=user,
                    type_notification="blacklist",
                    titre__icontains="amende",
                    date_creation__date=aujourd_hui,
                ).exists()
                if not deja_notifie:
                    Notification.objects.create(
                        utilisateur=user,
                        type_notification="blacklist",
                        titre="Amendes impayées dépassant 100 DH",
                        message=(
                            f"Vos amendes impayées s'élèvent à {total} DH. "
                            f"Réglez-les pour débloquer votre compte."
                        ),
                    )
                    nb_amendes += 1

        # ─── 4. ✅ NOUVEAU : Rappel paiement manuel (délai 7 jours) ──────────
        date_limite = aujourd_hui - timedelta(days=7)
        
        # Récupérer les emprunts avec paiement manuel non confirmé
        emprunts_paiement_manuel = Emprunt.objects.filter(
            est_payee=False,
            amende_totale__gt=0,
            date_retour_effective__isnull=False,
            date_retour_effective__lte=date_limite,
        ).select_related("utilisateur", "livre")

        for emprunt in emprunts_paiement_manuel:
            deja_notifie = Notification.objects.filter(
                utilisateur=emprunt.utilisateur,
                type_notification="paiement_manuel",
                date_creation__date=aujourd_hui,
            ).exists()
            
            if not deja_notifie:
                Notification.objects.create(
                    utilisateur=emprunt.utilisateur,
                    type_notification="paiement_manuel",
                    titre="⚠️ Paiement d'amende en attente",
                    message=(
                        f"Vous avez une amende de {emprunt.amende_totale} DH pour le livre "
                        f"'{emprunt.livre.titre}' qui n'a pas été payée depuis plus de 7 jours. "
                        f"Veuillez vous rendre à la bibliothèque pour régulariser votre situation."
                    ),
                )
                nb_rappels_paiement += 1

        # ─── Log de la commande ─────────────────────────────────────────────
        if not mode_quiet:
            LogAction.objects.create(
                utilisateur=None,
                type_action="cron",
                description=(
                    f"CRON - Notifications auto : {nb_rappels} rappels retour, "
                    f"{nb_retards} alertes retard, {nb_amendes} alertes amendes, "
                    f"{nb_rappels_paiement} rappels paiement manuel"
                ),
            )

        # Affichage dans la console
        if mode_verbose:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Notifications envoyées : "
                    f"{nb_rappels} rappels, {nb_retards} retards, "
                    f"{nb_amendes} amendes, {nb_rappels_paiement} rappels paiement"
                )
            )
        elif not mode_quiet:
            self.stdout.write(
                f"[CRON] Rappels: {nb_rappels} | Retards: {nb_retards} | "
                f"Amendes: {nb_amendes} | Paiement: {nb_rappels_paiement}"
            )