from django.core.files.storage import FileSystemStorage

class NoLocationMigrationFileSystemStorage(FileSystemStorage):

    def deconstruct(obj):
        path, args, kwargs = FileSystemStorage.deconstruct(obj)
        kwargs["location"] = None
        return (path, args, kwargs)
