from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    path('', views.livre_list, name='livre_list'),
    path('ajouter/', views.livre_create, name='livre_create'),
    path('bulk-delete/', views.bulk_delete_livres, name='bulk_delete'),
    path('<int:pk>/', views.livre_detail, name='livre_detail'),
    path('<int:pk>/read/', views.livre_read, name='livre_read'),
    path('<int:pk>/modifier/', views.livre_update, name='livre_update'),
    path('<int:pk>/supprimer/', views.livre_delete, name='livre_delete'),
    path('api/definition/', views.api_definition, name='api_definition'),
    path('api/save-bookmark/<int:pk>/', views.save_bookmark, name='save_bookmark'),
    path('api/save-notes/<int:pk>/', views.save_notes, name='save_notes'),
    path('api/save-word/<int:pk>/', views.save_word, name='save_word'),
    path(
    'ai-dictionary/',
    views.ai_dictionary,
    name='ai_dictionary'
),
]