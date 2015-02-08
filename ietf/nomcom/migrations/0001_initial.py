from south.db import db
from south.v2 import SchemaMigration

from django.db import models

class Migration(SchemaMigration):

    depends_on = (
        ("name", "0013_add_dbtemplates_types"),
    )

    def forwards(self, orm):
        
        # Adding model 'ReminderDates'
        db.create_table('nomcom_reminderdates', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date', self.gf('django.db.models.fields.DateField')()),
            ('nomcom', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.NomCom'])),
        ))
        db.send_create_signal('nomcom', ['ReminderDates'])

        # Adding model 'NomCom'
        db.create_table('nomcom_nomcom', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('public_key', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['group.Group'])),
            ('send_questionnaire', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('reminder_interval', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal('nomcom', ['NomCom'])

        # Adding model 'Nomination'
        db.create_table('nomcom_nomination', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('position', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.Position'])),
            ('candidate_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('candidate_email', self.gf('django.db.models.fields.EmailField')(max_length=255)),
            ('candidate_phone', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('nominee', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.Nominee'])),
            ('comments', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.Feedback'])),
            ('nominator_email', self.gf('django.db.models.fields.EmailField')(max_length=75, blank=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('time', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('nomcom', ['Nomination'])

        # Adding model 'Nominee'
        db.create_table('nomcom_nominee', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('email', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Email'])),
            ('duplicated', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.Nominee'], null=True, blank=True)),
            ('nomcom', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.NomCom'])),
        ))
        db.send_create_signal('nomcom', ['Nominee'])

        # Adding unique constraint on 'Nominee', fields ['email', 'nomcom']
        db.create_unique('nomcom_nominee', ['email_id', 'nomcom_id'])

        # Adding model 'NomineePosition'
        db.create_table('nomcom_nomineeposition', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('position', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.Position'])),
            ('nominee', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.Nominee'])),
            ('state', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.NomineePositionState'])),
            ('time', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('nomcom', ['NomineePosition'])

        # Adding unique constraint on 'NomineePosition', fields ['position', 'nominee']
        db.create_unique('nomcom_nomineeposition', ['position_id', 'nominee_id'])

        # Adding model 'Position'
        db.create_table('nomcom_position', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('nomcom', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.NomCom'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('description', self.gf('django.db.models.fields.TextField')()),
            ('initial_text', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('requirement', self.gf('django.db.models.fields.related.ForeignKey')(related_name='requirement', null=True, to=orm['dbtemplate.DBTemplate'])),
            ('questionnaire', self.gf('django.db.models.fields.related.ForeignKey')(related_name='questionnaire', null=True, to=orm['dbtemplate.DBTemplate'])),
            ('is_open', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('incumbent', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Email'])),
        ))
        db.send_create_signal('nomcom', ['Position'])

        # Adding model 'Feedback'
        db.create_table('nomcom_feedback', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('nomcom', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['nomcom.NomCom'])),
            ('author', self.gf('django.db.models.fields.EmailField')(max_length=75, blank=True)),
            ('comments', self.gf('ietf.nomcom.fields.EncryptedTextField')()),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.FeedbackType'], null=True, blank=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True, blank=True)),
            ('time', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('nomcom', ['Feedback'])

        # Adding M2M table for field positions on 'Feedback'
        db.create_table('nomcom_feedback_positions', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('feedback', models.ForeignKey(orm['nomcom.feedback'], null=False)),
            ('position', models.ForeignKey(orm['nomcom.position'], null=False))
        ))
        db.create_unique('nomcom_feedback_positions', ['feedback_id', 'position_id'])

        # Adding M2M table for field nominees on 'Feedback'
        db.create_table('nomcom_feedback_nominees', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('feedback', models.ForeignKey(orm['nomcom.feedback'], null=False)),
            ('nominee', models.ForeignKey(orm['nomcom.nominee'], null=False))
        ))
        db.create_unique('nomcom_feedback_nominees', ['feedback_id', 'nominee_id'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'NomineePosition', fields ['position', 'nominee']
        db.delete_unique('nomcom_nomineeposition', ['position_id', 'nominee_id'])

        # Removing unique constraint on 'Nominee', fields ['email', 'nomcom']
        db.delete_unique('nomcom_nominee', ['email_id', 'nomcom_id'])

        # Deleting model 'ReminderDates'
        db.delete_table('nomcom_reminderdates')

        # Deleting model 'NomCom'
        db.delete_table('nomcom_nomcom')

        # Deleting model 'Nomination'
        db.delete_table('nomcom_nomination')

        # Deleting model 'Nominee'
        db.delete_table('nomcom_nominee')

        # Deleting model 'NomineePosition'
        db.delete_table('nomcom_nomineeposition')

        # Deleting model 'Position'
        db.delete_table('nomcom_position')

        # Deleting model 'Feedback'
        db.delete_table('nomcom_feedback')

        # Removing M2M table for field positions on 'Feedback'
        db.delete_table('nomcom_feedback_positions')

        # Removing M2M table for field nominees on 'Feedback'
        db.delete_table('nomcom_feedback_nominees')


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
        'dbtemplate.dbtemplate': {
            'Meta': {'object_name': 'DBTemplate'},
            'content': ('django.db.models.fields.TextField', [], {}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'path': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.DBTemplateTypeName']"}),
            'variables': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        'doc.docalias': {
            'Meta': {'object_name': 'DocAlias'},
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['doc.Document']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'doc.document': {
            'Meta': {'object_name': 'Document'},
            'abstract': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
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
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1', 'blank': 'True'}),
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
        'name.dbtemplatetypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DBTemplateTypeName'},
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
        'name.feedbacktype': {
            'Meta': {'ordering': "['order']", 'object_name': 'FeedbackType'},
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
        'name.nomineepositionstate': {
            'Meta': {'ordering': "['order']", 'object_name': 'NomineePositionState'},
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
        'nomcom.feedback': {
            'Meta': {'ordering': "['time']", 'object_name': 'Feedback'},
            'author': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'comments': ('ietf.nomcom.fields.EncryptedTextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nomcom': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.NomCom']"}),
            'nominees': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['nomcom.Nominee']", 'null': 'True', 'blank': 'True'}),
            'positions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['nomcom.Position']", 'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.FeedbackType']", 'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'nomcom.nomcom': {
            'Meta': {'object_name': 'NomCom'},
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['group.Group']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'public_key': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'reminder_interval': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'send_questionnaire': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'nomcom.nomination': {
            'Meta': {'object_name': 'Nomination'},
            'candidate_email': ('django.db.models.fields.EmailField', [], {'max_length': '255'}),
            'candidate_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'candidate_phone': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'comments': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.Feedback']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nominator_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'nominee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.Nominee']"}),
            'position': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.Position']"}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'nomcom.nominee': {
            'Meta': {'unique_together': "(('email', 'nomcom'),)", 'object_name': 'Nominee'},
            'duplicated': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.Nominee']", 'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Email']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nomcom': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.NomCom']"}),
            'nominee_position': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['nomcom.Position']", 'through': "orm['nomcom.NomineePosition']", 'symmetrical': 'False'})
        },
        'nomcom.nomineeposition': {
            'Meta': {'ordering': "['nominee']", 'unique_together': "(('position', 'nominee'),)", 'object_name': 'NomineePosition'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nominee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.Nominee']"}),
            'position': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.Position']"}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['name.NomineePositionState']"}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        'nomcom.position': {
            'Meta': {'object_name': 'Position'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'incumbent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['person.Email']"}),
            'initial_text': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'is_open': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'nomcom': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.NomCom']"}),
            'questionnaire': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'questionnaire'", 'null': 'True', 'to': "orm['dbtemplate.DBTemplate']"}),
            'requirement': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'requirement'", 'null': 'True', 'to': "orm['dbtemplate.DBTemplate']"})
        },
        'nomcom.reminderdates': {
            'Meta': {'object_name': 'ReminderDates'},
            'date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nomcom': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['nomcom.NomCom']"})
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

    complete_apps = ['nomcom']
