def name(name_class, slug, name, desc="", order=0):
    # create if it doesn't exist, set name and desc
    obj, _ = name_class.objects.get_or_create(slug=slug)
    obj.name = name
    obj.desc = desc
    obj.order = order
    obj.save()
    return obj
