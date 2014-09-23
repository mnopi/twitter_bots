# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding M2M table for field target_users on 'Project'
        m2m_table_name = db.shorten_name(u'project_project_target_users')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('project', models.ForeignKey(orm[u'project.project'], null=False)),
            ('targetuser', models.ForeignKey(orm[u'project.targetuser'], null=False))
        ))
        db.create_unique(m2m_table_name, ['project_id', 'targetuser_id'])

        # Removing M2M table for field projects on 'TargetUser'
        db.delete_table(db.shorten_name(u'project_targetuser_projects'))


        # Changing field 'TargetUser.next_cursor'
        db.alter_column(u'project_targetuser', 'next_cursor', self.gf('django.db.models.fields.BigIntegerField')(null=True))

    def backwards(self, orm):
        # Removing M2M table for field target_users on 'Project'
        db.delete_table(db.shorten_name(u'project_project_target_users'))

        # Adding M2M table for field projects on 'TargetUser'
        m2m_table_name = db.shorten_name(u'project_targetuser_projects')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('targetuser', models.ForeignKey(orm[u'project.targetuser'], null=False)),
            ('project', models.ForeignKey(orm[u'project.project'], null=False))
        ))
        db.create_unique(m2m_table_name, ['targetuser_id', 'project_id'])


        # Changing field 'TargetUser.next_cursor'
        db.alter_column(u'project_targetuser', 'next_cursor', self.gf('django.db.models.fields.PositiveIntegerField')())

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
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'target_users': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'projects'", 'symmetrical': 'False', 'to': u"orm['project.TargetUser']"})
        },
        u'project.targetuser': {
            'Meta': {'object_name': 'TargetUser'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'next_cursor': ('django.db.models.fields.BigIntegerField', [], {'default': '0', 'null': 'True'}),
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
            'city': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True'}),
            'created_date': ('django.db.models.fields.DateTimeField', [], {}),
            'followers_count': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'full_name': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True'}),
            'geo_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'default': "'en'", 'max_length': '2'}),
            'last_tweet_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'latitude': ('django.db.models.fields.FloatField', [], {'null': 'True'}),
            'longitude': ('django.db.models.fields.FloatField', [], {'null': 'True'}),
            'source': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'time_zone': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True'}),
            'tweets_count': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'twitter_id': ('django.db.models.fields.BigIntegerField', [], {}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '160'}),
            'verified': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        }
    }

    complete_apps = ['project']