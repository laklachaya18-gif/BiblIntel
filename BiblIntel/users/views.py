from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import User, CategoryPreference
from .forms import UserRegisterForm, UserProfileForm, UserLoginForm

from books.models import Livre
from borrowings.models import Emprunt
from logs.models import LogAction


# =========================
# LOG FUNCTION
# =========================
def _log(user, type_action, description, request=None):
    ip = None
    if request:
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = (
            x_forwarded.split(",")[0]
            if x_forwarded
            else request.META.get("REMOTE_ADDR")
        )

    LogAction.objects.create(
        utilisateur=user,
        type_action=type_action,
        description=description,
        ip_adresse=ip,
    )


# =========================
# HOME
# =========================

def home(request):
    # ===== LIVRES =====
    tous_les_livres = Livre.objects.all()
    total_livres = tous_les_livres.count()

    livres_disponibles = Livre.objects.filter(statut="disponible").order_by("-date_ajout")[:6]

    livres_populaires = Livre.objects.order_by("-nombre_emprunts")[:5]

    # ===== USERS =====
    total_utilisateurs = User.objects.filter(is_staff=False).count()

    utilisateurs_actifs = User.objects.filter(is_staff=False).order_by("-derniere_connexion")[:5]

    classement_fidelite = User.objects.filter(is_staff=False).order_by("-points_fidelite")[:5]

    # ===== EMPRUNTS =====
    emprunts_en_cours = Emprunt.objects.filter(statut__in=["en_cours", "approuve"]).count()

    emprunts_retard = Emprunt.objects.filter(statut="retard", est_payee=False)

    derniers_emprunts = Emprunt.objects.select_related("utilisateur", "livre").order_by("-date_demande")[:10]

    total_amendes = sum(e.amende_totale for e in emprunts_retard)

    # ===== CONTEXT =====
    context = {
        "livres": livres_disponibles,
        "total_livres": total_livres,
        "total_utilisateurs": total_utilisateurs,
        "emprunts_en_cours": emprunts_en_cours,
        "livres_populaires": livres_populaires,
        "utilisateurs_actifs": utilisateurs_actifs,
        "classement_fidelite": classement_fidelite,
        "emprunts_retard": emprunts_retard,
        "derniers_emprunts": derniers_emprunts,
        "total_amendes": total_amendes,
    }

    # ===== ADMIN STATS =====
    if request.user.is_staff:
        context["retards"] = Emprunt.objects.filter(statut="retard").count()
        context["blacklistes"] = User.objects.filter(est_blackliste=True).count()

    return render(request, "users/home.html", context)
# =========================
# REGISTER
# =========================
def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST, request.FILES)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password1"])
            user.save()

            # catégories préférées
            categories = form.cleaned_data.get("categories_preferees")
            if categories:
                for cat in categories:
                    CategoryPreference.objects.create(
                        user=user,
                        category=cat
                    )

            login(request, user)

            _log(user, "connexion", f"Inscription : {user.username}", request)

            messages.success(request, "Inscription réussie 🎉")
            return redirect("users:home")

    else:
        form = UserRegisterForm()

    return render(request, "users/register.html", {"form": form})


# =========================
# LOGIN
# =========================
def user_login(request):
    if request.method == "POST":
        form = UserLoginForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            user = authenticate(username=username, password=password)

            if user:
                login(request, user)
                user.derniere_connexion = timezone.now()
                user.save()

                _log(user, "connexion", f"Connexion : {user.username}", request)

                messages.success(request, f"Bonjour {user.first_name}")
                return redirect("users:home")

        messages.error(request, "Identifiants incorrects")

    else:
        form = UserLoginForm()

    return render(request, "users/login.html", {"form": form})


# =========================
# LOGOUT
# =========================
@login_required
def user_logout(request):
    _log(request.user, "deconnexion", "Déconnexion", request)
    logout(request)

    messages.info(request, "Déconnecté avec succès")
    return redirect("users:login")


# =========================
# PROFILE
# =========================
@login_required
def profile(request):
    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)

        if form.is_valid():
            form.save()

            _log(request.user, "profile", "Modification profil", request)

            messages.success(request, "Profil mis à jour")
            return redirect("users:profile")

    else:
        form = UserProfileForm(instance=request.user)

    return render(request, "users/profile.html", {"form": form})


# =========================
# USER LIST (ADMIN + FONCTIONNAIRE LIMITÉ)
# =========================
@login_required
def user_list(request):
    if not (request.user.is_staff or request.user.status == "fonctionnaire"):
        messages.error(request, "Accès refusé")
        return redirect("users:home")

    # Récupérer tous les utilisateurs (le template fera le filtre)
    users = User.objects.all().order_by("-date_inscription")
    return render(request, "users/user_list.html", {"users": users})


# =========================
# USER DETAIL
# =========================
@login_required
def user_detail(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Accès interdit")
        return redirect("users:home")

    user = get_object_or_404(User, pk=pk)
    return render(request, "users/user_detail.html", {"user_profile": user})


# =========================
# EDIT USER (FONCTIONNAIRE LIMITÉ)
# =========================
@login_required
def user_edit(request, pk):
    if not (request.user.is_staff or request.user.status == "fonctionnaire"):
        return redirect("users:home")

    user = get_object_or_404(User, pk=pk)

    # fonctionnaire restriction
    if request.user.status == "fonctionnaire":
        if user.is_staff or user.status == "fonctionnaire":
            messages.error(request, "Action non autorisée")
            return redirect("users:user_list")

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=user)

        if form.is_valid():
            form.save()
            messages.success(request, "Utilisateur modifié")
            return redirect("users:user_list")

    else:
        form = UserProfileForm(instance=user)

    return render(request, "users/user_edit.html", {
        "form": form,
        "user_profile": user
    })


# =========================
# DELETE USER (ADMIN ONLY)
# =========================
@login_required
def user_delete(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Accès refusé")
        return redirect("users:home")

    user = get_object_or_404(User, pk=pk)

    if user == request.user:
        messages.error(request, "Impossible de supprimer votre compte")
        return redirect("users:user_list")

    if request.method == "POST":
        username = user.username
        user.delete()

        messages.success(request, f"{username} supprimé")
        return redirect("users:user_list")

    return render(request, "users/user_confirm_delete.html", {
        "user_profile": user
    })


# =========================
# TOGGLE STAFF (ADMIN ONLY)
# =========================
@login_required
def user_toggle_staff(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Accès refusé")
        return redirect("users:home")

    user = get_object_or_404(User, pk=pk)

    if user == request.user:
        messages.error(request, "Action impossible")
        return redirect("users:user_list")

    user.is_staff = not user.is_staff

    if user.is_staff:
        user.status = "admin"

    user.save()

    messages.success(request, "Rôle modifié")
    return redirect("users:user_list")