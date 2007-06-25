from django.conf import settings

def server_mode(request):
    return {'server_mode': settings.SERVER_MODE}
    
