import re, os
from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from django.conf import settings
from ietf.proceedings.models import WgProceedingsActivities
from ietf.proceedings.models import Slide, WgAgenda, Proceeding
from datetime import datetime, time

class LatestWgProceedingsActivity(Feed):
    feed_type = Atom1Feed
    link = "/foo"
    description = "foobar"
    language = "en"
    feed_url = "/feed/wg-proceedings/"
    base_url = "http://www3.ietf.org/proceedings/"

    def items(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            objs = []
            from redesign.doc.models import Document
            for doc in Document.objects.filter(type__in=("agenda", "minutes", "slides")).order_by('-time')[:60]:
                obj = dict(
                    title=doc.type_id,
                    group_acronym=doc.name.split("-")[2],
                    date=doc.time,
                    link=self.base_url + os.path.join(doc.get_file_path(), doc.external_url)[len(settings.AGENDA_PATH):],
                    author=""
                    )
                objs.append(obj)

            return objs
        
        objs = []
        for act in WgProceedingsActivities.objects.order_by('-act_date')[:60]:
            obj = {}

            m = re.match("^slide, '(.*)', was uploaded$", act.activity)
            if m:
                obj['title'] = m.group(1) 
                obj['title'] = re.sub("[^ -~]+", "", obj['title'])
                slides = Slide.objects.filter(meeting=act.meeting).filter(slide_name=m.group(1)).filter(group_acronym_id=act.group_acronym_id)
                if len(slides) == 1:
                    obj['link'] = self.base_url + slides[0].file_loc()

            m = re.match("^agenda was uploaded$", act.activity)
            if m:
                obj['title'] = "agenda";
                agendas = WgAgenda.objects.filter(meeting=act.meeting).filter(group_acronym_id=act.group_acronym_id)
                if len(agendas) == 1:
                    dir = Proceeding.objects.get(meeting_num=act.meeting).dir_name
                    obj['link'] = self.base_url + dir + "/agenda/" + agendas[0].filename

            if len(obj) > 0:
                try:
                    act.irtf = False
                    obj['group_acronym'] = act.acronym()
                except:
                    act.irtf = True
                    try:
                        obj['group_acronym'] = act.acronym()
                    except:
                        obj['group_acronym'] = "?"
                obj['date'] = datetime.combine(act.act_date, time(int(act.act_time[0:2]), int(act.act_time[3:5]), int(act.act_time[6:8])))
                obj['author'] = str(act.act_by)
                objs.append(obj)
                
        return objs
       
    def get_object(self, bits):
        obj = {}
        obj['title'] = "This is the title";
        return obj

    def title(self, obj):
        return "Meeting Materials Activity"

    def item_link(self, item):
        if 'link' in item:
            return item['link']
        else:
            return ""
        
    def item_pubdate(self, item):
        return item['date']

    def item_author_name(self, item):
        return item['author']

    def item_author_email(self, item):
        return None;
