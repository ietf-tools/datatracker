# Copyright The IETF Trust 2007, All Rights Reserved

# Caching accessor for the reverse of a ForeignKey relatinoship
# Started by axiak on #django
class FKAsOneToOne(object):
    def __init__(self, field, reverse = False, query = None):
        self.field = field
        self.reverse = reverse
	self.query = query
    
    def __get_attr(self, instance):
        if self.reverse:
            field_name = '%s_set' % self.field
        else:
            field_name = self.field
        return getattr(instance, field_name)

    def __get__(self, instance, Model):
        if not hasattr(instance, '_field_values'):
            instance._field_values = {}
        try:
            return instance._field_values[self.field]
	except KeyError:
	    pass

        if self.reverse:
            value_set = self.__get_attr(instance).all()
	    if self.query:
		value_set = value_set.filter(self.query)
	    try:
                instance._field_values[self.field] = value_set[0]
	    except IndexError:
                instance._field_values[self.field] = None
        else:
            instance._field_values[self.field] = self.__get_attr(instance)

        return instance._field_values[self.field]

    def __set__(self, instance, value):
        if self.reverse:
            # this is dangerous
            #other_instance = self.__get_attr(instance).all()[0]
            #setattr(other_instance, self.field, value)
            #other_instance.save()
	    raise NotImplemented
        else:
            setattr(instance, self.field, value)
