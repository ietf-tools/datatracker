from django.apps import AppConfig
from . import populate_api_list


class ApiConfig(AppConfig):
    name = "ietf.api"

    def ready(self):
        """Hook to do init after the app registry is fully populated
        
        Importing models or accessing the app registry is ok here, but do not
        interact with the database. See        
        https://docs.djangoproject.com/en/4.2/ref/applications/#django.apps.AppConfig.ready
        """
        # Populate our API list now that the app registry is set up
        populate_api_list()

        # Import drf-spectacular extensions 
        import ietf.api.schema  # pyflakes: ignore
