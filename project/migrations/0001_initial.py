# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Project'
        db.create_table(u'project_project', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
        ))
        db.send_create_signal(u'project', ['Project'])

        # Adding model 'TweetMsg'
        db.create_table(u'project_tweetmsg', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('text', self.gf('django.db.models.fields.CharField')(max_length=160, blank=True)),
            ('project', self.gf('django.db.models.fields.related.ForeignKey')(related_name='tweet_msgs', to=orm['project.Project'])),
        ))
        db.send_create_signal(u'project', ['TweetMsg'])

        # Adding model 'TargetUser'
        db.create_table(u'project_targetuser', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=80, blank=True)),
        ))
        db.send_create_signal(u'project', ['TargetUser'])

        # Adding M2M table for field projects on 'TargetUser'
        m2m_table_name = db.shorten_name(u'project_targetuser_projects')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('targetuser', models.ForeignKey(orm[u'project.targetuser'], null=False)),
            ('project', models.ForeignKey(orm[u'project.project'], null=False))
        ))
        db.create_unique(m2m_table_name, ['targetuser_id', 'project_id'])

        # Adding model 'Follower'
        db.create_table(u'project_follower', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('target_user', self.gf('django.db.models.fields.related.ForeignKey')(related_name='followers', to=orm['project.TargetUser'])),
            ('twitter_user', self.gf('django.db.models.fields.related.OneToOneField')(related_name='follower', unique=True, to=orm['project.TwitterUser'])),
        ))
        db.send_create_signal(u'project', ['Follower'])

        # Adding model 'TwitterUser'
        db.create_table(u'project_twitteruser', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('latitude', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('longitude', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('source', self.gf('django.db.models.fields.CharField')(max_length=160, blank=True)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=160, blank=True)),
            ('twitter_id', self.gf('django.db.models.fields.BigIntegerField')(blank=True)),
            ('country', self.gf('django.db.models.fields.CharField')(max_length=2, null=True, blank=True)),
            ('language', self.gf('django.db.models.fields.CharField')(max_length=2, null=True, blank=True)),
            ('city', self.gf('django.db.models.fields.CharField')(max_length=80, null=True, blank=True)),
            ('created_date', self.gf('django.db.models.fields.DateTimeField')(blank=True)),
        ))
        db.send_create_signal(u'project', ['TwitterUser'])

        # Adding model 'Tweet'
        db.create_table(u'project_tweet', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('text', self.gf('django.db.models.fields.CharField')(max_length=160)),
            ('date', self.gf('django.db.models.fields.DateTimeField')()),
            ('project', self.gf('django.db.models.fields.related.ForeignKey')(related_name='tweets', to=orm['project.Project'])),
        ))
        db.send_create_signal(u'project', ['Tweet'])

        # Adding M2M table for field mentioned_users on 'Tweet'
        m2m_table_name = db.shorten_name(u'project_tweet_mentioned_users')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('tweet', models.ForeignKey(orm[u'project.tweet'], null=False)),
            ('twitteruser', models.ForeignKey(orm[u'project.twitteruser'], null=False))
        ))
        db.create_unique(m2m_table_name, ['tweet_id', 'twitteruser_id'])


    def backwards(self, orm):
        # Deleting model 'Project'
        db.delete_table(u'project_project')

        # Deleting model 'TweetMsg'
        db.delete_table(u'project_tweetmsg')

        # Deleting model 'TargetUser'
        db.delete_table(u'project_targetuser')

        # Removing M2M table for field projects on 'TargetUser'
        db.delete_table(db.shorten_name(u'project_targetuser_projects'))

        # Deleting model 'Follower'
        db.delete_table(u'project_follower')

        # Deleting model 'TwitterUser'
        db.delete_table(u'project_twitteruser')

        # Deleting model 'Tweet'
        db.delete_table(u'project_tweet')

        # Removing M2M table for field mentioned_users on 'Tweet'
        db.delete_table(db.shorten_name(u'project_tweet_mentioned_users'))


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
            'projects': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'target_users'", 'symmetrical': 'False', 'to': u"orm['project.Project']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'})
        },
        u'project.tweet': {
            'Meta': {'object_name': 'Tweet'},
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mentioned_users': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'mentions'", 'symmetrical': 'False', 'to': u"orm['project.TwitterUser']"}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tweets'", 'to': u"orm['project.Project']"}),
            'text': ('django.db.models.fields.CharField', [], {'max_length': '160'})
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
            'language': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True', 'blank': 'True'}),
            'latitude': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'longitude': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '160', 'blank': 'True'}),
            'twitter_id': ('django.db.models.fields.BigIntegerField', [], {'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '160', 'blank': 'True'})
        }
    }

    complete_apps = ['project']