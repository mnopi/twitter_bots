# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Proxy'
        db.create_table(u'core_proxy', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('proxy', self.gf('django.db.models.fields.CharField')(max_length=21, blank=True)),
            ('proxy_provider', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('is_unavailable_for_registration', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('date_unavailable_for_registration', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('is_unavailable_for_use', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('date_unavailable_for_use', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('is_phone_required', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('date_phone_required', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'core', ['Proxy'])

        # Adding field 'TwitterBot.proxy'
        db.add_column(u'core_twitterbot', 'proxy',
                      self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='twitter_bots', null=True, to=orm['core.Proxy']),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting model 'Proxy'
        db.delete_table(u'core_proxy')

        # Deleting field 'TwitterBot.proxy'
        db.delete_column(u'core_twitterbot', 'proxy_id')


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
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'core.proxy': {
            'Meta': {'object_name': 'Proxy'},
            'date_phone_required': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_unavailable_for_registration': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_unavailable_for_use': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_phone_required': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_unavailable_for_registration': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_unavailable_for_use': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'proxy': ('django.db.models.fields.CharField', [], {'max_length': '21', 'blank': 'True'}),
            'proxy_provider': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        },
        u'core.twitterbot': {
            'Meta': {'object_name': 'TwitterBot'},
            'birth_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_suspended_email': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_suspended_twitter': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.CharField', [], {'max_length': '256', 'blank': 'True'}),
            'email_registered_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'gender': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '1'}),
            'has_fast_mode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_manually_registered': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'it_works': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'must_verify_phone': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'password_email': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'password_twitter': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'proxy': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'twitter_bots'", 'null': 'True', 'to': u"orm['core.Proxy']"}),
            'random_mouse_paths': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'random_offsets': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'real_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'twitter_avatar_completed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'twitter_bio_completed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'twitter_confirmed_email_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'twitter_registered_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_agent': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'webdriver': ('django.db.models.fields.CharField', [], {'default': "'FI'", 'max_length': '2'})
        },
        u'core.user': {
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
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        }
    }

    complete_apps = ['core']