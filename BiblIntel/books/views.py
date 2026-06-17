import json
import os
import urllib.request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Livre, Categorie, Avis, UserBookmark, UserNote, UserWord
from .forms import LivreForm, AvisForm
from logs.models import LogAction
from borrowings.models import Emprunt, Reservation

# Dictionnaire local pour les mots français (fallback quand l'API ne trouve pas)
LOCAL_DICT = {
    'ordinateur': "Machine électronique qui traite des données et exécute des programmes.",
    'chat': "Animal domestique de la famille des félins.",
    'livre': "Ensemble de pages reliées contenant un texte ou des images.",
    'bibliothèque': "Lieu où sont conservés et consultés des livres.",
    'emprunt': "Action d'emprunter un livre pour une durée déterminée.",
    'réservation': "Action de réserver un livre avant de l'emprunter.",
    'fonctionnaire': "Personne qui travaille pour la bibliothèque.",
    'admin': "Administrateur du système, a tous les droits.",
    'django': "Framework web Python pour le développement rapide d'applications.",
    'python': "Langage de programmation interprété, polyvalent.",
    'javascript': "Langage de programmation pour le web.",
    'html': "Langage de balisage pour créer des pages web.",
    'css': "Langage de style pour les pages web.",
    'biblintel': "Votre bibliothèque numérique intelligente.",
    'lecture': "Action de lire un texte ou un livre.",
    'pdf': "Format de document portable, utilisé pour les livres numériques.",
    'emprunter': "Prendre un livre pour une durée déterminée.",
    'retour': "Action de rendre un livre emprunté.",
    'amende': "Pénalité financière pour retard de retour.",
    'blacklist': "Liste des utilisateurs bloqués pour non-respect des règles.",
    'internet': "Réseau informatique mondial.",
    'logiciel': "Ensemble de programmes qui font fonctionner un ordinateur.",
    'materiel': "Composants physiques d'un ordinateur.",
    'كتاب': "مجموعة من الصفحات المترابطة تحتوي على نص أو صور.",
    'مكتبة': "مكان يتم فيه حفظ الكتب واستشارتها.",
    'حاسوب': "آلة إلكترونية تعالج البيانات وتنفذ البرامج.",
    'انترنت': "شبكة كمبيوتر عالمية تربط ملايين الأجهزة.",
    'برمجة': "عملية كتابة التعليمات للحاسوب.",
    'لغة': "نظام تواصل يستخدمه البشر.",
    'قارئ': "شخص يقرأ الكتب أو النصوص.",
    'كاتب': "شخص يؤلف الكتب أو النصوص.",
    'رواية': "عمل أدبي طويل يحكي قصة.",
    'شاعر': "شخص يكتب الشعر.",
}

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


def livre_list(request):
    """Catalogue des livres - visible par tous (même non connectés)"""
    livres = Livre.objects.all()
    categorie_id = request.GET.get("categorie")
    search = request.GET.get("search", "").strip()
    statut = request.GET.get("statut")
    filiere = request.GET.get("filiere", "").strip()

    if categorie_id:
        livres = livres.filter(categories__id=categorie_id)
    if search:
        livres = livres.filter(
            Q(titre__icontains=search)
            | Q(auteur__icontains=search)
            | Q(resume__icontains=search)
            | Q(tags__icontains=search)
        )
        # ✅ Historique des recherches uniquement pour utilisateurs connectés
        if request.user.is_authenticated:
            hist = request.session.get("historique_recherches", [])
            if search not in hist:
                hist.insert(0, search)
                hist = hist[:5]
            request.session["historique_recherches"] = hist
    if statut:
        livres = livres.filter(statut=statut)
    if filiere:
        livres = livres.filter(filiere_cible__icontains=filiere)

    # Autocomplete JSON (accessible à tous)
    if request.GET.get("autocomplete"):
        titres = list(livres.values_list("titre", flat=True)[:8])
        auteurs = list(
            Livre.objects.filter(auteur__icontains=search)
            .values_list("auteur", flat=True)
            .distinct()[:4]
        )
        results = list(dict.fromkeys(titres + auteurs))[:8]
        return JsonResponse({"results": results})

    categories = Categorie.objects.all()
    
    # ✅ Historique uniquement pour connectés
    historique = []
    if request.user.is_authenticated:
        historique = request.session.get("historique_recherches", [])

    # ============================================================
    # 📌 RECOMMANDATIONS PERSONNALISÉES (UNIQUEMENT POUR CONNECTÉS)
    # ============================================================
    recommandations = []
    
    # ✅ Les recommandations sont UNIQUEMENT pour les utilisateurs connectés
    if request.user.is_authenticated and not search:
        user = request.user
        est_admin_ou_bibliothecaire = user.is_staff or user.status == "admin" or user.status == "bibliothecaire"
        
        # ❌ Admin et bibliothécaire n'ont PAS de recommandations
        if not est_admin_ou_bibliothecaire:
            # Récupérer les IDs des livres déjà empruntés par l'utilisateur
            emprunts_ids = Emprunt.objects.filter(utilisateur=user).values_list("livre_id", flat=True)
            
            # Base : livres disponibles uniquement
            base_qs = Livre.objects.filter(statut="disponible").exclude(id__in=emprunts_ids)
            
            # ===== 1. ÉTUDIANT =====
            if user.status == "etudiant" and user.filiere:
                recommandations = list(
                    base_qs.filter(filiere_cible__icontains=user.filiere)
                    .order_by("-note_moyenne", "-nombre_emprunts")[:4]
                )
            
            # ===== 2. ENSEIGNANT =====
            elif user.status == "enseignant":
                qs_matiere = base_qs.filter(
                    Q(tags__icontains=user.matiere_enseignee) |
                    Q(filiere_cible__icontains=user.matiere_enseignee) |
                    Q(resume__icontains=user.matiere_enseignee)
                )
                qs_categories = base_qs.filter(categories__in=user.categories_preferees.all())
                
                recommandations = list(
                    (qs_matiere | qs_categories)
                    .distinct()
                    .order_by("-note_moyenne", "-nombre_emprunts")[:4]
                )
            
            # ===== 3. EMPLOYEUR =====
            elif user.status == "employeur" and user.domaine_professionnel:
                recommandations = list(
                    base_qs.filter(
                        Q(tags__icontains=user.domaine_professionnel) |
                        Q(categories__nom__icontains=user.domaine_professionnel) |
                        Q(filiere_cible__icontains=user.domaine_professionnel) |
                        Q(resume__icontains=user.domaine_professionnel)
                    )
                    .distinct()
                    .order_by("-note_moyenne", "-nombre_emprunts")[:4]
                )
            
            # ===== 4. PERSONNE NORMALE =====
            elif user.status == "personne":
                if user.categories_preferees.exists():
                    recommandations = list(
                        base_qs.filter(categories__in=user.categories_preferees.all())
                        .distinct()
                        .order_by("-note_moyenne", "-nombre_emprunts")[:4]
                    )
            
            # ===== 5. COMPLÉTER AVEC LES LIVRES POPULAIRES =====
            if len(recommandations) < 4:
                ids_deja = [l.id for l in recommandations] + list(emprunts_ids)
                plus_pop = list(
                    Livre.objects.filter(statut="disponible")
                    .exclude(id__in=ids_deja)
                    .order_by("-nombre_emprunts", "-note_moyenne")[:4 - len(recommandations)]
                )
                recommandations += plus_pop

    return render(
        request,
        "books/livre_list.html",
        {
            "livres": livres,
            "categories": categories,
            "search": search,
            "statut": statut,
            "filiere": filiere,
            "historique_recherches": historique,
            "recommandations": recommandations,
            "user_is_authenticated": request.user.is_authenticated,  # ← AJOUTÉ pour le template
        },
    )
def livre_detail(request, pk):
    """Détail d'un livre - accessible à tous (connectés ou non)"""
    livre = get_object_or_404(Livre, pk=pk)
    avis_list = livre.avis.all()
    
    # Variables pour tous (indépendantes de l'authentification)
    prochain_retour = (
        Emprunt.objects.filter(livre=livre, statut__in=["en_cours", "retard"])
        .order_by("date_retour_prevue")
        .first()
    )
    
    file_attente = Reservation.objects.filter(livre=livre, est_active=True).order_by("date_reservation")
    
    # Variables dépendantes de l'authentification (visiteur = valeurs par défaut)
    user_avis = None
    is_admin = False
    is_bibliothecaire = False
    
    if request.user.is_authenticated:
        user_avis = avis_list.filter(utilisateur=request.user).first()
        is_admin = request.user.is_staff or request.user.status == "admin"
        is_bibliothecaire = request.user.status == "bibliothecaire"
    
    # Traitement du formulaire d'avis (uniquement pour utilisateurs connectés et non admin)
    if request.method == "POST" and request.user.is_authenticated and not user_avis and not is_admin:
        if Avis.objects.filter(livre=livre, utilisateur=request.user).exists():
            messages.error(request, "Vous avez déjà laissé un avis pour ce livre.")
            return redirect("books:livre_detail", pk=pk)
        form = AvisForm(request.POST)
        
        if form.is_valid():
            avis = form.save(commit=False)
            avis.livre = livre
            avis.utilisateur = request.user
            avis.save()
            
            # Mettre à jour la note moyenne du livre
            moyenne = livre.avis.aggregate(Avg("note"))["note__avg"] or 0
            livre.note_moyenne = round(moyenne, 2)
            
            # BONUS SALAIRE BIBLIOTHÉCAIRE (si note >= 4/5)
            if avis.note >= 4 and livre.bibliothecaire:
                livre.gain_salaire_bonus_note += 20
                total_gains = sum(
                    l.gain_salaire_base + l.gain_salaire_bonus_note + l.gain_salaire_emprunts
                    for l in Livre.objects.filter(bibliothecaire=livre.bibliothecaire)
                )
                livre.bibliothecaire.salaire_total = total_gains
                livre.bibliothecaire.save()
                messages.success(request, f"Avis ajouté ! +20 DH pour le bibliothécaire ({livre.bibliothecaire.first_name})")
            else:
                messages.success(request, "Avis ajouté avec succès.")
            
            livre.save()
            return redirect("books:livre_detail", pk=pk)
    else:
        form = AvisForm()
    
    return render(
        request,
        "books/livre_detail.html",
        {
            "livre": livre,
            "avis_list": avis_list,
            "form": form,
            "user_avis": user_avis,
            "is_admin": is_admin,
            "is_bibliothecaire": is_bibliothecaire,
            "prochain_retour": prochain_retour,
            "file_attente": file_attente,
        },
    )
@login_required
def livre_create(request):
    # Vérifier les droits
    if not (request.user.is_staff or request.user.status == "bibliothecaire"):
        messages.error(request, "Accès réservé aux administrateurs et bibliothécaires.")
        return redirect("books:livre_list")
    
    if request.method == "POST":
        form = LivreForm(request.POST, request.FILES)
        if form.is_valid():
            livre = form.save(commit=False)
            livre.ajoute_par = request.user
            
            if request.user.status == "bibliothecaire":
                livre.bibliothecaire = request.user
                livre.gain_salaire_base = 10
                livre.save()
                request.user.salaire_total += 10
                request.user.save()
                messages.success(request, f"Livre ajouté avec succès. +10 DH pour votre salaire !")
            else:
                livre.save()
                messages.success(request, "Livre ajouté avec succès.")
            
            form.save_m2m()
            _log(request.user, "crud_livre", f"Ajout livre : {livre.titre}", request)
            return redirect("books:livre_list")
        # ✅ Si formulaire invalide, continuer pour afficher les erreurs
    else:
        form = LivreForm()
    
    # ✅ TOUJOURS retourner le template (GET ou formulaire invalide)
    categories = Categorie.objects.all()
    return render(request, "books/livre_form.html", {
        "form": form,
        "titre": "Ajouter un livre",
        "categories": categories
    })
@login_required
def livre_update(request, pk):
    """Modifier un livre (admin tous, bibliothécaire uniquement ses livres)"""
    livre = get_object_or_404(Livre, pk=pk)
    
    # Vérifier les droits
    est_admin = request.user.is_staff
    est_bibliothecaire_proprietaire = (
        request.user.status == "bibliothecaire" and 
        livre.bibliothecaire == request.user
    )
    
    if not (est_admin or est_bibliothecaire_proprietaire):
        messages.error(request, "Vous n'avez pas le droit de modifier ce livre.")
        return redirect("books:livre_detail", pk=pk)
    
    if request.method == "POST":
        form = LivreForm(request.POST, request.FILES, instance=livre)
        if form.is_valid():
            form.save()
            _log(request.user, "crud_livre", f"Modification livre : {livre.titre}", request)
            messages.success(request, "Livre modifié avec succès.")
            return redirect("books:livre_detail", pk=pk)
        else:
            messages.error(request, "Impossible de modifier le livre. Vérifiez les champs.")
    else:
        form = LivreForm(instance=livre)
    
    categories = Categorie.objects.all()
    return render(request, "books/livre_form.html", {
        "form": form, 
        "titre": "Modifier le livre", 
        "categories": categories
    })

@login_required
def livre_read(request, pk):
    """Lecture du PDF avec toutes les fonctionnalités"""
    livre = get_object_or_404(Livre, pk=pk)

    # ✅ ADMIN ou BIBLIOTHÉCAIRE : lecture sans restriction
    est_admin_ou_bibliothecaire = request.user.is_staff or request.user.status == "bibliothecaire"

    if est_admin_ou_bibliothecaire:
        # Les admins et bibliothécaires peuvent lire tous les livres sans emprunt
        pass
    else:
        # Utilisateur normal : doit avoir emprunté le livre
        a_emprunte = Emprunt.objects.filter(
            utilisateur=request.user,
            livre=livre,
            statut__in=["en_cours", "retard"]
        ).exists()
        
        if not a_emprunte:
            messages.error(request, "⛔ Vous devez emprunter ce livre pour pouvoir le lire.")
            return redirect("books:livre_detail", pk=pk)

    saved_page = 1
    notes = ""
    saved_words = []

    if request.user.is_authenticated:
        bookmark = UserBookmark.objects.filter(user=request.user, livre=livre).first()
        if bookmark:
            saved_page = bookmark.page

        user_note = UserNote.objects.filter(user=request.user, livre=livre).first()
        if user_note:
            notes = user_note.notes

        user_words = UserWord.objects.filter(user=request.user, livre=livre)
        saved_words = [word.word for word in user_words]

    context = {
        'livre': livre,
        'pdf_url': livre.fichier_pdf.url if livre.fichier_pdf else None,
        'saved_page': saved_page,
        'notes': notes,
        'saved_words': json.dumps(saved_words),
    }
    return render(request, 'books/livre_read.html', context)
@login_required
def livre_delete(request, pk):
    """Supprimer un livre (admin tous, bibliothécaire uniquement ses livres)"""
    livre = get_object_or_404(Livre, pk=pk)
    
    # Vérifier les droits
    est_admin = request.user.is_staff
    est_bibliothecaire_proprietaire = (
        request.user.status == "bibliothecaire" and 
        livre.bibliothecaire == request.user
    )
    
    if not (est_admin or est_bibliothecaire_proprietaire):
        messages.error(request, "Vous n'avez pas le droit de supprimer ce livre.")
        return redirect("books:livre_detail", pk=pk)
    
    if request.method == "POST":
        titre = livre.titre
        
        # ✅ Retirer le salaire uniquement si c'est un bibliothécaire (pas admin)
        if livre.bibliothecaire and not est_admin:
            perte = livre.gain_salaire_base + livre.gain_salaire_bonus_note + livre.gain_salaire_emprunts
            livre.bibliothecaire.salaire_total -= perte
            livre.bibliothecaire.save()
            messages.success(request, f"Livre supprimé. Salaire diminué de {perte:.2f} DH.")
        else:
            messages.success(request, f"Livre '{titre}' supprimé avec succès.")
        
        # Supprimer les fichiers physiques
        if livre.fichier_pdf and os.path.isfile(livre.fichier_pdf.path):
            os.remove(livre.fichier_pdf.path)
        if livre.couverture and os.path.isfile(livre.couverture.path):
            os.remove(livre.couverture.path)
        if hasattr(livre, 'musique_ambiance') and livre.musique_ambiance and os.path.isfile(livre.musique_ambiance.path):
            os.remove(livre.musique_ambiance.path)
        
        livre.delete()
        _log(request.user, "crud_livre", f"Suppression livre : {titre}", request)
        return redirect("books:livre_list")
    
    return render(request, "books/livre_confirm_delete.html", {"livre": livre})
@login_required
def bulk_delete_livres(request):
    """Supprimer plusieurs livres en masse"""
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('users:home')

    if request.method == 'POST':
        livre_ids = request.POST.get('livre_ids', '')

        if livre_ids:
            ids_list = [int(id) for id in livre_ids.split(',')]
            livres_a_supprimer = Livre.objects.filter(id__in=ids_list)
            nombre = livres_a_supprimer.count()

            for livre in livres_a_supprimer:
                if livre.fichier_pdf and os.path.isfile(livre.fichier_pdf.path):
                    os.remove(livre.fichier_pdf.path)
                if livre.couverture and os.path.isfile(livre.couverture.path):
                    os.remove(livre.couverture.path)

            livres_a_supprimer.delete()
            messages.success(request, f"{nombre} livre(s) supprimé(s) avec succès.")
        else:
            messages.warning(request, "Aucun livre sélectionné.")

    return redirect('books:livre_list')


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def save_bookmark(request, pk):
    livre = get_object_or_404(Livre, pk=pk)
    data = json.loads(request.body)
    page = data.get('page', 1)

    bookmark, created = UserBookmark.objects.update_or_create(
        user=request.user,
        livre=livre,
        defaults={'page': page, 'updated_at': timezone.now()}
    )

    return JsonResponse({'success': True, 'page': page})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def save_notes(request, pk):
    livre = get_object_or_404(Livre, pk=pk)
    data = json.loads(request.body)
    notes = data.get('notes', '')

    user_note, created = UserNote.objects.update_or_create(
        user=request.user,
        livre=livre,
        defaults={'notes': notes, 'updated_at': timezone.now()}
    )

    return JsonResponse({'success': True, 'notes': notes})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def save_word(request, pk):
    livre = get_object_or_404(Livre, pk=pk)
    data = json.loads(request.body)
    word = data.get('word', '').lower().strip()
    definition = data.get('definition', '')

    if word:
        user_word, created = UserWord.objects.get_or_create(
            user=request.user,
            livre=livre,
            word=word,
            defaults={'definition': definition, 'searched_at': timezone.now()}
        )
        if not created:
            user_word.searched_at = timezone.now()
            user_word.save()
        return JsonResponse({'success': True, 'word': word, 'created': created})

    return JsonResponse({'success': False, 'error': 'Mot invalide'})


@csrf_exempt
def api_definition(request):
    word = request.GET.get('word', '').strip()

    if not word:
        return JsonResponse({'error': 'Aucun mot fourni'}, status=400)

    dictionary = {
        'intelligence': "Capacité à comprendre, apprendre et raisonner.",
        'artificielle': "Qui est produit par l'homme, non naturel.",
        'apprentissage': "Processus d'acquisition de connaissances.",
        'deep': "Profond, avancé.",
        'learning': "Apprentissage.",
        'réseau': "Ensemble d'éléments interconnectés.",
        'neurone': "Cellule nerveuse qui transmet des signaux.",
        'algorithme': "Suite d'opérations pour résoudre un problème.",
        'donnée': "Information brute.",
        'modèle': "Représentation simplifiée d'un système.",
        'conscience': "Faculté de se connaître soi-même.",
        'tranquille': "Calme, paisible.",
        'projetait': "Planifiait, envisageait.",
        'entraînement': "Action de former, d'exercer.",
        'insultes': "Paroles offensantes.",
        'compris': "Saisi par l'esprit.",
        'gigoter': "Remuer, s'agiter.",
        'manie': "Habitude étrange, tic.",
        'dont': "Pronom relatif indiquant la possession.",
        'ébahi': "Très surpris, stupéfait.",
        'attirail': "Ensemble d'objets, équipement.",
        'diable': "Être maléfique, exclamation de surprise.",
        'ia': "Intelligence Artificielle - domaine de l'informatique.",
        'machine': "Appareil mécanique ou électronique.",
        'data': "Données, informations brutes.",
        'code': "Ensemble d'instructions en langage informatique.",
        'python': "Langage de programmation interprété.",
        'java': "Langage de programmation orienté objet.",
        'javascript': "Langage de programmation pour le web.",
        'html': "Langage de balisage pour créer des pages web.",
        'css': "Langage de style pour les pages web.",
    }

    clean_word = word.lower().strip()
    definition = dictionary.get(clean_word, f"Définition non trouvée pour '{word}'.")

    return JsonResponse({
        'success': True,
        'word': word,
        'definition': definition,
        'examples': [],
        'synonyms': []
    })


@csrf_exempt
@login_required
def ai_dictionary(request):
    """Dictionnaire via API gratuite + fallback local"""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body)
        word = data.get("word", "").strip().lower()

        if not word:
            return JsonResponse({"error": "empty word"}, status=400)

        # 1️⃣ Essayer l'API (anglais d'abord, puis français)
        for lang in ["en", "fr"]:
            try:
                url = f"https://api.dictionaryapi.dev/api/v2/entries/{lang}/{word}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        result = json.loads(response.read())
                        if result and len(result) > 0:
                            meanings = result[0].get('meanings', [])
                            if meanings:
                                definitions = meanings[0].get('definitions', [])
                                if definitions:
                                    definition = definitions[0].get('definition', '')
                                    if definition:
                                        return JsonResponse({
                                            "success": True,
                                            "result": definition,
                                            "lang": lang
                                        })
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
            except Exception:
                continue

        # 2️⃣ Fallback : dictionnaire local
        if word in LOCAL_DICT:
            return JsonResponse({
                "success": True,
                "result": LOCAL_DICT[word],
                "source": "local"
            })

        # 3️⃣ Aucune définition trouvée
        return JsonResponse({
            "success": False,
            "result": f"Définition non trouvée pour '{word}'."
        })

    except Exception as e:
        print(f"[ai_dictionary ERROR] {type(e).__name__}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)