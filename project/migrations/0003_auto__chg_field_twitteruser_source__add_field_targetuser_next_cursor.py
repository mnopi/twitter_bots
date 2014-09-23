# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'TwitterUser.source'
        db.alter_column(u'project_twitteruser', 'source', self.gf('django.db.models.fields.CharField')(max_length=160, null=True))
        # Adding field 'TargetUser.next_cursor'
        db.add_column(u'project_targetuser', 'next_cursor',
                      self.gf('django.db.models.fields.PositiveIntegerField')(default=0),
                      keep_default=False)


    def backwards(self, orm):

        # Changing field 'TwitterUser.source'
        db.alter_column(u'project_twitteruser', 'source', self.gf('django.db.models.fields.CharField')(default='', max_length=160))
        # Deleting field 'TargetUser.next_cursor'
        db.delete_column(u'project_targetuser', 'next_cursor')


    models = {
        u'project.follower': {
            'Meta': {'object_name': 'Follower'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'target_user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'followers'", 'to': u"orm['project.TargetUser']"}),
            'twitter_user': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'follower'", 'unique': 'True', 'to': u"orm['project.TwitterUser']"})
        },
        u'project.project': {
            'Meta': {'object_name': 'Project'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        u'project.targetuser': {
            'Meta': {'object_name': 'TargetUser'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'next_cursor': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'projects': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'target_users'", 'symmetrical': 'False', 'to': u"orm['project.Project']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'})
        },
        u'project.tweet': {
            'Meta': {'object_name': 'Tweet'},
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mentioned_users': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'mentions'", 'symmetrical': 'False', 'to': u"orm['project.TwitterUser']"}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tweets'", 'to': u"orm['project.Project']"}),
            'tweet_msg': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['project.TweetMsg']"})
        },
        u'project.tweetmsg': {
            'Meta': {'object_name': 'TweetMsg'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tweet_msgs'", 'to': u"orm['project.Project']"}),
            'text': ('django.db.models.fields.CharField', [], {'max_length': '160', 'blank': 'True'})
        },
        u'project.twitteruser': {
            'Meta': {'object_name': 'TwitterUser'},
            'city': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True', 'blank': 'True'}),
            'created_date': ('django.db.models.fields.DateTimeField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'default': "'en'", 'max_length': '2', 'blank': 'True'}),
            'latitude': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'longitude': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'}),
            'twitter_id': ('django.db.models.fields.BigIntegerField', [], {'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '160', 'blank': 'True'})
        }
    }

    complete_apps = ['project']