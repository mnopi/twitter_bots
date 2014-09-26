import datetime
import simplejson
import time
from project.exceptions import RateLimitedException
from project.models import TargetUser, TwitterUser, Follower
from twitter_bots import settings
from twitter_bots.settings import LOGGER

__author__ = 'Michel'

import requests_oauthlib as req


class TwitterExplorer(object):

    def __init__(self):
        self.api = TwitterAPI()

    def extract_followers(self, target_username):

        def create_twitter_user(tw_follower):
            twitter_user = TwitterUser.objects.filter(twitter_id=tw_follower['id'])
            if not twitter_user.exists():
                twitter_user = TwitterUser()
                settings.LOGGER.info('Creating new twitter user %s' % tw_follower['screen_name'])
            else:
                if len(twitter_user) > 1:
                    raise Exception('Duplicated twitter user with id %i' % twitter_user[0].twitter_id)
                else:
                    twitter_user = twitter_user[0]
                    settings.LOGGER.info('Twitter user %s exists previously saved. Getting..' % twitter_user.username)

            twitter_user.twitter_id = tw_follower['id']
            twitter_user.created_date = self.api.format_datetime(tw_follower['created_at'])
            twitter_user.followers_count = tw_follower['followers_count']
            twitter_user.geo_enabled = tw_follower['geo_enabled']
            twitter_user.language = tw_follower['lang'][:2] if tw_follower['lang'] else TwitterUser.DEFAULT_LANG
            twitter_user.full_name = tw_follower['name']
            twitter_user.username = tw_follower['screen_name']
            twitter_user.tweets_count = tw_follower['statuses_count']
            twitter_user.time_zone = tw_follower['time_zone']
            twitter_user.verified = tw_follower['verified']

            if 'status' in tw_follower:
                if 'created_at' in tw_follower['status']:
                    twitter_user.last_tweet_date = self.api.format_datetime(tw_follower['status']['created_at'])
                if 'source' in tw_follower['status']:
                    twitter_user.source = self.api.format_source(tw_follower['status']['source'])
                else:
                    twitter_user.source = TwitterUser.OTHERS
            else:
                twitter_user.source = TwitterUser.OTHERS

            twitter_user.save()
            settings.LOGGER.info('Twitter user %s saved ok' % twitter_user.username)
            return twitter_user

        uri = 'followers/list.json?screen_name=%s&count=200' % target_username
        target_user = TargetUser.objects.get_or_create(username=target_username)[0]
        target_user.process()

        next_cursor = target_user.next_cursor
        while True:
            try:
                settings.LOGGER.info('Retrieving %s followers (cursor %i)' % (target_username, next_cursor))

                # si esta a None entonces se dan por procesados todos sus followers
                if next_cursor == None:
                    break
                elif next_cursor != 0:
                    full_uri = uri + '&cursor=%i' % next_cursor
                else:
                    full_uri = uri

                resp = self.api.get(full_uri)

                self.api.check_api_rate_reachability_limit(resp)

                for tw_follower in resp['users']:
                    # creamos twitter_user a partir del follower si ya no existe en BD
                    twitter_user = create_twitter_user(tw_follower)
                    Follower.objects.get_or_create(twitter_user=twitter_user, target_user=target_user)

                # actualizamos el next_cursor para el target user
                next_cursor = resp['next_cursor']
                if not next_cursor:
                    next_cursor = None
                    target_user.next_cursor = next_cursor
                    target_user.save()
                    settings.LOGGER.info('All followers from %s retrieved ok' % target_username)
                    break
                else:
                    target_user.next_cursor = next_cursor
                    target_user.save()
            except RateLimitedException:
                settings.LOGGER.exception('')
                # ponemos a dormir el explorador 16 minutillos hasta que refresque el periodo ventana de la API para pedir mas followers
                time.sleep(16*60)

class TwitterAPI(object):
    consumer_key = "ESjshGwY13JIl3SLF4dLiQVDB"
    consumer_secret = "QFD2w79cXOXoGOf1TDbcSxPEhVJWtjGhMHrFTkTiouwreg9nJ3"
    access_token = "2532144721-eto2YywaV7KF0gmrHLhYSWiZ8X22xt8KuTItV83"
    access_token_secret = "R6zdO3qVsLP0RuyTN25nCqfxvtCyUydOVzFn8NCzJezuG"
    base_url = 'https://api.twitter.com/1.1/'

    def __init__(self):
        self.twitter = req.OAuth1Session(self.consumer_key,
                                    client_secret=self.consumer_secret,
                                    resource_owner_key=self.access_token,
                                    resource_owner_secret=self.access_token_secret)

    def get(self, uri):
        # url = 'https://api.twitter.com/1.1/followers/list.json?cursor=2&screen_name=candycrush&count=5000'
        resp = self.twitter.get(self.base_url + uri)
        return simplejson.loads(resp.content)

    def get_user_info(self, username):
        return self.get('users/show.json?screen_name=%s' % username)

    def format_datetime(self, twitter_datetime_str):
        if not twitter_datetime_str:
            return None
        else:
            return datetime.datetime.strptime(twitter_datetime_str, '%a %b %d %H:%M:%S +0000 %Y')

    def format_source(self, user_source_str):
        low = user_source_str.lower()
        if 'iphone' in low:
            return TwitterUser.IPHONE
        elif 'ipad' in low:
            return TwitterUser.IPAD
        elif 'ios' in low:
            return TwitterUser.IOS
        elif 'android' in low:
            return TwitterUser.ANDROID
        else:
            return TwitterUser.OTHERS

    def check_api_rate_reachability_limit(self, resp):
        if 'errors' in resp:
            for e in resp['errors']:
                if e['code'] == 88:
                    raise RateLimitedException()