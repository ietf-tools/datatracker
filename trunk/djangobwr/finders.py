from django.contrib.staticfiles.finders import AppDirectoriesFinder

class AppDirectoriesFinderBower(AppDirectoriesFinder):

    def list(self, ignore_patterns):
        """
        List all files in all app storages.
        """
        ignore_patterns.append("bower_components")
        return super(AppDirectoriesFinderBower, self).list(ignore_patterns)
