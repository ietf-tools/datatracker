import datetime

from django.db.models import Q


class DisplayField(object):

    codename = ''
    description = ''

    def get_value(self, document):
        return None


class FilenameField(DisplayField):
    codename = 'filename'
    description = 'I-D filename'

    def get_value(self, document):
        return document.name


class TitleField(DisplayField):
    codename = 'title'
    description = 'I-D title'

    def get_value(self, document):
        return document.title


class DateField(DisplayField):
    codename = 'date'
    description = 'Date of current I-D'

    def get_value(self, document):
        dates = document.documentchangedates_set.all()
        if dates and dates[0].new_version_date:
            return dates[0].new_version_date.strftime('%Y-%m-%d')
        return document.time.strftime('%Y-%m-%d')


class StatusField(DisplayField):
    codename = 'status'
    description = 'Status in the IETF process'

    def get_value(self, document):
        return document.state


class WGField(DisplayField):
    codename = 'wg_rg'
    description = 'Associated WG or RG'

    def get_value(self, document):
        return document.group or ''


class ADField(DisplayField):
    codename = 'ad'
    description = 'Associated AD, if any'

    def get_value(self, document):
        return document.ad or ''


class OneDayField(DisplayField):
    codename = '1_day'
    description = 'Changed within the last 1 day'

    def get_value(self, document):
        now = datetime.datetime.now()
        last = now - datetime.timedelta(days=1)
        if document.documentchangedates_set.filter(
            Q(new_version_date__gte=last) |
            Q(normal_change_date__gte=last)):
            return '&#10004;'
        return ''


class TwoDaysField(DisplayField):
    codename = '2_days'
    description = 'Changed within the last 2 days'

    def get_value(self, document):
        now = datetime.datetime.now()
        last = now - datetime.timedelta(days=2)
        if document.documentchangedates_set.filter(
            Q(new_version_date__gte=last) |
            Q(normal_change_date__gte=last)):
            return '&#10004;'
        return ''


class SevenDaysField(DisplayField):
    codename = '7_days'
    description = 'Changed within the last 7 days'

    def get_value(self, document):
        now = datetime.datetime.now()
        last = now - datetime.timedelta(days=7)
        if document.documentchangedates_set.filter(
            Q(new_version_date__gte=last) |
            Q(normal_change_date__gte=last)):
            return '&#10004;'
        return ''


TYPES_OF_DISPLAY_FIELDS = [(i.codename, i.description) for i in DisplayField.__subclasses__()]


class SortMethod(object):
    codename = ''
    description = ''

    def get_sort_field(self):
        return 'pk'


class FilenameSort(SortMethod):
    codename = 'by_filename'
    description = 'Alphabetical by I-D filename and RFC number'

    def get_sort_field(self):
        return 'name'


class TitleSort(SortMethod):
    codename = 'by_title'
    description = 'Alphabetical by document title'

    def get_sort_field(self):
        return 'title'


class WGSort(SortMethod):
    codename = 'by_wg'
    description = 'Alphabetical by associated WG'

    def get_sort_field(self):
        return 'group__name'


class PublicationSort(SortMethod):
    codename = 'date_publication'
    description = 'Date of publication of current version of the document'

    def get_sort_field(self):
        return 'documentchangedates__new_version_date'


class ChangeSort(SortMethod):
    codename = 'recent_change'
    description = 'Date of most recent change of status of any type'

    def get_sort_field(self):
        return 'documentchangedates__normal_change_date'


class SignificantSort(SortMethod):
    codename = 'recent_significant'
    description = 'Date of most recent significant change of status'

    def get_sort_field(self):
        return 'documentchangedates__significant_change_date'


TYPES_OF_SORT = [(i.codename, i.description) for i in SortMethod.__subclasses__()]
