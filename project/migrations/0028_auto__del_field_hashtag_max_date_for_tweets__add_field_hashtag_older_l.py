# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Hashtag.max_date_for_tweets'
        db.delete_column(u'project_hashtag', 'max_date_for_tweets')

        # Adding field 'Hashtag.older_limit_for_tweets'
        db.add_column(u'project_hashtag', 'older_limit_for_tweets',
                      self.gf('django.db.models.fields.DateTimeField')(null=True),
                      keep_default=False)

        # Adding field 'Hashtag.max_user_count'
        db.add_column(u'project_hashtag', 'max_user_count',
                      self.gf('django.db.models.fields.IntegerField')(null=True),
                      keep_default=False)

        # Adding field 'Hashtag.is_extracted'
        db.add_column(u'project_hashtag', 'is_extracted',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'Extractor.minutes_window'
        db.add_column(u'project_extractor', 'minutes_window',
                      self.gf('django.db.models.fields.PositiveIntegerField')(null=True),
                      keep_default=False)

        # Adding field 'Extractor.mode'
        db.add_column(u'project_extractor', 'mode',
                      self.gf('django.db.models.fields.PositiveIntegerField')(default=1),
                      keep_default=False)

        # Adding M2M table for field hashtags on 'Project'
        m2m_table_name = db.shorten_name(u'project_project_hashtags')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('project', models.ForeignKey(orm[u'project.project'], null=False)),
            ('hashtag', models.ForeignKey(orm[u'project.hashtag'], null=False))
        ))
        db.create_unique(m2m_table_name, ['project_id', 'hashtag_id'])


    def backwards(self, orm):
        # Adding field 'Hashtag.max_date_for_tweets'
        db.add_column(u'project_hashtag', 'max_date_for_tweets',
                      self.gf('django.db.models.fields.DateTimeField')(null=True),
                      keep_default=False)

        # Deleting field 'Hashtag.older_limit_for_tweets'
        db.delete_column(u'project_hashtag', 'older_limit_for_tweets')

        # Deleting field 'Hashtag.max_user_count'
        db.delete_column(u'project_hashtag', 'max_user_count')

        # Deleting field 'Hashtag.is_extracted'
        db.delete_column(u'project_hashtag', 'is_extracted')

        # Deleting field 'Extractor.minutes_window'
        db.delete_column(u'project_extractor', 'minutes_window')

        # Deleting field 'Extractor.mode'
        db.delete_column(u'project_extractor', 'mode')

        # Removing M2M table for field hashtags on 'Project'
        db.delete_table(db.shorten_name(u'project_project_hashtags'))


    models = {
        u'core.proxy': {
            'Meta': {'object_name': 'Proxy'},
            'date_added': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
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
            'is_being_created': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_manually_registered': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_suspended': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_suspended_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'password_email': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'password_twitter': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'proxy': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'twitter_bots'", 'null': 'True', 'on_delete': 'models.DO_NOTHING', 'to': u"orm['core.Proxy']"}),
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
        u'project.extractor': {
            'Meta': {'object_name': 'Extractor'},
            'access_token': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'access_token_secret': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'consumer_key': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'consumer_secret': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_rate_limited': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_request_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'minutes_window': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'mode': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'twitter_bot': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'extractor'", 'unique': 'True', 'to': u"orm['core.TwitterBot']"})
        },
        u'project.follower': {
            'Meta': {'object_name': 'Follower'},
            'date_saved': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'target_user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'followers'", 'to': u"orm['project.TargetUser']"}),
            'twitter_user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'follower'", 'to': u"orm['project.TwitterUser']"})
        },
        u'project.hashtag': {
            'Meta': {'object_name': 'Hashtag'},
            'geocode': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_extracted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lang': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True'}),
            'max_id': ('django.db.models.fields.BigIntegerField', [], {'null': 'True'}),
            'max_user_count': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'older_limit_for_tweets': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'q': ('django.db.models.fields.CharField', [], {'max_length': '140'}),
            'result_type': ('django.db.models.fields.PositiveIntegerField', [], {'default': '2'}),
            'twitter_users': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'hashtags'", 'blank': 'True', 'through': u"orm['project.TwitterUserHasHashtag']", 'to': u"orm['project.TwitterUser']"})
        },
        u'project.link': {
            'Meta': {'object_name': 'Link'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'platform': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'links'", 'to': u"orm['project.Project']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'})
        },
        u'project.project': {
            'Meta': {'object_name': 'Project'},
            'has_tracked_clicks': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'hashtags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'projects'", 'blank': 'True', 'to': u"orm['project.Hashtag']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_running': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'target_users': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'projects'", 'blank': 'True', 'to': u"orm['project.TargetUser']"})
        },
        u'project.targetuser': {
            'Meta': {'object_name': 'TargetUser'},
            'followers_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'next_cursor': ('django.db.models.fields.BigIntegerField', [], {'default': '0', 'null': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'})
        },
        u'project.tweet': {
            'Meta': {'object_name': 'Tweet'},
            'bot_used': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tweets'", 'null': 'True', 'to': u"orm['core.TwitterBot']"}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'link': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tweet'", 'null': 'True', 'to': u"orm['project.Link']"}),
            'mentioned_users': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'mentions'", 'null': 'True', 'symmetrical': 'False', 'to': u"orm['project.TwitterUser']"}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tweets'", 'to': u"orm['project.Project']"}),
            'sending': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sent_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tweet_msg': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['project.TweetMsg']"})
        },
        u'project.tweetmsg': {
            'Meta': {'object_name': 'TweetMsg'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tweet_msgs'", 'to': u"orm['project.Project']"}),
            'text': ('django.db.models.fields.CharField', [], {'max_length': '101'})
        },
        u'project.twitteruser': {
            'Meta': {'object_name': 'TwitterUser'},
            'city': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True'}),
            'created_date': ('django.db.models.fields.DateTimeField', [], {}),
            'date_saved': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
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
        },
        u'project.twitteruserhashashtag': {
            'Meta': {'object_name': 'TwitterUserHasHashtag'},
            'date_saved': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'hashtag': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['project.Hashtag']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'twitter_user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['project.TwitterUser']"})
        }
    }

    complete_apps = ['project']