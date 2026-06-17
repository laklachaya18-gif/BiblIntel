from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Notification
from borrowings.models import Emprunt


@login_required
def notification_list(request):
    is_admin = request.user.is_staff or request.user.status == "admin"

    if is_admin:
        all_notifications = (
            Notification.objects.exclude(utilisateur=request.user)
            .select_related("utilisateur")
            .order_by("-date_creation")
        )

        all_emprunts = Emprunt.objects.select_related("utilisateur", "livre").order_by(
            "-date_demande"
        )

        return render(
            request,
            "notifications/notification_list_admin.html",
            {
                "notifications": all_notifications,
                "emprunts": all_emprunts,
            },
        )
    else:
        notifications = Notification.objects.filter(utilisateur=request.user)
        non_lues = notifications.filter(lu=False)
        non_lues_count = non_lues.count()

        # Marquer comme lues
        non_lues.update(lu=True)

        return render(
            request,
            "notifications/notification_list.html",
            {
                "notifications": notifications,
                "non_lues_count": non_lues_count,
            },
        )


@login_required
@require_POST
def mark_all_read(request):
    """Marque toutes les notifications de l'utilisateur comme lues."""
    Notification.objects.filter(utilisateur=request.user, lu=False).update(lu=True)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True})
    return redirect("notifications:notification_list")


@login_required
def unread_count(request):
    """Retourne le nombre de notifications non lues (pour la navbar)."""
    count = Notification.objects.filter(utilisateur=request.user, lu=False).count()
    return JsonResponse({"count": count})
