from ietf.group.models import Group, Role
from ietf.person.models import Person
from ietf.utils.proxy import proxy_personify_role

from ietf.liaisons.accounts import (is_ietfchair, is_iabchair, is_iab_executive_director,
                                    get_ietf_chair, get_iab_chair, get_iab_executive_director,
                                    is_secretariat)

IETFCHAIR = {'name': u'The IETF Chair', 'address': u'chair@ietf.org'}
IESG = {'name': u'The IESG', 'address': u'iesg@ietf.org'}
IAB = {'name': u'The IAB', 'address': u'iab@iab.org'}
IABCHAIR = {'name': u'The IAB Chair', 'address': u'iab-chair@iab.org'}
IABEXECUTIVEDIRECTOR = {'name': u'The IAB Executive Director', 'address': u'execd@iab.org'}
IRTFCHAIR = {'name': u'The IRTF Chair', 'address': u'irtf-chair@irtf.org'}
IESGANDIAB = {'name': u'The IESG and IAB', 'address': u'iesg-iab@ietf.org'}


class FakePerson(object):

    def __init__(self, name, address):
        self.name = name
        self.address = address

    def email(self):
        return (self.name, self.address)

# the following is a biggish object hierarchy abstracting the entity
# names and auth rules for posting liaison statements in a sort of
# semi-declarational (and perhaps overengineered given the revamped
# schema) way - unfortunately, it's never been strong enough to do so
# fine-grained enough so the form code also has some rules

def all_sdo_managers():
    return [proxy_personify_role(r) for r in Role.objects.filter(group__type="sdo", name="liaiman").select_related("person").distinct()]

def role_persons_with_fixed_email(group, role_name):
    return [proxy_personify_role(r) for r in Role.objects.filter(group=group, name=role_name).select_related("person").distinct()]
    
class Entity(object):

    poc = []
    cc = []

    def __init__(self, name, obj=None):
        self.name = name
        self.obj = obj

    def get_poc(self):
        if not isinstance(self.poc, list):
            return [self.poc]
        return self.poc

    def get_cc(self, person=None):
        if not isinstance(self.cc, list):
            return [self.cc]
        return self.cc

    def get_from_cc(self, person=None):
        return []

    def needs_approval(self, person=None):
        return False

    def can_approve(self):
        return []

    def post_only(self, person, user):
        return False

    def full_user_list(self):
        return False


class IETFEntity(Entity):

    poc = FakePerson(**IETFCHAIR)
    cc = FakePerson(**IESG)

    def get_from_cc(self, person):
        result = []
        if not is_ietfchair(person):
            result.append(self.poc)
        result.append(self.cc)
        return result

    def needs_approval(self, person=None):
        if is_ietfchair(person):
            return False
        return True

    def can_approve(self):
        return [self.poc]

    def full_user_list(self):
        result = all_sdo_managers()
        result.append(get_ietf_chair())
        return result


class IABEntity(Entity):
    chair = FakePerson(**IABCHAIR)
    director = FakePerson(**IABEXECUTIVEDIRECTOR)
    poc = [chair, director]
    cc = FakePerson(**IAB)

    def get_from_cc(self, person):
        result = []
        if not is_iabchair(person):
            result.append(self.chair)
        result.append(self.cc)
        if not is_iab_executive_director(person):
            result.append(self.director)
        return result

    def needs_approval(self, person=None):
        if is_iabchair(person) or is_iab_executive_director(person):
            return False
        return True

    def can_approve(self):
        return [self.chair]

    def full_user_list(self):
        result = all_sdo_managers()
        result += [get_iab_chair(), get_iab_executive_director()]
        return result


class IRTFEntity(Entity):
    chair = FakePerson(**IRTFCHAIR)
    poc = [chair,]

    def get_from_cc(self, person):
        result = []
        return result

    def needs_approval(self, person=None):
        if is_irtfchair(person):
            return False
        return True

    def can_approve(self):
        return [self.chair]

    def full_user_list(self):
        result = [get_irtf_chair()]
        return result


class IAB_IESG_Entity(Entity):

    poc = [IABEntity.chair, IABEntity.director, FakePerson(**IETFCHAIR), FakePerson(**IESGANDIAB), ]
    cc = [FakePerson(**IAB), FakePerson(**IESG), FakePerson(**IESGANDIAB)]

    def __init__(self, name, obj=None):
        self.name = name
        self.obj = obj
        self.iab = IABEntity(name, obj)
        self.iesg = IETFEntity(name, obj)

    def get_from_cc(self, person):
        return list(set(self.iab.get_from_cc(person) + self.iesg.get_from_cc(person)))

    def needs_approval(self, person=None):
        if not self.iab.needs_approval(person):
            return False
        if not self.iesg.needs_approval(person):
            return False
        return True

    def can_approve(self):
        return list(set(self.iab.can_approve() + self.iesg.can_approve()))

    def full_user_list(self):
        return [get_ietf_chair(), get_iab_chair(), get_iab_executive_director()]
        
class AreaEntity(Entity):

    def get_poc(self):
        return role_persons_with_fixed_email(self.obj, "ad")

    def get_cc(self, person=None):
        return [FakePerson(**IETFCHAIR)]

    def get_from_cc(self, person):
        result = [p for p in role_persons_with_fixed_email(self.obj, "ad") if p != person]
        result.append(FakePerson(**IETFCHAIR))
        return result

    def needs_approval(self, person=None):
        # Check if person is an area director
        if self.obj.role_set.filter(person=person, name="ad"):
            return False
        return True

    def can_approve(self):
        return self.get_poc()

    def full_user_list(self):
        result = all_sdo_managers()
        result += self.get_poc()
        return result


class WGEntity(Entity):

    def get_poc(self):
        return role_persons_with_fixed_email(self.obj, "chair")

    def get_cc(self, person=None):
        if self.obj.parent:
            result = [p for p in role_persons_with_fixed_email(self.obj.parent, "ad") if p != person]
        else:
            result = []
        if self.obj.list_subscribe:
            result.append(FakePerson(name ='%s Discussion List' % self.obj.name,
                                     address = self.obj.list_subscribe))
        return result

    def get_from_cc(self, person):
        result = [p for p in role_persons_with_fixed_email(self.obj, "chair") if p != person]
        result += role_persons_with_fixed_email(self.obj.parent, "ad") if self.obj.parent else []
        if self.obj.list_subscribe:
            result.append(FakePerson(name ='%s Discussion List' % self.obj.name,
                                     address = self.obj.list_subscribe))
        return result

    def needs_approval(self, person=None):
        # Check if person is director of this wg area
        if self.obj.parent and self.obj.parent.role_set.filter(person=person, name="ad"):
            return False
        return True

    def can_approve(self):
        return role_persons_with_fixed_email(self.obj.parent, "ad") if self.obj.parent else []

    def full_user_list(self):
        result = all_sdo_managers()
        result += self.get_poc()
        return result


class SDOEntity(Entity):

    def get_poc(self):
        return []

    def get_cc(self, person=None):
        return role_persons_with_fixed_email(self.obj, "liaiman")

    def get_from_cc(self, person=None):
        return [p for p in role_persons_with_fixed_email(self.obj, "liaiman") if p != person]

    def post_only(self, person, user):
        if is_secretariat(user) or self.obj.role_set.filter(person=person, name="auth"):
            return False
        return True

    def full_user_list(self):
        result = role_persons_with_fixed_email(self.obj, "liaiman")
        result += role_persons_with_fixed_email(self.obj, "auth")
        return result


class EntityManager(object):

    def __init__(self, pk=None, name=None, queryset=None):
        self.pk = pk
        self.name = name
        self.queryset = queryset

    def get_entity(self, pk=None):
        return Entity(name=self.name)

    def get_managed_list(self):
        return [(self.pk, self.name)]

    def can_send_on_behalf(self, person):
        return []

    def can_approve_list(self, person):
        return []


class IETFEntityManager(EntityManager):

    def __init__(self, *args, **kwargs):
        super(IETFEntityManager, self).__init__(*args, **kwargs)
        self.entity = IETFEntity(name=self.name)

    def get_entity(self, pk=None):
        return self.entity

    def can_send_on_behalf(self, person):
        if is_ietfchair(person):
            return self.get_managed_list()
        return []

    def can_approve_list(self, person):
        if is_ietfchair(person):
            return self.get_managed_list()
        return []


class IABEntityManager(EntityManager):

    def __init__(self, *args, **kwargs):
        super(IABEntityManager, self).__init__(*args, **kwargs)
        self.entity = IABEntity(name=self.name)

    def get_entity(self, pk=None):
        return self.entity

    def can_send_on_behalf(self, person):
        if (is_iabchair(person) or
            is_iab_executive_director(person)):
            return self.get_managed_list()
        return []

    def can_approve_list(self, person):
        if (is_iabchair(person) or
            is_iab_executive_director(person)):
            return self.get_managed_list()
        return []


class IRTFEntityManager(EntityManager):

    def __init__(self, *args, **kwargs):
        super(IRTFEntityManager, self).__init__(*args, **kwargs)
        self.entity = IRTFEntity(name=self.name)

    def get_entity(self, pk=None):
        return self.entity

    def can_send_on_behalf(self, person):
        if is_irtfchair(person):
            return self.get_managed_list()
        return []

    def can_approve_list(self, person):
        if is_irtfchair(person):
            return self.get_managed_list()
        return []


class IAB_IESG_EntityManager(EntityManager):

    def __init__(self, *args, **kwargs):
        super(IAB_IESG_EntityManager, self).__init__(*args, **kwargs)
        self.entity = IAB_IESG_Entity(name=self.name)

    def get_entity(self, pk=None):
        return self.entity

    def can_send_on_behalf(self, person):
        if (is_iabchair(person) or
            is_iab_executive_director(person) or
            is_ietfchair(person)):
            return self.get_managed_list()
        return []

    def can_approve_list(self, person):
        if (is_iabchair(person) or
            is_iab_executive_director(person) or
            is_ietfchair(person)):
            return self.get_managed_list()
        return []


class AreaEntityManager(EntityManager):

    def __init__(self, pk=None, name=None, queryset=None):
        super(AreaEntityManager, self).__init__(pk, name, queryset)
        from ietf.group.proxy import Area
        if self.queryset == None:
            self.queryset = Area.active_areas()

    def get_managed_list(self, query_filter=None):
        if not query_filter:
            query_filter = {}
        return [(u'%s_%s' % (self.pk, i.pk), i.area_acronym.name) for i in self.queryset.filter(**query_filter).order_by('area_acronym__name')]

    def get_entity(self, pk=None):
        if not pk:
            return None
        try:
            obj = self.queryset.get(pk=pk)
        except self.queryset.model.DoesNotExist:
            return None
        return AreaEntity(name=obj.area_acronym.name, obj=obj)

    def can_send_on_behalf(self, person):
        query_filter = dict(role__person=person, role__name="ad")
        return self.get_managed_list(query_filter)

    def can_approve_list(self, person):
        query_filter = dict(role__person=person, role__name="ad")
        return self.get_managed_list(query_filter)


class WGEntityManager(EntityManager):

    def __init__(self, pk=None, name=None, queryset=None):
        super(WGEntityManager, self).__init__(pk, name, queryset)
        if self.queryset == None:
            from ietf.group.proxy import IETFWG, Area
            self.queryset = IETFWG.objects.filter(group_type=1, status=IETFWG.ACTIVE, areagroup__area__status=Area.ACTIVE)

    def get_managed_list(self, query_filter=None):
        if not query_filter:
            query_filter = {}
        return [(u'%s_%s' % (self.pk, i.pk), '%s - %s' % (i.group_acronym.acronym, i.group_acronym.name)) for i in self.queryset.filter(**query_filter).order_by('group_acronym__acronym')]

    def get_entity(self, pk=None):
        if not pk:
            return None
        try:
            obj = self.queryset.get(pk=pk)
        except self.queryset.model.DoesNotExist:
            return None
        return WGEntity(name=obj.group_acronym.name, obj=obj)

    def can_send_on_behalf(self, person):
        wgs = Group.objects.filter(role__person=person, role__name__in=("chair", "secretary")).values_list('pk', flat=True)
        query_filter = {'pk__in': wgs}
        return self.get_managed_list(query_filter)

    def can_approve_list(self, person):
        query_filter = dict(parent__role__person=person, parent__role__name="ad")
        return self.get_managed_list(query_filter)


class SDOEntityManager(EntityManager):

    def __init__(self, pk=None, name=None, queryset=None):
        super(SDOEntityManager, self).__init__(pk, name, queryset)
        if self.queryset == None:
            self.queryset = Group.objects.filter(type="sdo")

    def get_managed_list(self):
        return [(u'%s_%s' % (self.pk, i.pk), i.name) for i in self.queryset.order_by('name')]

    def get_entity(self, pk=None):
        if not pk:
            return None
        try:
            obj = self.queryset.get(pk=pk)
        except self.queryset.model.DoesNotExist:
            return None
        return SDOEntity(name=obj.name, obj=obj)


class IETFHierarchyManager(object):

    def __init__(self):
        self.managers = {'ietf': IETFEntityManager(pk='ietf', name=u'The IETF'),
                         'iesg': IETFEntityManager(pk='iesg', name=u'The IESG'),
                         'iab': IABEntityManager(pk='iab', name=u'The IAB'),
                         'iabiesg': IAB_IESG_EntityManager(pk='iabiesg', name=u'The IESG and the IAB'),
                         'area': AreaEntityManager(pk='area', name=u'IETF Areas'),
                         'wg': WGEntityManager(pk='wg', name=u'IETF Working Groups'),
                         'sdo': SDOEntityManager(pk='sdo', name=u'Standards Development Organizations'),
                         'othersdo': EntityManager(pk='othersdo', name=u'Other SDOs'),
                        }

    def get_entity_by_key(self, entity_id):
        if not entity_id:
            return None
        id_list = entity_id.split('_', 1)
        key = id_list[0]
        pk = None
        if len(id_list)==2:
            pk = id_list[1]
        if key not in self.managers.keys():
            return None
        return self.managers[key].get_entity(pk)

    def get_all_entities(self):
        entities = []
        for manager in self.managers.values():
            entities += manager.get_managed_list()
        return entities

    def get_all_incoming_entities(self):
        entities = []
        results = []
        for key in ['ietf', 'iesg', 'iab', 'iabiesg']:
            results += self.managers[key].get_managed_list()
        entities.append(('Main IETF Entities', results))
        entities.append(('IETF Areas', self.managers['area'].get_managed_list()))
        entities.append(('IETF Working Groups', self.managers['wg'].get_managed_list()))
        return entities

    def get_all_outgoing_entities(self):
        entities = [(self.managers['sdo'].name, self.managers['sdo'].get_managed_list())]
        entities += [(self.managers['othersdo'].name, self.managers['othersdo'].get_managed_list())]
        return entities

    def get_entities_for_person(self, person):
        entities = []
        results = []
        for key in ['ietf', 'iesg', 'iab', 'iabiesg']:
            results += self.managers[key].can_send_on_behalf(person)
        if results:
            entities.append(('Main IETF Entities', results))
        areas = self.managers['area'].can_send_on_behalf(person)
        if areas:
            entities.append(('IETF Areas', areas))
        wgs = self.managers['wg'].can_send_on_behalf(person)
        if wgs:
            entities.append(('IETF Working Groups', wgs))
        return entities

    def get_all_can_approve_codes(self, person):
        entities = []
        for key in ['ietf', 'iesg', 'iab', 'iabiesg']:
            entities += self.managers[key].can_approve_list(person)
        entities += self.managers['area'].can_approve_list(person)
        entities += self.managers['wg'].can_approve_list(person)
        return [i[0] for i in entities]


IETFHM = IETFHierarchyManager()
