import factory
import datetime

from ietf.review.models import ReviewTeamSettings, ReviewRequest

class ReviewTeamSettingsFactory(factory.DjangoModelFactory):
    class Meta:
        model = ReviewTeamSettings

    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='dir')
    
class ReviewRequestFactory(factory.DjangoModelFactory):
    class Meta:
        model = ReviewRequest

    state_id = 'requested'
    type_id = 'lc'
    doc = factory.SubFactory('ietf.doc.factories.DocumentFactory',type_id='draft')
    team = factory.SubFactory('ietf.group.factories.ReviewTeamFactory',type_id='dir')   
    deadline = datetime.datetime.today()+datetime.timedelta(days=14)
    requested_by = factory.SubFactory('ietf.person.factories.PersonFactory')

