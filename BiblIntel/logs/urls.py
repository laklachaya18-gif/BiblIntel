from django.urls import path
from . import views

app_name = "logs"

urlpatterns = [
    path("", views.log_list, name="log_list"),
    # L'export CSV se fait via ?export=csv sur la même vue
]
