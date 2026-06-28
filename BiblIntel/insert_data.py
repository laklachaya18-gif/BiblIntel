#!/usr/bin/env python
import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'biblintel.settings')
django.setup()

from users.models import User
from books.models import Categorie, Livre, Avis
from borrowings.models import Emprunt, Reservation
from banking.models import CompteBancaire, CompteEntreprise
from logs.models import LogAction
from notifications.models import Notification
from django.db import models

print("=" * 70)
print("📚 INSERTION DES DONNÉES DE TEST - BiblIntel (CORRIGÉE)")
print("=" * 70)

# ============================================================
# 1. CATÉGORIES
# ============================================================
categories_data = [
    ('Informatique', 'Livres sur la programmation, algorithmes et systèmes', None),
    ('Intelligence Artificielle', 'IA, Machine Learning, Deep Learning', 'Informatique'),
    ('Développement Web', 'HTML, CSS, JavaScript, Frameworks', 'Informatique'),
    ('Réseaux & Sécurité', 'Réseaux informatiques, cybersécurité', 'Informatique'),
    ('Littérature', 'Romans, nouvelles, poésie', None),
    ('Roman français', 'Romans d\'auteurs français', 'Littérature'),
    ('Science-Fiction', 'Futur, technologies, dystopies', 'Littérature'),
    ('Mathématiques', 'Algèbre, analyse, statistiques', None),
    ('Physique', 'Mécanique, électromagnétisme, quantique', None),
    ('Histoire', 'Histoire ancienne, moderne, contemporaine', None),
    ('Philosophie', 'Courants philosophiques, penseurs', None),
    ('Économie', 'Microéconomie, macroéconomie, finance', None),
    ('Droit', 'Droit civil, pénal, commercial', None),
    ('Psychologie', 'Psychologie clinique, sociale', None),
    ('Développement personnel', 'Bien-être, productivité, soft skills', None),
]

categories = {}
for nom, desc, parent_nom in categories_data:
    parent = categories.get(parent_nom) if parent_nom else None
    cat, created = Categorie.objects.get_or_create(nom=nom, defaults={'description': desc, 'parent': parent})
    categories[nom] = cat
    print(f"  {'✅' if created else '📁'} Catégorie: {nom}")

# ============================================================
# 2. UTILISATEURS
# ============================================================
users_data = [
    # ÉTUDIANTS (5)
    ('etudiant1', 'Ahmed', 'Benali', 'ahmed.benali@example.com', 'etudiant', '4IIR', '0612345678'),
    ('etudiant2', 'Fatima', 'Zahra', 'fatima.zahra@example.com', 'etudiant', 'IASD', '0623456789'),
    ('etudiant3', 'Youssef', 'El Amrani', 'youssef.elamrani@example.com', 'etudiant', 'Génie Civil', '0634567890'),
    ('etudiant4', 'Sara', 'Mansouri', 'sara.mansouri@example.com', 'etudiant', '4IIR', '0645678901'),
    ('etudiant5', 'Omar', 'Idrissi', 'omar.idrissi@example.com', 'etudiant', 'IASD', '0656789012'),
    # ENSEIGNANTS (5)
    ('enseignant1', 'Mohamed', 'El Fassi', 'mohamed.elfassi@example.com', 'enseignant', None, '0667890123'),
    ('enseignant2', 'Nadia', 'Benjelloun', 'nadia.benjelloun@example.com', 'enseignant', None, '0678901234'),
    ('enseignant3', 'Karim', 'Tazi', 'karim.tazi@example.com', 'enseignant', None, '0689012345'),
    ('enseignant4', 'Leila', 'Berrada', 'leila.berrada@example.com', 'enseignant', None, '0690123456'),
    ('enseignant5', 'Hassan', 'Lamrani', 'hassan.lamrani@example.com', 'enseignant', None, '0612345670'),
    # BIBLIOTHÉCAIRES (5) - avec RIB
    ('biblio1', 'Khadija', 'Slimani', 'khadija.slimani@example.com', 'bibliothecaire', None, '0612345680'),
    ('biblio2', 'Reda', 'Mouline', 'reda.mouline@example.com', 'bibliothecaire', None, '0623456790'),
    ('biblio3', 'Samira', 'Fassi', 'samira.fassi@example.com', 'bibliothecaire', None, '0634567801'),
    ('biblio4', 'Anas', 'Cherkaoui', 'anas.cherkaoui@example.com', 'bibliothecaire', None, '0645678912'),
    ('biblio5', 'Nadia', 'Toumi', 'nadia.toumi@example.com', 'bibliothecaire', None, '0656789023'),
    # EMPLOYEURS (5)
    ('employeur1', 'Rachid', 'El Hadri', 'rachid.elhadri@example.com', 'employeur', None, '0667890134'),
    ('employeur2', 'Naima', 'Bouazza', 'naima.bouazza@example.com', 'employeur', None, '0678901245'),
    ('employeur3', 'Fouad', 'Meknesi', 'fouad.meknesi@example.com', 'employeur', None, '0689012356'),
    ('employeur4', 'Latifa', 'Chraibi', 'latifa.chraibi@example.com', 'employeur', None, '0690123467'),
    ('employeur5', 'Mehdi', 'Joundi', 'mehdi.joundi@example.com', 'employeur', None, '0612345780'),
    # PERSONNES NORMALES (5)
    ('personne1', 'Imane', 'Bennis', 'imane.bennis@example.com', 'personne', None, '0623456791'),
    ('personne2', 'Hamza', 'Ziani', 'hamza.ziani@example.com', 'personne', None, '0634567802'),
    ('personne3', 'Rim', 'Kabbaj', 'rim.kabbaj@example.com', 'personne', None, '0645678913'),
    ('personne4', 'Yassine', 'Lahlou', 'yassine.lahlou@example.com', 'personne', None, '0656789024'),
    ('personne5', 'Siham', 'Alaoui', 'siham.alaoui@example.com', 'personne', None, '0667890135'),
]

users = {}
for username, first, last, email, status, filiere, phone in users_data:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'first_name': first,
            'last_name': last,
            'email': email,
            'status': status,
            'filiere': filiere,
            'telephone': phone,
            'points_fidelite': 0,
            'est_blackliste': False,
            'is_active': True,
            'is_staff': False,
            'is_superuser': False,
            'salaire_total': 0,  # ✅ Initialisé à 0
        }
    )
    if created:
        user.set_password('password123')
        user.save()
    users[username] = user
    print(f"  {'✅' if created else '📁'} Utilisateur: {username}")

# Points spéciaux
users['etudiant1'].points_fidelite = 45
users['etudiant2'].points_fidelite = 120
users['etudiant4'].points_fidelite = 200
users['etudiant5'].points_fidelite = 75
users['etudiant5'].est_blackliste = True
users['etudiant5'].raison_blacklist = '3 retards simultanés'
users['etudiant5'].date_blacklist = datetime.now() - timedelta(days=5)
users['personne3'].points_fidelite = 85
users['personne4'].points_fidelite = 250
users['personne5'].points_fidelite = 30
users['personne2'].est_blackliste = True
users['personne2'].raison_blacklist = 'Amendes impayées > 100 DH'
users['personne2'].date_blacklist = datetime.now() - timedelta(days=10)

for u in [users['etudiant1'], users['etudiant2'], users['etudiant4'], users['etudiant5'], 
          users['personne3'], users['personne4'], users['personne5'], users['personne2']]:
    u.save()

# RIB des bibliothécaires
biblio_ribs = {
    'biblio1': 'FR7612345678901234567890123',
    'biblio2': 'FR7612345678901234567890124',
    'biblio3': 'FR7612345678901234567890125',
    'biblio4': 'FR7612345678901234567890126',
    'biblio5': 'FR7612345678901234567890127',
}
for username, rib in biblio_ribs.items():
    users[username].rib = rib
    users[username].save()
    print(f"  📋 RIB défini pour {username}")

# ============================================================
# 3. LIVRES (avec association aux bibliothécaires)
# ============================================================
livres_data = [
    # (titre, auteur, resume, filiere, pdf, couv, pages, langue, max_emp, biblio_username)
    ('Artificial Intelligence: A Modern Approach', 'Stuart Russell, Peter Norvig', 
     'Livre de référence sur l\'intelligence artificielle.', '4IIR,IASD',
     'livres/pdfs/Artificial_Intelligence.pdf', 'livres/couvertures/Deep_Learning.png',
     1152, 'Anglais', 2, 'biblio1'),
    ('Deep Learning', 'Ian Goodfellow', 
     'Livre complet sur le deep learning.', '4IIR,IASD',
     'livres/pdfs/Deep_Learning.pdf', 'livres/couvertures/Deep_Learning.png',
     800, 'Anglais', 2, 'biblio1'),
    ('Hands-On Machine Learning', 'Aurélien Géron', 
     'Guide pratique pour le machine learning.', '4IIR',
     'livres/pdfs/Hands-On_Machine_Learning.pdf', None,
     856, 'Anglais', 1, 'biblio2'),
    ('JavaScript: The Good Parts', 'Douglas Crockford', 
     'Les bonnes parties du langage JavaScript.', '3IIR',
     'livres/pdfs/JavaScript_The_Good_Parts.pdf', 'livres/couvertures/JavaScript_The_God_Parts.png',
     176, 'Anglais', 3, 'biblio2'),
    ('Les Misérables', 'Victor Hugo', 
     'Chef-d\'œuvre de la littérature française.', 'Tous',
     'livres/pdfs/les_miserables_gvt3ZL2.pdf', 'livres/couvertures/les_miserables.png',
     1462, 'Français', 3, 'biblio3'),
    ('Le Petit Prince', 'Antoine de Saint-Exupéry', 
     'Conte philosophique et poétique.', 'Tous',
     'livres/pdfs/Le_Petit_Prince.pdf', 'livres/couvertures/Le_Petit_Prince.png',
     96, 'Français', 5, 'biblio3'),
    ('Ce soir', 'Auteur inconnu', 
     'Un roman mystérieux.', 'Tous',
     'livres/pdfs/Ce_soir_mPEOmbM.pdf', 'livres/couvertures/Ce soir.png',
     200, 'Français', 2, 'biblio4'),
    ('Meurtres sur Compostelle', 'Auteur inconnu', 
     'Un thriller palpitant.', 'Tous',
     'livres/pdfs/Meurtres_sur_Compostelle_JxTdJQS.pdf', None,
     250, 'Français', 2, 'biblio4'),
    ('1984', 'George Orwell', 'Dystopie classique.', 'Tous', None, None, 328, 'Français', 3, 'biblio5'),
    ('Le Meilleur des mondes', 'Aldous Huxley', 'Une dystopie futuriste.', 'Tous', None, None, 311, 'Français', 2, 'biblio5'),
    ('L\'Étranger', 'Albert Camus', 'Classique sur l\'absurde.', 'Tous', None, None, 123, 'Français', 3, 'biblio1'),
    ('La Peste', 'Albert Camus', 'Roman allégorique.', 'Tous', None, None, 320, 'Français', 2, 'biblio2'),
    ('Voyage au bout de la nuit', 'Louis-Ferdinand Céline', 'Roman noir.', 'Tous', None, None, 505, 'Français', 2, 'biblio3'),
    ('Clean Code', 'Robert C. Martin', 'Bonnes pratiques de code.', '4IIR,3IIR', None, None, 464, 'Anglais', 2, 'biblio4'),
    ('Introduction to Algorithms', 'Thomas H. Cormen', 'Algorithms reference.', '4IIR', None, None, 1312, 'Anglais', 1, 'biblio5'),
]

livres = {}
for titre, auteur, resume, filiere, pdf, couv, pages, langue, max_emp, biblio_username in livres_data:
    livre, created = Livre.objects.get_or_create(
        titre=titre,
        defaults={
            'auteur': auteur,
            'resume': resume,
            'filiere_cible': filiere,
            'fichier_pdf': pdf,
            'couverture': couv,
            'nombre_pages': pages,
            'langue': langue,
            'max_emprunts_simultanes': max_emp,
            'gain_salaire_base': 10,  # ✅ +10 DH par livre ajouté
            'gain_salaire_bonus_note': 0,
            'gain_salaire_emprunts': 0,
            'statut': 'disponible',
            'date_ajout': datetime.now() - timedelta(days=10),
            'bibliothecaire': users[biblio_username],  # ✅ Association au bibliothécaire
        }
    )
    livres[titre] = livre
    print(f"  {'✅' if created else '📁'} Livre: {titre[:40]}... (ajouté par {biblio_username})")

# Associer catégories
for titre, cat_noms in [
    ('Artificial Intelligence: A Modern Approach', ['Informatique', 'Intelligence Artificielle']),
    ('Deep Learning', ['Informatique', 'Intelligence Artificielle']),
    ('Hands-On Machine Learning', ['Informatique', 'Intelligence Artificielle']),
    ('JavaScript: The Good Parts', ['Informatique', 'Développement Web']),
    ('Les Misérables', ['Littérature', 'Roman français']),
    ('Le Petit Prince', ['Littérature', 'Roman français']),
    ('Ce soir', ['Littérature']),
    ('Meurtres sur Compostelle', ['Littérature']),
    ('1984', ['Littérature', 'Science-Fiction']),
    ('Le Meilleur des mondes', ['Littérature', 'Science-Fiction']),
    ('L\'Étranger', ['Littérature', 'Philosophie']),
    ('La Peste', ['Littérature', 'Philosophie']),
    ('Voyage au bout de la nuit', ['Littérature', 'Roman français']),
    ('Clean Code', ['Informatique', 'Développement Web']),
    ('Introduction to Algorithms', ['Informatique']),
]:
    livre = livres.get(titre)
    if livre:
        for cat_nom in cat_noms:
            cat = categories.get(cat_nom)
            if cat:
                livre.categories.add(cat)

# ============================================================
# 4. COMPTES BANCAIRES
# ============================================================
for user in users.values():
    CompteBancaire.objects.get_or_create(
        utilisateur=user,
        defaults={'solde': 500.00, 'numero_carte': '4111111111111111', 'date_expiration': '12/28', 'cryptogramme': '123'}
    )
print(f"  ✅ {CompteBancaire.objects.count()} comptes bancaires créés")

# ============================================================
# 5. COMPTE ENTREPRISE
# ============================================================
CompteEntreprise.objects.get_or_create(
    id=1,
    defaults={'nom': 'BiblIntel - Compte principal', 'solde': 0}
)
print("  ✅ Compte entreprise créé")

# ============================================================
# 6. EMPRUNTS
# ============================================================
today = datetime.now().date()

emprunts_data = [
    (users['etudiant1'], livres['Deep Learning'], today - timedelta(days=20), today + timedelta(days=10), 'en_cours', 0, 0, False, 0),
    (users['etudiant2'], livres['Hands-On Machine Learning'], today - timedelta(days=35), today - timedelta(days=5), 'retard', 50, 0, False, 0),
    (users['etudiant1'], livres['Les Misérables'], today - timedelta(days=60), today - timedelta(days=32), 'retourne', 0, 0, False, 0),
    (users['personne1'], livres['1984'], today - timedelta(days=50), today - timedelta(days=45), 'retourne', 80, 0, False, 0),
    (users['personne3'], livres['Le Meilleur des mondes'], today - timedelta(days=40), today - timedelta(days=35), 'retourne', 100, 0, True, 0),
    (users['enseignant1'], livres['Le Petit Prince'], today - timedelta(days=35), today + timedelta(days=2), 'en_cours', 0, 0, False, 1),
    (users['etudiant4'], livres['JavaScript: The Good Parts'], today - timedelta(days=5), None, 'en_attente', 0, 0, False, 0),
    (users['etudiant4'], livres['Deep Learning'], today - timedelta(days=55), today - timedelta(days=25), 'retourne', 0, 0, False, 0),
    (users['personne2'], livres['1984'], today - timedelta(days=70), today - timedelta(days=60), 'retourne', 150, 0, False, 0),
    (users['employeur1'], livres['Artificial Intelligence: A Modern Approach'], today - timedelta(days=15), today + timedelta(days=15), 'en_cours', 0, 0, False, 0),
    (users['personne4'], livres['Meurtres sur Compostelle'], today - timedelta(days=45), today - timedelta(days=40), 'retourne', 60, 0, False, 0),
    (users['personne5'], livres['L\'Étranger'], today - timedelta(days=50), today - timedelta(days=30), 'retourne', 0, 0, True, 0),
    (users['etudiant3'], livres['Ce soir'], today - timedelta(days=10), today + timedelta(days=20), 'en_cours', 0, 0, False, 0),
    (users['enseignant3'], livres['Clean Code'], today - timedelta(days=12), today + timedelta(days=18), 'en_cours', 0, 0, False, 0),
    (users['employeur2'], livres['Introduction to Algorithms'], today - timedelta(days=40), today - timedelta(days=38), 'retourne', 30, 0, False, 0),
]

for user, livre, debut, retour_prevue, statut, amende, payee, prolonge, nb_prolong in emprunts_data:
    if statut == 'retourne' and retour_prevue is not None:
        date_retour_effective = retour_prevue + timedelta(days=5 if amende > 0 else -2)
    else:
        date_retour_effective = None
    
    emprunt = Emprunt.objects.create(
        utilisateur=user,
        livre=livre,
        date_demande=debut,
        date_approbation=debut if statut != 'en_attente' else None,
        date_debut=debut if statut != 'en_attente' else None,
        date_retour_prevue=retour_prevue,
        date_retour_effective=date_retour_effective if statut == 'retourne' else None,
        statut=statut,
        amende_totale=amende,
        est_payee=payee,
        a_prolonge=prolonge,
        nombre_prolongations=nb_prolong,
    )
    
    # ✅ Incrémenter le compteur d'emprunts du livre
    livre.nombre_emprunts += 1
    livre.save()
    
    # ✅ Si le livre a un bibliothécaire, ajouter +5 DH pour l'emprunt
    if livre.bibliothecaire:
        livre.gain_salaire_emprunts += 5
        livre.save()
        # Mettre à jour le salaire du bibliothécaire
        livre.bibliothecaire.salaire_total = sum(
            l.gain_salaire_base + l.gain_salaire_bonus_note + l.gain_salaire_emprunts
            for l in Livre.objects.filter(bibliothecaire=livre.bibliothecaire)
        )
        livre.bibliothecaire.save()

print(f"  ✅ {Emprunt.objects.count()} emprunts créés")

# ============================================================
# 7. RÉSERVATIONS
# ============================================================
Reservation.objects.create(utilisateur=users['etudiant5'], livre=livres['Hands-On Machine Learning'], position_file=1)
Reservation.objects.create(utilisateur=users['enseignant2'], livre=livres['Hands-On Machine Learning'], position_file=2)
Reservation.objects.create(utilisateur=users['etudiant2'], livre=livres['Artificial Intelligence: A Modern Approach'], position_file=1)
Reservation.objects.create(utilisateur=users['enseignant4'], livre=livres['JavaScript: The Good Parts'], position_file=1)
print(f"  ✅ {Reservation.objects.count()} réservations créées")

# ============================================================
# 8. AVIS (avec bonus pour les bibliothécaires)
# ============================================================
avis_data = [
    (livres['Artificial Intelligence: A Modern Approach'], users['etudiant1'], 5, 'Excellent livre sur l\'IA ! Très complet.'),
    (livres['Deep Learning'], users['etudiant3'], 5, 'Le meilleur livre sur le Deep Learning !'),
    (livres['Les Misérables'], users['personne1'], 5, 'Chef-d\'œuvre absolu !'),
    (livres['Le Petit Prince'], users['personne4'], 5, 'Magnifique conte philosophique.'),
    # ✅ Avis pour générer des bonus notes (≥ 4)
    (livres['1984'], users['etudiant2'], 4, 'Très bonne dystopie, je recommande.'),
    (livres['Clean Code'], users['etudiant1'], 5, 'Indispensable pour tout développeur !'),
]

for livre, user, note, commentaire in avis_data:
    avis, created = Avis.objects.get_or_create(
        livre=livre,
        utilisateur=user,
        defaults={'note': note, 'commentaire': commentaire}
    )
    if created:
        # ✅ Si note ≥ 4, ajouter +20 DH au bibliothécaire
        if note >= 4 and livre.bibliothecaire:
            livre.gain_salaire_bonus_note += 20
            livre.save()
            livre.bibliothecaire.salaire_total = sum(
                l.gain_salaire_base + l.gain_salaire_bonus_note + l.gain_salaire_emprunts
                for l in Livre.objects.filter(bibliothecaire=livre.bibliothecaire)
            )
            livre.bibliothecaire.save()
            print(f"  ⭐ Bonus +20 DH pour {livre.bibliothecaire.username} (avis ≥ 4 sur '{livre.titre[:30]}...')")

print(f"  ✅ {Avis.objects.count()} avis créés")

# ============================================================
# 9. NOTIFICATIONS
# ============================================================
Notification.objects.create(
    utilisateur=users['etudiant2'],
    type_notification='retard',
    titre='⚠️ Retard sur votre emprunt',
    message='Le livre "Hands-On Machine Learning" est en retard.',
)
Notification.objects.create(
    utilisateur=users['enseignant1'],
    type_notification='retour_proche',
    titre='Rappel : retour dans 2 jours',
    message='Le livre "Le Petit Prince" doit être retourné bientôt.',
)
Notification.objects.create(
    utilisateur=users['personne2'],
    type_notification='blacklist',
    titre='⚠️ Vous avez été blacklisté',
    message='Raison : Amendes impayées dépassant 100 DH.',
)
print(f"  ✅ {Notification.objects.count()} notifications créées")

# ============================================================
# 10. Mise à jour des notes moyennes
# ============================================================
for livre in livres.values():
    avg = livre.avis.aggregate(models.Avg('note'))['note__avg']
    if avg:
        livre.note_moyenne = round(avg, 2)
        livre.save()
print("  ✅ Notes moyennes mises à jour")

# ============================================================
# 11. RÉCAPITULATIF DES SALAIRES DES BIBLIOTHÉCAIRES
# ============================================================
print("\n" + "=" * 70)
print("📊 SALAIRES DES BIBLIOTHÉCAIRES")
print("=" * 70)
for username in ['biblio1', 'biblio2', 'biblio3', 'biblio4', 'biblio5']:
    biblio = users[username]
    livres_biblio = Livre.objects.filter(bibliothecaire=biblio)
    base_total = sum(l.gain_salaire_base for l in livres_biblio)
    bonus_total = sum(l.gain_salaire_bonus_note for l in livres_biblio)
    emprunts_total = sum(l.gain_salaire_emprunts for l in livres_biblio)
    total = base_total + bonus_total + emprunts_total
    print(f"  👤 {username}:")
    print(f"     📚 Livres: {livres_biblio.count()} | Base: {base_total} DH | Bonus: {bonus_total} DH | Emprunts: {emprunts_total} DH")
    print(f"     💰 Salaire total: {total} DH\n")

# ============================================================
# RÉCAPITULATIF FINAL
# ============================================================
print("=" * 70)
print("✨ INSERTION TERMINÉE AVEC SUCCÈS !")
print("=" * 70)
print(f"📚 Livres : {Livre.objects.count()}")
print(f"👥 Utilisateurs : {User.objects.count()}")
print(f"💰 Comptes bancaires : {CompteBancaire.objects.count()}")
print(f"📖 Emprunts : {Emprunt.objects.count()}")
print(f"⭐ Avis : {Avis.objects.count()}")
print(f"🔔 Notifications : {Notification.objects.count()}")
print(f"📌 Réservations : {Reservation.objects.count()}")
print("=" * 70)