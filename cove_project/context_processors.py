from django.conf import settings


def analytics(request):
    return {
        'hotjar': settings.HOTJAR
    }
