# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'TwitterUser.full_name'
        db.add_column(u'project_twitteruser', 'full_name',
                      self.gf('django.db.models.fields.CharField')(max_length=160, null=True),
                      keep_default=False)

        # Adding field 'TwitterUser.geo_enabled'
        db.add_column(u'project_twitteruser', 'geo_enabled',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'TwitterUser.time_zone'
        db.add_column(u'project_twitteruser', 'time_zone',
                      self.gf('django.db.models.fields.CharField')(max_length=50, null=True),
                      keep_default=False)

        # Adding field 'TwitterUser.last_tweet_date'
        db.add_column(u'project_twitteruser', 'last_tweet_date',
                      self.gf('django.db.models.fields.DateTimeField')(null=True),
                      keep_default=False)

        # Adding field 'TwitterUser.followers_count'
        db.add_column(u'project_twitteruser', 'followers_count',
                      self.gf('django.db.models.fields.PositiveIntegerField')(null=True),
                      keep_default=False)

        # Adding field 'TwitterUser.tweets_count'
        db.add_column(u'project_twitteruser', 'tweets_count',
                      self.gf('django.db.models.fields.PositiveIntegerField')(null=True),
                      keep_default=False)

        # Adding field 'TwitterUser.verified'
        db.add_column(u'project_twitteruser', 'verified',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


        # Changing field 'TwitterUser.source'
        db.alter_column(u'project_twitteruser', 'source', self.gf('django.db.models.fields.PositiveIntegerField')())

    def backwards(self, orm):
        # Deleting field 'TwitterUser.full_name'
        db.delete_column(u'project_twitteruser', 'full_name')

        # Deleting field 'TwitterUser.geo_enabled'
        db.delete_column(u'project_twitteruser', 'geo_enabled')

        # Deleting field 'TwitterUser.time_zone'
        db.delete_column(u'project_twitteruser', 'time_zone')

        # Deleting field 'TwitterUser.last_tweet_date'
        db.delete_column(u'project_twitteruser', 'last_tweet_date')

        # Deleting field 'TwitterUser.followers_count'
        db.delete_column(u'project_twitteruser', 'followers_count')

        # Deleting field 'TwitterUser.tweets_count'
        db.delete_column(u'project_twitteruser', 'tweets_count')

        # Deleting field 'TwitterUser.verified'
        db.delete_column(u'project_twitteruser', 'verified')


        # Changing field 'TwitterUser.source'
        db.alter_column(u'project_twitteruser', 'source', self.gf('django.db.models.fields.CharField')(max_length=160, null=True))

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
            'created_date': ('django.db.models.fields.DateTimeField', [], {}),
            'followers_count': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'full_name': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True'}),
            'geo_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'default': "'en'", 'max_length': '2', 'blank': 'True'}),
            'last_tweet_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'latitude': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'longitude': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'source': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'time_zone': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True'}),
            'tweets_count': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'twitter_id': ('django.db.models.fields.BigIntegerField', [], {}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '160'}),
            'verified': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        }
    }

    complete_apps = ['project']