# -*- coding: utf-8 -*-
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        import re

        events = orm.DocEvent.objects.filter(type="changed_document").filter(
            models.Q(desc__istartswith="State changed to ") |
            models.Q(desc__istartswith="State Changes to ") |
            models.Q(desc__istartswith="Sub state has been changed to ") |
            models.Q(desc__istartswith="State has been changed to ")
        ).select_related("doc").values("id", "desc", "doc", "doc__type")

        re_state_changed = re.compile(r"(?:State (?:has been changed|changed|Changes) to <b>(?P<to>.*)</b> from (<b>|)(?P<from>.*)(</b> by|)|Sub state has been changed to (?P<tosub>.*) from (?P<fromsub>.*))")

        state_map = {
            "draft-iesg": {},
            "charter": {},
            "statchg": {},
            "conflrev": {},
            }

        state_types = dict((t.slug, t) for t in orm.StateType.objects.all())

        for t in state_map:
            for s in orm.State.objects.filter(type=t).select_related("type"):
                state_map[t][s.name] = s
                if t == "draft-iesg":
                    state_map[t][str(s.order)] = s

        state_map["draft-iesg"]["Last Call Issued"] = state_map["draft-iesg"]["In Last Call"]
        state_map["draft-iesg"]["Wait for Last Call to End"] = state_map["draft-iesg"]["In Last Call"]
        state_map["draft-iesg"]["Wait for Writeup"] = state_map["draft-iesg"]["Waiting for Writeup"]
        state_map["draft-iesg"]["Ready for Telechat"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["Defer"] = state_map["draft-iesg"]["IESG Evaluation - Defer"]
        state_map["draft-iesg"]["Final AD Go-Ahead"] = state_map["draft-iesg"]["Waiting for AD Go-Ahead"]
        state_map["draft-iesg"]["Do not publish - Info sent"] = state_map["draft-iesg"]["DNP-announcement to be sent"]
        state_map["draft-iesg"]["AD re-review"] = state_map["draft-iesg"]["AD Evaluation"]
        state_map["draft-iesg"]["Pre AD Evaluation"] = state_map["draft-iesg"]["AD Evaluation"]
        state_map["draft-iesg"]["Approved - Info sent"] = state_map["draft-iesg"]["Approved-announcement sent"]
        state_map["draft-iesg"]["Approved But Comments Needed"] = state_map["draft-iesg"]["Approved-announcement to be sent"]
        state_map["draft-iesg"]["Approved"] = state_map["draft-iesg"]["Approved-announcement sent"]
        state_map["draft-iesg"]["Requested"] = state_map["draft-iesg"]["Publication Requested"]
        state_map["draft-iesg"]["Reading List"] = state_map["draft-iesg"]["AD is watching"]
        state_map["draft-iesg"]["Discuss Cleared, Wait for approval"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["Discuss Writing Received"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["Discuss fix received"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["Evaluation: Discuss"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["In WG"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["New Version Coming"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["New Version Needed (WG/Author)"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["Token@wg or Author"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["WG/Author"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["AD Followup"] = state_map["draft-iesg"]["IESG Evaluation"]
        state_map["draft-iesg"]["AD to write --Don't publish"] = state_map["draft-iesg"]["DNP-waiting for AD note"]

        events = list(events)

        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("start transaction")

        for e in events:
            desc = e["desc"]
            m = re_state_changed.match(desc)
            if not m:
                print "FAIL", e["id"], desc
            else:
                to = (m.group("to") or "")
                i = to.find("::")
                if i != -1:
                    to = to[:i]

                i = to.find("  --")
                if i != -1:
                    to = to[:i]

                i = to.find(" (ends ")
                if i != -1:
                    to = to[:i]

                if "IESG: Dead" in to:
                    to = u"Dead"

                to = to.strip()

                t = e["doc__type"]
                if t == "draft":
                    t = "draft-iesg"

                state = state_map[t].get(to)
                state_type = state_types[t]

                # insert StateDocEvent with the DocEvent as base,
                # doesn't appear to be possible to do this through
                # Django, so fallback to raw SQL
                cursor.execute("insert into doc_statedocevent (docevent_ptr_id, state_type_id, state_id) values (%s, %s, %s)"
                               % (e["id"], "'" + state_type.pk + "'", state.pk if state else "NULL"))
                orm.DocEvent.objects.filter(pk=e["id"]).update(type="changed_state")

                #if to not in state_map[t]:
                #    print e["doc"], e["id"], to, desc

        cursor.execute("commit")

    def backwards(self, orm):
        pass

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
        u'doc.ballotdocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'BallotDocEvent', '_ormbases': [u'doc.DocEvent']},
            'ballot_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.BallotType']"}),
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'doc.ballotpositiondocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'BallotPositionDocEvent', '_ormbases': [u'doc.DocEvent']},
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'ballot': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['doc.BallotDocEvent']", 'null': 'True'}),
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'comment_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discuss': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'discuss_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'pos': ('django.db.models.fields.related.ForeignKey', [], {'default': "'norecord'", 'to': u"orm['name.BallotPositionName']"})
        },
        u'doc.ballottype': {
            'Meta': {'ordering': "['order']", 'object_name': 'BallotType'},
            'doc_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocTypeName']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'positions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['name.BallotPositionName']", 'symmetrical': 'False', 'blank': 'True'}),
            'question': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'doc.consensusdocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'ConsensusDocEvent', '_ormbases': [u'doc.DocEvent']},
            'consensus': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'doc.deletedevent': {
            'Meta': {'object_name': 'DeletedEvent'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'json': ('django.db.models.fields.TextField', [], {}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'})
        },
        u'doc.docalias': {
            'Meta': {'object_name': 'DocAlias'},
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        u'doc.docevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'DocEvent'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'desc': ('django.db.models.fields.TextField', [], {}),
            'doc': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'db_index': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'doc.dochistory': {
            'Meta': {'object_name': 'DocHistory'},
            'abstract': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'ad_dochistory_set'", 'null': 'True', 'to': u"orm['person.Person']"}),
            'authors': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['person.Email']", 'symmetrical': 'False', 'through': u"orm['doc.DocHistoryAuthor']", 'blank': 'True'}),
            'doc': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'history_set'", 'to': u"orm['doc.Document']"}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'external_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'intended_std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IntendedStdLevelName']", 'null': 'True', 'blank': 'True'}),
            'internal_comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'note': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'notify': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1', 'blank': 'True'}),
            'pages': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'related': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.DocAlias']", 'symmetrical': 'False', 'through': u"orm['doc.RelatedDocHistory']", 'blank': 'True'}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'shepherd_dochistory_set'", 'null': 'True', 'to': u"orm['person.Person']"}),
            'states': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.State']", 'symmetrical': 'False', 'blank': 'True'}),
            'std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.StdLevelName']", 'null': 'True', 'blank': 'True'}),
            'stream': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.StreamName']", 'null': 'True', 'blank': 'True'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['name.DocTagName']", 'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocTypeName']", 'null': 'True', 'blank': 'True'})
        },
        u'doc.dochistoryauthor': {
            'Meta': {'ordering': "['document', 'order']", 'object_name': 'DocHistoryAuthor'},
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Email']"}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.DocHistory']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {})
        },
        u'doc.docreminder': {
            'Meta': {'object_name': 'DocReminder'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'due': ('django.db.models.fields.DateTimeField', [], {}),
            'event': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.DocEvent']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocReminderTypeName']"})
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
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'shepherd_document_set'", 'null': 'True', 'to': u"orm['person.Person']"}),
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
        u'doc.initialreviewdocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'InitialReviewDocEvent', '_ormbases': [u'doc.DocEvent']},
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        u'doc.lastcalldocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'LastCallDocEvent', '_ormbases': [u'doc.DocEvent']},
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        u'doc.newrevisiondocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'NewRevisionDocEvent', '_ormbases': [u'doc.DocEvent']},
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '16'})
        },
        u'doc.relateddochistory': {
            'Meta': {'object_name': 'RelatedDocHistory'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'relationship': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocRelationshipName']"}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.DocHistory']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'reversely_related_document_history_set'", 'to': u"orm['doc.DocAlias']"})
        },
        u'doc.relateddocument': {
            'Meta': {'object_name': 'RelatedDocument'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'relationship': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocRelationshipName']"}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.DocAlias']"})
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
        u'doc.statedocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'StateDocEvent', '_ormbases': [u'doc.DocEvent']},
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.State']", 'null': 'True', 'blank': 'True'}),
            'state_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.StateType']"})
        },
        u'doc.statetype': {
            'Meta': {'object_name': 'StateType'},
            'label': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '30', 'primary_key': 'True'})
        },
        u'doc.telechatdocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'TelechatDocEvent', '_ormbases': [u'doc.DocEvent']},
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'returning_item': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'telechat_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'})
        },
        u'doc.writeupdocevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'WriteupDocEvent', '_ormbases': [u'doc.DocEvent']},
            u'docevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['doc.DocEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'group.group': {
            'Meta': {'object_name': 'Group'},
            'acronym': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '40'}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']", 'null': 'True', 'blank': 'True'}),
            'charter': ('django.db.models.fields.related.OneToOneField', [], {'blank': 'True', 'related_name': "'chartered_group'", 'unique': 'True', 'null': 'True', 'to': u"orm['doc.Document']"}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
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
        u'name.ballotpositionname': {
            'Meta': {'ordering': "['order']", 'object_name': 'BallotPositionName'},
            'blocking': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.docrelationshipname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocRelationshipName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'revname': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.docremindertypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocReminderTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.doctagname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTagName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.doctypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.groupstatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.grouptypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.intendedstdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'IntendedStdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.stdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.streamname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StreamName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
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

    complete_apps = ['doc']
    symmetrical = True
