# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'TargetUser.date_last_extraction'
        db.add_column(u'project_targetuser', 'date_last_extraction',
                      self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'TargetUser.date_last_extraction'
        db.delete_column(u'project_targetuser', 'date_last_extraction')


    models = {
        u'core.proxy': {
            'Meta': {'object_name': 'Proxy'},
            'date_added': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_not_in_proxies_txts': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_phone_required': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_unavailable_for_registration': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_unavailable_for_use': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_in_proxies_txts': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_phone_required': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_unavailable_for_registration': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_unavailable_for_use': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'proxies_group': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'proxies'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': u"orm['project.ProxiesGroup']"}),
            'proxy': ('django.db.models.fields.CharField', [], {'max_length': '21', 'blank': 'True'}),
            'proxy_provider': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        },
        u'core.twitterbot': {
            'Meta': {'object_name': 'TwitterBot'},
            'birth_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_death': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_suspended_email': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_suspended_twitter': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.CharField', [], {'max_length': '256', 'blank': 'True'}),
            'email_registered_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'gender': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '1'}),
            'has_fast_mode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_being_created': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_dead': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_manually_registered': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_suspended': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_suspended_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'num_suspensions_lifted': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'password_email': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'password_twitter': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'proxy_for_registration': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'twitter_bots_registered'", 'null': 'True', 'on_delete': 'models.DO_NOTHING', 'to': u"orm['core.Proxy']"}),
            'proxy_for_usage': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'twitter_bots_using'", 'null': 'True', 'on_delete': 'models.DO_NOTHING', 'to': u"orm['core.Proxy']"}),
            'real_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'twitter_avatar_completed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'twitter_bio_completed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'twitter_confirmed_email_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'twitter_registered_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_agent': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
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
            'last_request_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'minutes_window': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'mode': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'twitter_bot': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'extractor'", 'unique': 'True', 'to': u"orm['core.TwitterBot']"})
        },
        u'project.feed': {
            'Meta': {'object_name': 'Feed'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'_unnamed'", 'max_length': '100'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'})
        },
        u'project.feeditem': {
            'Meta': {'object_name': 'FeedItem'},
            'feed': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['project.Feed']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'link': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'text': ('django.db.models.fields.CharField', [], {'max_length': '101'})
        },
        u'project.feedsgroup': {
            'Meta': {'object_name': 'FeedsGroup'},
            'feeds': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'feeds_groups'", 'null': 'True', 'symmetrical': 'False', 'to': u"orm['project.Feed']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'proxies_groups': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'feeds_groups'", 'null': 'True', 'symmetrical': 'False', 'to': u"orm['project.ProxiesGroup']"})
        },
        u'project.follower': {
            'Meta': {'object_name': 'Follower'},
            'date_saved': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'target_user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'followers'", 'to': u"orm['project.TargetUser']"}),
            'twitter_user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'follower'", 'to': u"orm['project.TwitterUser']"})
        },
        u'project.ftweetsnumpertumention': {
            'Meta': {'object_name': 'FTweetsNumPerTuMention'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'tu_mention': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'ftweets_num'", 'unique': 'True', 'to': u"orm['project.Tweet']"})
        },
        u'project.hashtag': {
            'Meta': {'object_name': 'Hashtag'},
            'geocode': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_extracted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lang': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True', 'blank': 'True'}),
            'max_id': ('django.db.models.fields.BigIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'max_user_count': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'older_limit_for_tweets': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'q': ('django.db.models.fields.CharField', [], {'max_length': '140'}),
            'result_type': ('django.db.models.fields.PositiveIntegerField', [], {'default': '2'}),
            'twitter_users': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'hashtags'", 'blank': 'True', 'through': u"orm['project.TwitterUserHasHashtag']", 'to': u"orm['project.TwitterUser']"})
        },
        u'project.hashtaggroup': {
            'Meta': {'object_name': 'HashtagGroup'},
            'hashtags': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'hashtag_groups'", 'symmetrical': 'False', 'to': u"orm['project.Hashtag']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '140'}),
            'projects': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'hashtag_groups'", 'symmetrical': 'False', 'to': u"orm['project.Project']"})
        },
        u'project.link': {
            'Meta': {'object_name': 'Link'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'links'", 'null': 'True', 'to': u"orm['project.Project']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'})
        },
        u'project.pagelink': {
            'Meta': {'object_name': 'PageLink'},
            'hashtags': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'page_links'", 'null': 'True', 'symmetrical': 'False', 'to': u"orm['project.PageLinkHashtag']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'page_img'", 'null': 'True', 'to': u"orm['project.TweetImg']"}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True', 'blank': 'True'}),
            'page_link': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'page_title': ('django.db.models.fields.CharField', [], {'max_length': '150', 'null': 'True', 'blank': 'True'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['project.Project']", 'null': 'True', 'blank': 'True'})
        },
        u'project.pagelinkhashtag': {
            'Meta': {'object_name': 'PageLinkHashtag'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
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
        u'project.proxiesgroup': {
            'Meta': {'object_name': 'ProxiesGroup'},
            'destination_bot_checking_time_window': ('django.db.models.fields.CharField', [], {'default': "'4-6'", 'max_length': '10'}),
            'feedtweets_per_twitteruser_mention': ('django.db.models.fields.CharField', [], {'default': "'0-3'", 'max_length': '10'}),
            'has_link': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_mentions': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_page_announced': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_tweet_img': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_tweet_msg': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_bot_creation_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_bot_usage_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'max_num_mentions_per_tweet': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'max_tw_bots_per_proxy_for_registration': ('django.db.models.fields.PositiveIntegerField', [], {'default': '6'}),
            'max_tw_bots_per_proxy_for_usage': ('django.db.models.fields.PositiveIntegerField', [], {'default': '12'}),
            'mctweet_to_same_bot_time_window': ('django.db.models.fields.CharField', [], {'default': "'60-120'", 'max_length': '10'}),
            'mention_fail_time_window': ('django.db.models.fields.CharField', [], {'default': "'10-40'", 'max_length': '10'}),
            'min_days_between_registrations_per_proxy': ('django.db.models.fields.PositiveIntegerField', [], {'default': '5'}),
            'min_days_between_registrations_per_proxy_under_same_subnet': ('django.db.models.fields.PositiveIntegerField', [], {'default': '2'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'num_consecutive_mentions_for_check_mentioning_works': ('django.db.models.fields.PositiveIntegerField', [], {'default': '20'}),
            'projects': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'proxies_groups'", 'null': 'True', 'symmetrical': 'False', 'to': u"orm['project.Project']"}),
            'reuse_proxies_with_suspended_bots': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'time_between_tweets': ('django.db.models.fields.CharField', [], {'default': "'2-7'", 'max_length': '10'}),
            'webdriver': ('django.db.models.fields.CharField', [], {'default': "'PH'", 'max_length': '2'})
        },
        u'project.sublink': {
            'Meta': {'object_name': 'Sublink'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'default': "'en'", 'max_length': '2'}),
            'parent_link': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'sublinks'", 'to': u"orm['project.Link']"}),
            'platform': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'})
        },
        u'project.targetuser': {
            'Meta': {'object_name': 'TargetUser'},
            'date_extraction_end': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_last_extraction': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'followers_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'next_cursor': ('django.db.models.fields.BigIntegerField', [], {'default': '0', 'null': 'True'}),
            'num_consecutive_pages_without_enough_new_followers': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'null': 'True'}),
            'twitter_users': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'target_users'", 'blank': 'True', 'through': u"orm['project.Follower']", 'to': u"orm['project.TwitterUser']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'})
        },
        u'project.tugroup': {
            'Meta': {'object_name': 'TUGroup'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '140'}),
            'projects': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'tu_groups'", 'symmetrical': 'False', 'to': u"orm['project.Project']"}),
            'target_users': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'tu_groups'", 'symmetrical': 'False', 'to': u"orm['project.TargetUser']"})
        },
        u'project.tweet': {
            'Meta': {'object_name': 'Tweet'},
            'bot_used': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tweets'", 'null': 'True', 'to': u"orm['core.TwitterBot']"}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'feed_item': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tweets'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': u"orm['project.FeedItem']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'link': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tweets'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': u"orm['project.Link']"}),
            'mentioned_bots': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'mentions'", 'null': 'True', 'symmetrical': 'False', 'to': u"orm['core.TwitterBot']"}),
            'mentioned_users': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'mentions'", 'null': 'True', 'symmetrical': 'False', 'to': u"orm['project.TwitterUser']"}),
            'page_announced': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tweets'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': u"orm['project.PageLink']"}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tweets'", 'null': 'True', 'to': u"orm['project.Project']"}),
            'sending': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sent_ok': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tweet_img': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tweets'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': u"orm['project.TweetImg']"}),
            'tweet_msg': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['project.TweetMsg']", 'null': 'True', 'on_delete': 'models.PROTECT', 'blank': 'True'})
        },
        u'project.tweetcheckingmention': {
            'Meta': {'object_name': 'TweetCheckingMention'},
            'destination_bot_checked_mention': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'destination_bot_checked_mention_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'destination_bot_is_checking_mention': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mentioning_works': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tweet': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'tweet_checking_mention'", 'unique': 'True', 'to': u"orm['project.Tweet']"})
        },
        u'project.tweetfromfeed': {
            'Meta': {'object_name': 'TweetFromFeed'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tu_mention': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tweets_from_feed'", 'to': u"orm['project.Tweet']"}),
            'tweet': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'tweet_from_feed'", 'unique': 'True', 'to': u"orm['project.Tweet']"})
        },
        u'project.tweetimg': {
            'Meta': {'object_name': 'TweetImg'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'is_using': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tweet_imgs'", 'to': u"orm['project.Project']"})
        },
        u'project.tweetmsg': {
            'Meta': {'object_name': 'TweetMsg'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True', 'blank': 'True'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tweet_msgs'", 'null': 'True', 'to': u"orm['project.Project']"}),
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
            'last_tweet_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
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
            'hashtag': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'hashtag_users'", 'to': u"orm['project.Hashtag']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'twitter_user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'hashtag_users'", 'to': u"orm['project.TwitterUser']"})
        }
    }

    complete_apps = ['project']