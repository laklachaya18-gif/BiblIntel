from django.contrib import admin
from .models import LogAction


@admin.register(LogAction)
class LogActionAdmin(admin.ModelAdmin):
    list_display = ["type_action", "utilisateur", "description", "date_action"]
    list_filter = ["type_action", "date_action"]
