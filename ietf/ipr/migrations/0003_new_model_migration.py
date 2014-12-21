# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.v2 import DataMigration

#import datetime
import email
import os
import re
import urllib2
#import pytz
from collections import namedtuple
from time import mktime, strptime
from urlparse import urlparse

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string


class Migration(DataMigration):
    depends_on = (
        ("name", "0029_add_ipr_names"),
    )
    
    # ---------------------------
    # Private Helper Functions
    # ---------------------------
    def _decode_safely(self,data):
        """Return data decoded according to charset, but do so safely."""
        try:
            return unicode(data,'latin1')
        except (UnicodeDecodeError, LookupError):
            return unicode(data,'latin1',errors='replace')
        
    def _get_url(self,url):
        """Returns contents of URL as unicode"""
        try:
            fp = urllib2.urlopen(url)
            data = fp.read()
            fp.close()
        except Exception:
            return ''
        return self._decode_safely(data)
    
    def _get_legacy_submitter(self,ipr):
        """Returns tuple of submitter_name, submitter_email if submitter info
        is found in the legacy text file"""
        match = self.LEGACY_URL_PATTERN.match(ipr.legacy_url_0)
        if not match:
            return (None,None)
        filename = match.groups()[0]
        path = os.path.join(settings.IPR_DOCUMENT_PATH,filename)
        try:
            with open(path) as file:
                for line in file:
                    if re.search('^Submitter:',line):
                        text = line[10:]
                        return email.utils.parseaddr(text)
        except:
            pass

        return (None,None)
    
    def _create_comment(self,old, new, url_field, orm, title_field=None):
        """Create an IprEvent Comment given the legacy info.
        If called with legacy_url_0 field created use LegacyMigrationIprEvent type"""
        url = getattr(old,url_field)
        if title_field:
            title_text = u"{}: {}\n".format(title_field,getattr(old,title_field))
        else:
            title_text = u""

        if url.endswith('pdf'):
            # TODO: check for file ending in txt
            data = ''
        else:
            data = self._get_url(url)

        # Fix up missing scheme and hostname for links in message
        if re.search('href=[\'"]/', data):
            scheme, netloc, _, _, _, _ = urlparse(url)
            data = re.sub('(href=[\'"])/', r'\1%s://%s/'%(scheme,netloc), data)

        # create event objects
        desc = title_text + u"From: {}\n\n{}".format(url,data)
        if url_field == 'legacy_url_0':
            klass = orm.LegacyMigrationIprEvent
        else:
            klass = orm.IprEvent


        obj = klass.objects.create(type=self.legacy_event,
                                by=self.system,
                                disclosure=new,
                                desc=desc)
        obj.time = old.submitted_date
        obj.save()


    def _combine_fields(self,obj,fields):
        """Returns fields combined into one string.  Uses field_mapping to apply
        extra formatting for some fields."""
        data = u""
        for field in fields:
            val = getattr(obj,field)
            if val:
                if field in self.field_mapping:
                    data += u"{}: {}\n".format(self.field_mapping[field],val)
                else:
                    data += u"{}\n".format(val)
        return data
    
    def _handle_contacts(self,old,new,orm):
        """
        In some cases, due to bug?, one declaration may have multiple contacts of the same
        type (see pk=2185), only process once.
        """
        seen = []
        for contact in old.contact.all():
            if contact.contact_type in seen:
                continue
            seen.append(contact.contact_type)
            fields = self.contact_type_mapping[contact.contact_type]
            info = self._combine_fields(contact,['title',
                                           'department',
                                           'address1',
                                           'address2',
                                           'telephone',
                                           'fax'])

            fields = self.ContactFields(*fields)
            if hasattr(new,fields.name):
                setattr(new,fields.name,contact.name)
            if hasattr(new,fields.info):
                setattr(new,fields.info,info)
            if hasattr(new,fields.email):
                setattr(new,fields.email,contact.email)
    
    def _handle_docs(self,old,new,orm):
        """Create IprDocRel relationships"""
        iprdocaliases = old.iprdocalias_set.all()
        for iprdocalias in iprdocaliases:
            orm.IprDocRel.objects.create(disclosure=new.iprdisclosurebase_ptr,
                                     document=iprdocalias.doc_alias,
                                     sections=old.document_sections,
                                     revisions=iprdocalias.rev)

        # check other_designations for related documents
        matches = self.DRAFT_PATTERN.findall(old.other_designations)
        for name,rev in map(self._split_revision,matches):
            try:
                draft = orm['doc.Document'].objects.get(type='draft',name=name)
            except ObjectDoesNotExist:
                print "WARN: couldn't find other_designation: {}".format(name)
                continue
            if not orm.IprDocRel.objects.filter(disclosure=new.iprdisclosurebase_ptr,document__in=draft.docalias_set.all()):
                orm.IprDocRel.objects.create(disclosure=new.iprdisclosurebase_ptr,
                                         document=draft.docalias_set.get(name=draft.name),
                                         sections=old.document_sections,
                                         revisions=rev)
                                     
    def _handle_licensing(self,old,new,orm):
        """Map licensing information into new object.  ThirdParty disclosures
        do not have any.  The "limited to standards track only" designators are not
        included in the new models.  Users will need to include this in the notes
        sections.  Therefore lic_opt_?_sub options are converted to license text"""
        if old.lic_opt_a_sub or old.lic_opt_b_sub or old.lic_opt_c_sub:
            extra = "This licensing declaration is limited solely to standards-track IETF documents"
        else:
            extra = ''
        if isinstance(new, (orm.GenericIprDisclosure,orm.NonDocSpecificIprDisclosure)):
            context = {'option':old.licensing_option,'info':old.comments,'extra':extra}
            new.statement = render_to_string("ipr/migration_licensing.txt",context)
        elif isinstance(new, orm.HolderIprDisclosure):
            new.licensing = self.licensing_mapping[old.licensing_option]
            new.licensing_comments = old.comments
            if extra:
                new.licensing_comments = new.licensing_comments + '\n\n' + extra
            new.submitter_claims_all_terms_disclosed = old.lic_checkbox

    def _handle_legacy_fields(self,old,new,orm):
        """Get contents of URLs in legacy fields and save in an IprEvent"""
        # legacy_url_0
        if old.legacy_url_0:
            self._create_comment(old,new,'legacy_url_0',orm)
            if not new.submitter_email:
                name,email = self._get_legacy_submitter(old)
                if name or email:
                    new.submitter_name = name
                    new.submitter_email = email

        # legacy_url_1
        # Titles that start with "update" will be converted to RelatedIpr later
        if old.legacy_title_1 and not old.legacy_title_1.startswith('Update'):
            self._create_comment(old,new,'legacy_url_1',orm,title_field='legacy_title_1')

        # legacy_url_2

    def _handle_notification(self,rec,orm):
        """Map IprNotification to IprEvent and Message objects.
    
        NOTE: some IprNotifications contain non-ascii text causing
        email.message_from_string() to fail, hence the workaround
        """
        parts = rec.notification.split('\r\n\r\n',1)
        msg = email.message_from_string(parts[0])
        msg.set_payload(parts[1])
        disclosure = orm.IprDisclosureBase.objects.get(pk=rec.ipr.pk)
        type = orm['name.IprEventTypeName'].objects.get(slug='msgout')
        subject = msg['subject']
        subject = (subject[:252] + '...') if len(subject) > 255 else subject
        time_string = rec.date_sent.strftime('%Y-%m-%d ') + rec.time_sent
        struct = strptime(time_string,'%Y-%m-%d %H:%M:%S')
        # Use this when we start using TZ-aware datetimes
        #timestamp = datetime.datetime.fromtimestamp(mktime(struct), pytz.timezone('US/Pacific'))
        timestamp = datetime.datetime.fromtimestamp(mktime(struct))
        message = orm['message.Message'].objects.create(
            by = self.system,
            subject = subject,
            frm = msg.get('from'),
            to = msg.get('to'),
            cc = msg.get('cc'),
            body = msg.get_payload(),
            time = timestamp,
        )
        event = orm.IprEvent.objects.create(
            type = type,
            by = self.system,
            disclosure = disclosure,
            desc = 'Sent Message',
            message = message,
        )
        # go back fix IprEvent.time
        event.time = timestamp
        event.save()
    
    def _handle_patent_info(self,old,new,orm):
        """Map patent info.  patent_info and applies_to_all are mutually exclusive"""
        # TODO: do anything with old.applies_to_all?
        if not hasattr(new, 'patent_info'):
            return None
        data = self._combine_fields(old,['patents','date_applied','country','notes'])
        new.patent_info = data
        if old.is_pending == 1:
            new.has_patent_pending = True
        
    def _handle_rel(self,iprdetail,orm):
        """Create RelatedIpr relationships based on legacy data"""
        new = orm.IprDisclosureBase.objects.get(pk=iprdetail.pk)

        # build relationships from IprUpdates
        for iprupdate in iprdetail.updates.all():
            target = orm.IprDisclosureBase.objects.get(pk=iprupdate.updated.pk)
            orm.RelatedIpr.objects.create(source=new,
                                            target=target,
                                            relationship=self.UPDATES)

        # build relationships from legacy_url_1
        url = iprdetail.legacy_url_1
        title = iprdetail.legacy_title_1
        if title and title.startswith('Updated by'):
            # get object id from URL
            match = self.URL_PATTERN.match(url)
            if match:
                id = match.groups()[0]
                try:
                    source = orm.IprDisclosureBase.objects.get(pk=id)
                except:
                    print "No record for {}".format(url)
                    return
                try:
                    orm.RelatedIpr.objects.get(source=source,target=new,relationship=self.UPDATES)
                except ObjectDoesNotExist:
                    orm.RelatedIpr.objects.create(source=source,target=new,relationship=self.UPDATES)

    def _split_revision(self,text):
        if self.DRAFT_HAS_REVISION_PATTERN.match(text):
            return text[:-3],text[-2:]
        else:
            return text,None
    
    # ---------------------------
    # Migrations Functions
    # ---------------------------
    
    def forwards(self, orm):
        "Write your forwards methods here."
        # Note: Don't use "from appname.models import ModelName". 
        # Use orm.ModelName to refer to models in this application,
        # and orm['appname.ModelName'] for models in other applications.
        self.system = orm['person.Person'].objects.get(name="(System)")
        self.ContactFields = namedtuple('ContactFields',['name','info','email'])
        self.DRAFT_PATTERN = re.compile(r'draft-[a-zA-Z0-9\-]+')
        self.DRAFT_HAS_REVISION_PATTERN = re.compile(r'.*-[0-9]{2}')
        self.URL_PATTERN = re.compile(r'https?://datatracker.ietf.org/ipr/(\d{1,4})/')
        self.LEGACY_URL_PATTERN = re.compile(r'https?://www.ietf.org/ietf-ftp/IPR/(.*)$')
        self.SEQUENCE_PATTERN = re.compile(r'.+ \(\d\)$')
        self.UPDATES = orm['name.DocRelationshipName'].objects.get(slug='updates')
        self.legacy_event = orm['name.IprEventTypeName'].objects.get(slug='legacy')
        self.field_mapping = {'telephone':'T','fax':'F','date_applied':'Date','country':'Country','notes':'\nNotes'}
        self.contact_type_name_mapping = { 1:'holder',2:'ietfer',3:'submitter' }
        self.licensing_mapping = { 0:orm['name.IprLicenseTypeName'].objects.get(slug='none-selected'),
            1:orm['name.IprLicenseTypeName'].objects.get(slug='no-license'),
            2:orm['name.IprLicenseTypeName'].objects.get(slug='royalty-free'),
            3:orm['name.IprLicenseTypeName'].objects.get(slug='reasonable'),
            4:orm['name.IprLicenseTypeName'].objects.get(slug='provided-later'),
            5:orm['name.IprLicenseTypeName'].objects.get(slug='unwilling-to-commit'),
            6:orm['name.IprLicenseTypeName'].objects.get(slug='see-below'),
            None:orm['name.IprLicenseTypeName'].objects.get(slug='none-selected') }
        self.states_mapping = { 0:orm['name.IprDisclosureStateName'].objects.get(slug='pending'),
            1:orm['name.IprDisclosureStateName'].objects.get(slug='posted'),
            2:orm['name.IprDisclosureStateName'].objects.get(slug='rejected'),
            3:orm['name.IprDisclosureStateName'].objects.get(slug='removed') }
        self.contact_type_mapping = { 1:('holder_contact_name','holder_contact_info','holder_contact_email'),
            2:('ietfer_name','ietfer_contact_info','ietfer_contact_email'),
            3:('submitter_name','submitter_info','submitter_email') }
                         
        all = orm.IprDetail.objects.all().order_by('ipr_id')
        for rec in all:
            # Defaults
            kwargs = { 'by':self.system,
                       'holder_legal_name':(rec.legal_name or "").strip(),
                       'id':rec.pk,
                       'notes':rec.other_notes,
                       'other_designations':rec.other_designations,
                       'state':self.states_mapping[rec.status],
                       'title':rec.title,
                       'time':datetime.datetime.now() }

            # Determine Type.
            if rec.third_party:
                klass = orm.ThirdPartyIprDisclosure
            elif rec.generic:
                if rec.patents:
                    klass = orm.NonDocSpecificIprDisclosure
                else:
                    klass = orm.GenericIprDisclosure
            else:
                klass = orm.HolderIprDisclosure
                kwargs['licensing'] = self.licensing_mapping[rec.licensing_option]
            
            new = klass.objects.create(**kwargs)

            new.time = rec.submitted_date
            self._handle_licensing(rec,new,orm)
            self._handle_patent_info(rec,new,orm)
            self._handle_contacts(rec,new,orm)
            self._handle_legacy_fields(rec,new,orm)
            self._handle_docs(rec,new,orm)

            # strip sequence from title
            if self.SEQUENCE_PATTERN.match(new.title):
                new.title = new.title[:-4]

            # save changes to disclosure object
            new.save()

            # create IprEvent:submitted
            event = orm.IprEvent.objects.create(type_id='submitted',
                                            by=self.system,
                                            disclosure=new,
                                            desc='IPR Disclosure Submitted')
            # need to set time after object creation to override auto_now_add
            event.time = rec.submitted_date
            event.save()

            if rec.status == 1:
                # create IprEvent:posted
                event = orm.IprEvent.objects.create(type_id='posted',
                                                by=self.system,
                                                disclosure=new,
                                                desc='IPR Disclosure Posted')
                # need to set time after object creation to override auto_now_add
                event.time = rec.submitted_date
                event.save()
            
        # pass two, create relationships
        for rec in all:
            self._handle_rel(rec,orm)
        
        # migrate IprNotifications
        for rec in orm.IprNotification.objects.all():
            self._handle_notification(rec,orm)
        
        # print stats
        print "-------------------------------"
        for klass in (orm.HolderIprDisclosure,
                      orm.ThirdPartyIprDisclosure,
                      orm.NonDocSpecificIprDisclosure,
                      orm.GenericIprDisclosure):
            print "{}: {}".format(klass.__name__,klass.objects.count())
        print "Total records: {}".format(orm.IprDisclosureBase.objects.count())

    def backwards(self, orm):
        "Write your backwards methods here."
        orm.IprDisclosureBase.objects.all().delete()
        orm.IprEvent.objects.all().delete()
        orm.RelatedIpr.objects.all().delete()
        orm.IprDocRel.objects.all().delete()

    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'doc.docalias': {
            'Meta': {'object_name': 'DocAlias'},
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        u'doc.document': {
            'Meta': {'object_name': 'Document'},
            'abstract': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'ad_document_set'", 'null': 'True', 'to': u"orm['person.Person']"}),
            'authors': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['person.Email']", 'symmetrical': 'False', 'through': u"orm['doc.DocumentAuthor']", 'blank': 'True'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'external_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            'intended_std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IntendedStdLevelName']", 'null': 'True', 'blank': 'True'}),
            'internal_comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'primary_key': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'notify': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1', 'blank': 'True'}),
            'pages': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'shepherd_document_set'", 'null': 'True', 'to': u"orm['person.Email']"}),
            'states': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.State']", 'symmetrical': 'False', 'blank': 'True'}),
            'std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.StdLevelName']", 'null': 'True', 'blank': 'True'}),
            'stream': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.StreamName']", 'null': 'True', 'blank': 'True'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['name.DocTagName']", 'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocTypeName']", 'null': 'True', 'blank': 'True'})
        },
        u'doc.documentauthor': {
            'Meta': {'ordering': "['document', 'order']", 'object_name': 'DocumentAuthor'},
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Email']"}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        },
        u'doc.state': {
            'Meta': {'ordering': "['type', 'order']", 'object_name': 'State'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'next_states': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'previous_states'", 'blank': 'True', 'to': u"orm['doc.State']"}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.StateType']"}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'doc.statetype': {
            'Meta': {'object_name': 'StateType'},
            'label': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '30', 'primary_key': 'True'})
        },
        u'group.group': {
            'Meta': {'object_name': 'Group'},
            'acronym': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '40'}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']", 'null': 'True', 'blank': 'True'}),
            'charter': ('django.db.models.fields.related.OneToOneField', [], {'blank': 'True', 'related_name': "'chartered_group'", 'unique': 'True', 'null': 'True', 'to': u"orm['doc.Document']"}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'list_archive': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'list_email': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'list_subscribe': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.GroupStateName']", 'null': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.GroupTypeName']", 'null': 'True'}),
            'unused_states': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.State']", 'symmetrical': 'False', 'blank': 'True'}),
            'unused_tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['name.DocTagName']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'ipr.genericiprdisclosure': {
            'Meta': {'object_name': 'GenericIprDisclosure', '_ormbases': [u'ipr.IprDisclosureBase']},
            'holder_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'holder_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'holder_contact_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'iprdisclosurebase_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'unique': 'True', 'primary_key': 'True'}),
            'statement': ('django.db.models.fields.TextField', [], {})
        },
        u'ipr.holderiprdisclosure': {
            'Meta': {'object_name': 'HolderIprDisclosure', '_ormbases': [u'ipr.IprDisclosureBase']},
            'has_patent_pending': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'holder_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'holder_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'holder_contact_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'ietfer_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'ietfer_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ietfer_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            u'iprdisclosurebase_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'unique': 'True', 'primary_key': 'True'}),
            'licensing': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IprLicenseTypeName']"}),
            'licensing_comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'patent_info': ('django.db.models.fields.TextField', [], {}),
            'submitter_claims_all_terms_disclosed': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'ipr.iprcontact': {
            'Meta': {'object_name': 'IprContact'},
            'address1': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'address2': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'contact_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'contact_type': ('django.db.models.fields.IntegerField', [], {}),
            'department': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '255'}),
            'fax': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'ipr': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'contact'", 'to': u"orm['ipr.IprDetail']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'telephone': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        u'ipr.iprdetail': {
            'Meta': {'object_name': 'IprDetail'},
            'applies_to_all': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_column': "'selectowned'", 'blank': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'comply': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'date_applied': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'document_sections': ('django.db.models.fields.TextField', [], {'max_length': '255', 'db_column': "'disclouser_identify'", 'blank': 'True'}),
            'generic': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id_document_tag': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'ipr_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_pending': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_column': "'selecttype'", 'blank': 'True'}),
            'legacy_title_1': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'additional_old_title1'", 'blank': 'True'}),
            'legacy_title_2': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'additional_old_title2'", 'blank': 'True'}),
            'legacy_url_0': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'old_ipr_url'", 'blank': 'True'}),
            'legacy_url_1': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'additional_old_url1'", 'blank': 'True'}),
            'legacy_url_2': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'additional_old_url2'", 'blank': 'True'}),
            'legal_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_column': "'p_h_legal_name'"}),
            'lic_checkbox': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lic_opt_a_sub': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'lic_opt_b_sub': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'lic_opt_c_sub': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'licensing_option': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'db_column': "'p_notes'", 'blank': 'True'}),
            'other_designations': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'other_notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'patents': ('django.db.models.fields.TextField', [], {'max_length': '255', 'db_column': "'p_applications'"}),
            'rfc_number': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'submitted_date': ('django.db.models.fields.DateField', [], {'blank': 'True'}),
            'third_party': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_column': "'document_title'", 'blank': 'True'}),
            'update_notified_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'})
        },
        u'ipr.iprdisclosurebase': {
            'Meta': {'object_name': 'IprDisclosureBase'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'compliant': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'docs': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.DocAlias']", 'through': u"orm['ipr.IprDocRel']", 'symmetrical': 'False'}),
            'holder_legal_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'other_designations': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'rel': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'through': u"orm['ipr.RelatedIpr']", 'symmetrical': 'False'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IprDisclosureStateName']"}),
            'submitter_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'submitter_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        u'ipr.iprdocalias': {
            'Meta': {'object_name': 'IprDocAlias'},
            'doc_alias': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.DocAlias']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipr': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ipr.IprDetail']"}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True'})
        },
        u'ipr.iprdocrel': {
            'Meta': {'object_name': 'IprDocRel'},
            'disclosure': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ipr.IprDisclosureBase']"}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.DocAlias']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'revisions': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'sections': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'ipr.iprevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'IprEvent'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'desc': ('django.db.models.fields.TextField', [], {}),
            'disclosure': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ipr.IprDisclosureBase']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_reply_to': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'irtoevents'", 'null': 'True', 'to': u"orm['message.Message']"}),
            'message': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'msgevents'", 'null': 'True', 'to': u"orm['message.Message']"}),
            'response_due': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IprEventTypeName']"})
        },
        u'ipr.iprnotification': {
            'Meta': {'object_name': 'IprNotification'},
            'date_sent': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipr': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ipr.IprDetail']"}),
            'notification': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'time_sent': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'})
        },
        u'ipr.iprupdate': {
            'Meta': {'object_name': 'IprUpdate'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipr': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'updates'", 'to': u"orm['ipr.IprDetail']"}),
            'processed': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'status_to_be': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'updated_by'", 'db_column': "'updated'", 'to': u"orm['ipr.IprDetail']"})
        },
        u'ipr.legacymigrationiprevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'LegacyMigrationIprEvent', '_ormbases': [u'ipr.IprEvent']},
            u'iprevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprEvent']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'ipr.nondocspecificiprdisclosure': {
            'Meta': {'object_name': 'NonDocSpecificIprDisclosure', '_ormbases': [u'ipr.IprDisclosureBase']},
            'has_patent_pending': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'holder_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'holder_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'holder_contact_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'iprdisclosurebase_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'unique': 'True', 'primary_key': 'True'}),
            'patent_info': ('django.db.models.fields.TextField', [], {}),
            'statement': ('django.db.models.fields.TextField', [], {})
        },
        u'ipr.relatedipr': {
            'Meta': {'object_name': 'RelatedIpr'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'relationship': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocRelationshipName']"}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'relatedipr_source_set'", 'to': u"orm['ipr.IprDisclosureBase']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'relatedipr_target_set'", 'to': u"orm['ipr.IprDisclosureBase']"})
        },
        u'ipr.thirdpartyiprdisclosure': {
            'Meta': {'object_name': 'ThirdPartyIprDisclosure', '_ormbases': [u'ipr.IprDisclosureBase']},
            'has_patent_pending': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ietfer_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'ietfer_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ietfer_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'iprdisclosurebase_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'unique': 'True', 'primary_key': 'True'}),
            'patent_info': ('django.db.models.fields.TextField', [], {})
        },
        u'message.message': {
            'Meta': {'ordering': "['time']", 'object_name': 'Message'},
            'bcc': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'body': ('django.db.models.fields.TextField', [], {}),
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'cc': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.CharField', [], {'default': "'text/plain'", 'max_length': '255', 'blank': 'True'}),
            'frm': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'related_docs': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.Document']", 'symmetrical': 'False', 'blank': 'True'}),
            'related_groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['group.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'reply_to': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'subject': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'to': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        u'message.sendqueue': {
            'Meta': {'ordering': "['time']", 'object_name': 'SendQueue'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['message.Message']"}),
            'note': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'send_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'sent_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'})
        },
        u'name.ballotpositionname': {
            'Meta': {'ordering': "['order']", 'object_name': 'BallotPositionName'},
            'blocking': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.constraintname': {
            'Meta': {'ordering': "['order']", 'object_name': 'ConstraintName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'penalty': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.dbtemplatetypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DBTemplateTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.docrelationshipname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocRelationshipName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'revname': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.docremindertypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocReminderTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.doctagname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTagName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.doctypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.draftsubmissionstatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DraftSubmissionStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'next_states': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'previous_states'", 'blank': 'True', 'to': u"orm['name.DraftSubmissionStateName']"}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.feedbacktypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'FeedbackTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.groupmilestonestatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupMilestoneStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.groupstatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.grouptypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.intendedstdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'IntendedStdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.iprdisclosurestatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'IprDisclosureStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.ipreventtypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'IprEventTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.iprlicensetypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'IprLicenseTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.liaisonstatementpurposename': {
            'Meta': {'ordering': "['order']", 'object_name': 'LiaisonStatementPurposeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.meetingtypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'MeetingTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.nomineepositionstatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'NomineePositionStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.rolename': {
            'Meta': {'ordering': "['order']", 'object_name': 'RoleName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.roomresourcename': {
            'Meta': {'ordering': "['order']", 'object_name': 'RoomResourceName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.sessionstatusname': {
            'Meta': {'ordering': "['order']", 'object_name': 'SessionStatusName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.stdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.streamname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StreamName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.timeslottypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'TimeSlotTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'person.email': {
            'Meta': {'object_name': 'Email'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'address': ('django.db.models.fields.CharField', [], {'max_length': '64', 'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']", 'null': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        u'person.person': {
            'Meta': {'object_name': 'Person'},
            'address': ('django.db.models.fields.TextField', [], {'max_length': '255', 'blank': 'True'}),
            'affiliation': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'ascii': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'ascii_short': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['auth.User']", 'unique': 'True', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['message', 'name', 'ipr']
    symmetrical = True
