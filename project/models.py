from django.db import models
from project.managers import TargetUserManager, TweetManager
from twitter_bots.settings import LOGGER


class Project(models.Model):
    name = models.CharField(max_length=100, null=False, blank=True)
    target_users = models.ManyToManyField('TargetUser', related_name='projects')

    def __unicode__(self):
        return self.name

    def followers_spammed(self):
        pass

    def total_followers(self):
        return Follower.objects.filter(target_user__projects=self).count()

    def create_tweets(self, platform=None):
        """platform es una de las posibles opciones de segmentacion a implementar en un futuro (por pais, idioma..)"""
        LOGGER.info('Creating tweets for project %s' % self.name)
        filter = {
            'target_user__projects': self,
        }
        if platform != None:
            filter.update(twitter_user__source=platform)

        # todo: optimizar par una sola consulta
        current_tweet = self.create_tweet_to_send(platform=TwitterUser.ANDROID)
        followers = Follower.objects.filter(**filter)
        for follower in followers:
            if not follower.was_mentioned(project=self):
                LOGGER.info('Processing follower %s' % follower.twitter_user.username)
                current_tweet.mentioned_users.add(follower.twitter_user)
                if not current_tweet.has_space():
                    current_tweet.mentioned_users.remove(follower.twitter_user)
                    current_tweet = self.create_tweet_to_send(platform=TwitterUser.ANDROID)
                    current_tweet.mentioned_users.add(follower.twitter_user)
            else:
                LOGGER.info('%s was mentioned for project %s' % (follower.twitter_user.username, self.name))

        if not current_tweet.mentioned_users.all():
            current_tweet.delete()

    def get_tweets_pending_to_send(self):
        return Tweet.objects.filter(project=self, sent_ok=False, sending=False)

    def create_tweet_to_send(self, platform=None):
        new_tweet = Tweet(project=self, tweet_msg=self.tweet_msgs.first())

        links = self.links.filter(platform=platform)
        if platform != None and links.exists():
            new_tweet.link = links.first()

        new_tweet.save()
        return new_tweet


class TweetMsg(models.Model):
    text = models.CharField(max_length=160, null=False, blank=True)
    project = models.ForeignKey(Project, related_name='tweet_msgs')

    def __unicode__(self):
        return '%s @ %s' % (self.text, self.project.name)


class TargetUser(models.Model):
    username = models.CharField(max_length=80, null=False, blank=True)
    # cuando el cursor sea null es que se han extraido todos sus followers
    next_cursor = models.BigIntegerField(null=True, default=0)
    followers_count = models.PositiveIntegerField(null=True, default=0)

    objects = TargetUserManager()

    def __unicode__(self):
        return self.username

    def extract_followers(self):
        from project.twitter_explorer import TwitterExplorer
        TwitterExplorer().extract_followers(self.username)

    def process(self):
        from project.twitter_explorer import TwitterAPI

        tw_user = TwitterAPI().get_user_info(self.username)
        self.followers_count = tw_user['followers_count']
        self.save()

    def followers_saved(self):
        return Follower.objects.filter(target_user=self).count()


class Follower(models.Model):
    target_user = models.ForeignKey(TargetUser, related_name='followers', null=False)
    # follower = models.ForeignKey('project.models.TwitterUser', related_name='twitter_user')
    twitter_user = models.OneToOneField('TwitterUser', related_name='follower', null=False)

    def __unicode__(self):
        return '%s -> %s' % (self.twitter_user, self.target_user)

    def was_mentioned(self, project=None):
        """Mira si el follower aparece mencionado para todos los proyectos o el dado por parametro"""
        tweets = Tweet.objects.filter(mentioned_users__follower=self)
        if project:
            tweets = tweets.filter(project=project)
        if tweets:
            return True
        else:
            return False


class TwitterUser(models.Model):
    OTHERS = 0
    IOS = 1
    IPAD = 2
    IPHONE = 3
    ANDROID = 4
    SOURCES = (
        (OTHERS, 'others'),
        (IOS, 'ios'),
        (IPAD, 'ipad'),
        (IPHONE, 'iphone'),
        (ANDROID, 'android'),
    )
    source = models.PositiveIntegerField(null=False, choices=SOURCES, default=0)
    username = models.CharField(max_length=160, null=False)
    full_name = models.CharField(max_length=160, null=True)
    twitter_id = models.BigIntegerField(null=False)

    # GEO
    geo_enabled = models.BooleanField(default=False)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    city = models.CharField(max_length=80, null=True)
    country = models.CharField(max_length=2, null=True)

    # TIME
    created_date = models.DateTimeField(null=False)
    time_zone = models.CharField(max_length=50, null=True)  # te da la zona horaria por la ciudad, x. ej 'Madrid'
    last_tweet_date = models.DateTimeField(null=True)

    language = models.CharField(max_length=2, null=False, default='en')
    followers_count = models.PositiveIntegerField(null=True)
    tweets_count = models.PositiveIntegerField(null=True)
    verified = models.BooleanField(default=False)

    def __unicode__(self):
        return self.username


class Tweet(models.Model):
    tweet_msg = models.ForeignKey(TweetMsg, null=False)
    link = models.ForeignKey('Link', null=True, blank=True, related_name='tweet')
    date = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, related_name="tweets")
    mentioned_users = models.ManyToManyField(TwitterUser, related_name='mentions', null=True, blank=True)
    sending = models.BooleanField(default=False)
    sent_ok = models.BooleanField(default=False)

    objects = TweetManager()

    def __unicode__(self):
        return self.compose()

    def compose(self):
        mu_txt = ''
        for mu in self.mentioned_users.all():
            mu_txt += '@%s ' % mu.username

        link_txt = ' ' + self.link.url if self.link else ''

        return mu_txt + self.tweet_msg.text + link_txt

    def length(self):
        def mentioned_users_space():
            length = 0
            for mu in self.mentioned_users.all():
                length += len(mu.username) + 2
            return length

        total_lenght = 0
        total_lenght += mentioned_users_space()
        total_lenght += len(self.tweet_msg.text)
        if self.link:
            total_lenght += 1 + len(self.link.url)
        return total_lenght

    def has_space(self):
        """Devuelve si el tweet no supera los 140 caracteres"""
        return self.length() <= 140

    def is_available(self):
        return not self.sending and not self.sent_ok


class Link(models.Model):
    url = models.URLField(null=False)
    project = models.ForeignKey(Project, null=False, related_name='links')
    platform = models.IntegerField(null=False, choices=TwitterUser.SOURCES, default=0)

    def __unicode__(self):
        return '%s @ %s' % (self.project.name, self.get_platform_display())

