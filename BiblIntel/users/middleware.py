from django.utils import timezone
from logs.models import LogAction


class ActivityMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.user.is_authenticated:

            last_time = request.session.get("last_time")

            now = timezone.now().timestamp()

            if last_time:
                duration = int(now - last_time)

                LogAction.objects.create(
                    utilisateur=request.user,
                    type_action="activité",
                    description="Temps utilisation",
                    temps_utilisation=duration,
                )

            request.session["last_time"] = now

        response = self.get_response(request)

        return response