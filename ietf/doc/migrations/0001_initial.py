# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'StateType'
        db.create_table('doc_statetype', (
            ('slug', self.gf('django.db.models.fields.CharField')(max_length=30, primary_key=True)),
            ('label', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('doc', ['StateType'])

        # Adding model 'State'
        db.create_table('doc_state', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.StateType'])),
            ('slug', self.gf('django.db.models.fields.SlugField')(max_length=50, db_index=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('used', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('desc', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('order', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('doc', ['State'])

        # Adding M2M table for field next_states on 'State'
        db.create_table('doc_state_next_states', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('from_state', models.ForeignKey(orm['doc.state'], null=False)),
            ('to_state', models.ForeignKey(orm['doc.state'], null=False))
        ))
        db.create_unique('doc_state_next_states', ['from_state_id', 'to_state_id'])

        # Adding model 'RelatedDocument'
        db.create_table('doc_relateddocument', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('source', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.Document'])),
            ('target', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.DocAlias'])),
            ('relationship', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.DocRelationshipName'])),
        ))
        db.send_create_signal('doc', ['RelatedDocument'])

        # Adding model 'DocumentAuthor'
        db.create_table('doc_documentauthor', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('document', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.Document'])),
            ('author', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Email'])),
            ('order', self.gf('django.db.models.fields.IntegerField')(default=1)),
        ))
        db.send_create_signal('doc', ['DocumentAuthor'])

        # Adding model 'Document'
        db.create_table('doc_document', (
            ('time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.DocTypeName'], null=True, blank=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('stream', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.StreamName'], null=True, blank=True)),
            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['group.Group'], null=True, blank=True)),
            ('abstract', self.gf('django.db.models.fields.TextField')()),
            ('rev', self.gf('django.db.models.fields.CharField')(max_length=16, blank=True)),
            ('pages', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('order', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('intended_std_level', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.IntendedStdLevelName'], null=True, blank=True)),
            ('std_level', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.StdLevelName'], null=True, blank=True)),
            ('ad', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='ad_document_set', null=True, to=orm['person.Person'])),
            ('shepherd', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='shepherd_document_set', null=True, to=orm['person.Person'])),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('notify', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('external_url', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('note', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('internal_comments', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, primary_key=True)),
        ))
        db.send_create_signal('doc', ['Document'])

        # Adding M2M table for field states on 'Document'
        db.create_table('doc_document_states', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('document', models.ForeignKey(orm['doc.document'], null=False)),
            ('state', models.ForeignKey(orm['doc.state'], null=False))
        ))
        db.create_unique('doc_document_states', ['document_id', 'state_id'])

        # Adding M2M table for field tags on 'Document'
        db.create_table('doc_document_tags', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('document', models.ForeignKey(orm['doc.document'], null=False)),
            ('doctagname', models.ForeignKey(orm['name.doctagname'], null=False))
        ))
        db.create_unique('doc_document_tags', ['document_id', 'doctagname_id'])

        # Adding model 'RelatedDocHistory'
        db.create_table('doc_relateddochistory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('source', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.DocHistory'])),
            ('target', self.gf('django.db.models.fields.related.ForeignKey')(related_name='reversely_related_document_history_set', to=orm['doc.DocAlias'])),
            ('relationship', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.DocRelationshipName'])),
        ))
        db.send_create_signal('doc', ['RelatedDocHistory'])

        # Adding model 'DocHistoryAuthor'
        db.create_table('doc_dochistoryauthor', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('document', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.DocHistory'])),
            ('author', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Email'])),
            ('order', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal('doc', ['DocHistoryAuthor'])

        # Adding model 'DocHistory'
        db.create_table('doc_dochistory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.DocTypeName'], null=True, blank=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('stream', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.StreamName'], null=True, blank=True)),
            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['group.Group'], null=True, blank=True)),
            ('abstract', self.gf('django.db.models.fields.TextField')()),
            ('rev', self.gf('django.db.models.fields.CharField')(max_length=16, blank=True)),
            ('pages', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('order', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('intended_std_level', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.IntendedStdLevelName'], null=True, blank=True)),
            ('std_level', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.StdLevelName'], null=True, blank=True)),
            ('ad', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='ad_dochistory_set', null=True, to=orm['person.Person'])),
            ('shepherd', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='shepherd_dochistory_set', null=True, to=orm['person.Person'])),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('notify', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('external_url', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('note', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('internal_comments', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('doc', self.gf('django.db.models.fields.related.ForeignKey')(related_name='history_set', to=orm['doc.Document'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('doc', ['DocHistory'])

        # Adding M2M table for field states on 'DocHistory'
        db.create_table('doc_dochistory_states', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('dochistory', models.ForeignKey(orm['doc.dochistory'], null=False)),
            ('state', models.ForeignKey(orm['doc.state'], null=False))
        ))
        db.create_unique('doc_dochistory_states', ['dochistory_id', 'state_id'])

        # Adding M2M table for field tags on 'DocHistory'
        db.create_table('doc_dochistory_tags', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('dochistory', models.ForeignKey(orm['doc.dochistory'], null=False)),
            ('doctagname', models.ForeignKey(orm['name.doctagname'], null=False))
        ))
        db.create_unique('doc_dochistory_tags', ['dochistory_id', 'doctagname_id'])

        # Adding model 'DocAlias'
        db.create_table('doc_docalias', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('document', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.Document'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
        ))
        db.send_create_signal('doc', ['DocAlias'])

        # Adding model 'DocReminder'
        db.create_table('doc_docreminder', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('event', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.DocEvent'])),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.DocReminderTypeName'])),
            ('due', self.gf('django.db.models.fields.DateTimeField')()),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('doc', ['DocReminder'])

        # Adding model 'DocEvent'
        db.create_table('doc_docevent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Person'])),
            ('doc', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.Document'])),
            ('desc', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('doc', ['DocEvent'])

        # Adding model 'NewRevisionDocEvent'
        db.create_table('doc_newrevisiondocevent', (
            ('docevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['doc.DocEvent'], unique=True, primary_key=True)),
            ('rev', self.gf('django.db.models.fields.CharField')(max_length=16)),
        ))
        db.send_create_signal('doc', ['NewRevisionDocEvent'])

        # Adding model 'BallotPositionDocEvent'
        db.create_table('doc_ballotpositiondocevent', (
            ('docevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['doc.DocEvent'], unique=True, primary_key=True)),
            ('ad', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Person'])),
            ('pos', self.gf('django.db.models.fields.related.ForeignKey')(default='norecord', to=orm['name.BallotPositionName'])),
            ('discuss', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('discuss_time', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('comment', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('comment_time', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('doc', ['BallotPositionDocEvent'])

        # Adding model 'WriteupDocEvent'
        db.create_table('doc_writeupdocevent', (
            ('docevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['doc.DocEvent'], unique=True, primary_key=True)),
            ('text', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal('doc', ['WriteupDocEvent'])

        # Adding model 'LastCallDocEvent'
        db.create_table('doc_lastcalldocevent', (
            ('docevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['doc.DocEvent'], unique=True, primary_key=True)),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('doc', ['LastCallDocEvent'])

        # Adding model 'TelechatDocEvent'
        db.create_table('doc_telechatdocevent', (
            ('docevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['doc.DocEvent'], unique=True, primary_key=True)),
            ('telechat_date', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('returning_item', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('doc', ['TelechatDocEvent'])

        # Adding model 'GroupBallotPositionDocEvent'
        db.create_table('doc_groupballotpositiondocevent', (
            ('docevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['doc.DocEvent'], unique=True, primary_key=True)),
            ('ad', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Person'])),
            ('pos', self.gf('django.db.models.fields.related.ForeignKey')(default='norecord', to=orm['name.GroupBallotPositionName'])),
            ('block_comment', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('block_comment_time', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('comment', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('comment_time', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('doc', ['GroupBallotPositionDocEvent'])

        # Adding model 'InitialReviewDocEvent'
        db.create_table('doc_initialreviewdocevent', (
            ('docevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['doc.DocEvent'], unique=True, primary_key=True)),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('doc', ['InitialReviewDocEvent'])


    def backwards(self, orm):
        
        # Deleting model 'StateType'
        db.delete_table('doc_statetype')

        # Deleting model 'State'
        db.delete_table('doc_state')

        # Removing M2M table for field next_states on 'State'
        db.delete_table('doc_state_next_states')

        # Deleting model 'RelatedDocument'
        db.delete_table('doc_relateddocument')

        # Deleting model 'DocumentAuthor'
        db.delete_table('doc_documentauthor')

        # Deleting model 'Document'
        db.delete_table('doc_document')

        # Removing M2M table for field states on 'Document'
        db.delete_table('doc_document_states')

        # Removing M2M table for field tags on 'Document'
        db.delete_table('doc_document_tags')

        # Deleting model 'RelatedDocHistory'
        db.delete_table('doc_relateddochistory')

        # Deleting model 'DocHistoryAuthor'
        db.delete_table('doc_dochistoryauthor')

        # Deleting model 'DocHistory'
        db.delete_table('doc_dochistory')

        # Removing M2M table for field states on 'DocHistory'
        db.delete_table('doc_dochistory_states')

        # Removing M2M table for field tags on 'DocHistory'
        db.delete_table('doc_dochistory_tags')

        # Deleting model 'DocAlias'
        db.delete_table('doc_docalias')

        # Deleting model 'DocReminder'
        db.delete_table('doc_docreminder')

        # Deleting model 'DocEvent'
        db.delete_table('doc_docevent')

        # Deleting model 'NewRevisionDocEvent'
        db.delete_table('doc_newrevisiondocevent')

        # Deleting model 'BallotPositionDocEvent'
        db.delete_table('doc_ballotpositiondocevent')

        # Deleting model 'WriteupDocEvent'
        db.delete_table('doc_writeupdocevent')

        # Deleting model 'LastCallDocEvent'
        db.delete_table('doc_lastcalldocevent')

        # Deleting model 'TelechatDocEvent'
        db.delete_table('doc_telechatdocevent')

        # Deleting model 'GroupBallotPositionDocEvent'
        db.delete_table('doc_groupballotpositiondocevent')

        # Deleting model 'InitialReviewDocEvent'
        db.delete_table('doc_initialreviewdocevent')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'doc.ballotpositiondocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'BallotPositionDocEvent', '_ormbases': ['doc.DocEvent']},
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Person']"}),
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'comment_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discuss': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'discuss_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'pos': ('django.db.models.fields.related.ForeignKey', [], {'default': "'norecord'", 'to': "orm['name.BallotPositionName']"})
        },
        'doc.docalias': {
            'Meta': {'object_name': 'DocAlias'},
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.Document']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'doc.docevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'DocEvent'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Person']"}),
            'desc': ('django.db.models.fields.TextField', [], {}),
            'doc': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.Document']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'doc.dochistory': {
            'Meta': {'object_name': 'DocHistory'},
            'abstract': ('django.db.models.fields.TextField', [], {}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'ad_dochistory_set'", 'null': 'True', 'to': "orm['person.Person']"}),
            'authors': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['person.Email']", 'symmetrical': 'False', 'through': "orm['doc.DocHistoryAuthor']", 'blank': 'True'}),
            'doc': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'history_set'", 'to': "orm['doc.Document']"}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'external_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'intended_std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.IntendedStdLevelName']", 'null': 'True', 'blank': 'True'}),
            'internal_comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'note': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'notify': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'pages': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'related': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['doc.DocAlias']", 'symmetrical': 'False', 'through': "orm['doc.RelatedDocHistory']", 'blank': 'True'}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'shepherd_dochistory_set'", 'null': 'True', 'to': "orm['person.Person']"}),
            'states': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['doc.State']", 'symmetrical': 'False', 'blank': 'True'}),
            'std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.StdLevelName']", 'null': 'True', 'blank': 'True'}),
            'stream': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.StreamName']", 'null': 'True', 'blank': 'True'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['name.DocTagName']", 'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.DocTypeName']", 'null': 'True', 'blank': 'True'})
        },
        'doc.dochistoryauthor': {
            'Meta': {'ordering': "['document', 'order']", 'object_name': 'DocHistoryAuthor'},
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Email']"}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.DocHistory']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {})
        },
        'doc.docreminder': {
            'Meta': {'object_name': 'DocReminder'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'due': ('django.db.models.fields.DateTimeField', [], {}),
            'event': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.DocEvent']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.DocReminderTypeName']"})
        },
        'doc.document': {
            'Meta': {'object_name': 'Document'},
            'abstract': ('django.db.models.fields.TextField', [], {}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'ad_document_set'", 'null': 'True', 'to': "orm['person.Person']"}),
            'authors': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['person.Email']", 'symmetrical': 'False', 'through': "orm['doc.DocumentAuthor']", 'blank': 'True'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'external_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            'intended_std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.IntendedStdLevelName']", 'null': 'True', 'blank': 'True'}),
            'internal_comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'primary_key': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'notify': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'pages': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'related': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'reversely_related_document_set'", 'blank': 'True', 'through': "orm['doc.RelatedDocument']", 'to': "orm['doc.DocAlias']"}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'shepherd_document_set'", 'null': 'True', 'to': "orm['person.Person']"}),
            'states': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['doc.State']", 'symmetrical': 'False', 'blank': 'True'}),
            'std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.StdLevelName']", 'null': 'True', 'blank': 'True'}),
            'stream': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.StreamName']", 'null': 'True', 'blank': 'True'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['name.DocTagName']", 'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.DocTypeName']", 'null': 'True', 'blank': 'True'})
        },
        'doc.documentauthor': {
            'Meta': {'ordering': "['document', 'order']", 'object_name': 'DocumentAuthor'},
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Email']"}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.Document']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        },
        'doc.groupballotpositiondocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'GroupBallotPositionDocEvent', '_ormbases': ['doc.DocEvent']},
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Person']"}),
            'block_comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'block_comment_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'comment_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'pos': ('django.db.models.fields.related.ForeignKey', [], {'default': "'norecord'", 'to': "orm['name.GroupBallotPositionName']"})
        },
        'doc.initialreviewdocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'InitialReviewDocEvent', '_ormbases': ['doc.DocEvent']},
            'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'doc.lastcalldocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'LastCallDocEvent', '_ormbases': ['doc.DocEvent']},
            'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'doc.newrevisiondocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'NewRevisionDocEvent', '_ormbases': ['doc.DocEvent']},
            'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '16'})
        },
        'doc.relateddochistory': {
            'Meta': {'object_name': 'RelatedDocHistory'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'relationship': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.DocRelationshipName']"}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.DocHistory']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'reversely_related_document_history_set'", 'to': "orm['doc.DocAlias']"})
        },
        'doc.relateddocument': {
            'Meta': {'object_name': 'RelatedDocument'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'relationship': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.DocRelationshipName']"}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.Document']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.DocAlias']"})
        },
        'doc.state': {
            'Meta': {'ordering': "['type', 'order']", 'object_name': 'State'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'next_states': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'previous_states'", 'symmetrical': 'False', 'to': "orm['doc.State']"}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.StateType']"}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'doc.statetype': {
            'Meta': {'object_name': 'StateType'},
            'label': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '30', 'primary_key': 'True'})
        },
        'doc.telechatdocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'TelechatDocEvent', '_ormbases': ['doc.DocEvent']},
            'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'returning_item': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'telechat_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'})
        },
        'doc.writeupdocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'WriteupDocEvent', '_ormbases': ['doc.DocEvent']},
            'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'group.group': {
            'Meta': {'object_name': 'Group'},
            'acronym': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '40', 'db_index': 'True'}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Person']", 'null': 'True', 'blank': 'True'}),
            'charter': ('django.db.models.fields.related.OneToOneField', [], {'blank': 'True', 'related_name': "'chartered_group'", 'unique': 'True', 'null': 'True', 'to': "orm['doc.Document']"}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'list_archive': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'list_email': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'list_subscribe': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.GroupStateName']", 'null': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.GroupTypeName']", 'null': 'True'}),
            'unused_states': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['doc.State']", 'symmetrical': 'False', 'blank': 'True'}),
            'unused_tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['name.DocTagName']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'name.ballotpositionname': {
            'Meta': {'ordering': "['order']", 'object_name': 'BallotPositionName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.docrelationshipname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocRelationshipName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.docremindertypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocReminderTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.doctagname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTagName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.doctypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.groupballotpositionname': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupBallotPositionName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.groupstatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.grouptypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.intendedstdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'IntendedStdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.stdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'name.streamname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StreamName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'person.email': {
            'Meta': {'object_name': 'Email'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'address': ('django.db.models.fields.CharField', [], {'max_length': '64', 'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Person']", 'null': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        'person.person': {
            'Meta': {'object_name': 'Person'},
            'address': ('django.db.models.fields.TextField', [], {'max_length': '255', 'blank': 'True'}),
            'affiliation': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'ascii': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'ascii_short': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['doc']
