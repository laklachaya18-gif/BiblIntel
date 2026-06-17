import csv
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from .models import LogAction


@login_required
def log_list(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("users:home")
    
    # ✅ CORRECTION : Utiliser 'date_action' au lieu de 'date_creation'
    logs = LogAction.objects.exclude(type_action='cron').select_related("utilisateur").order_by('-date_action')

    # Filtres
    type_action = request.GET.get("type", "").strip()
    date_debut = request.GET.get("date_debut", "").strip()
    date_fin = request.GET.get("date_fin", "").strip()
    utilisateur = request.GET.get("utilisateur", "").strip()

    if type_action:
        logs = logs.filter(type_action=type_action)
    if date_debut:
        logs = logs.filter(date_action__date__gte=date_debut)
    if date_fin:
        logs = logs.filter(date_action__date__lte=date_fin)
    if utilisateur:
        logs = logs.filter(utilisateur__username__icontains=utilisateur)

    # Export CSV (F16)
    if request.GET.get("export") == "csv":
        return _export_csv(logs)

    type_choices = LogAction.TYPE_CHOICES
    return render(
        request,
        "logs/log_list.html",
        {
            "logs": logs,
            "type_choices": type_choices,
            "filters": {
                "type": type_action,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "utilisateur": utilisateur,
            },
        },
    )


def _export_csv(logs):
    """Exporte les logs filtrés en CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"logs_biblintel_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    # BOM pour Excel (UTF-8)
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        ["Date", "Utilisateur", "Type d'action", "Description", "Adresse IP"]
    )

    for log in logs:
        writer.writerow(
            [
                log.date_action.strftime("%d/%m/%Y %H:%M:%S"),
                log.utilisateur.username if log.utilisateur else "(supprimé)",
                log.get_type_action_display(),
                log.description,
                log.ip_adresse or "",
            ]
        )

    return response