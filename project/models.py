from django.db import models
from project.managers import TargetUserManager


class Project(models.Model):
    name = models.CharField(max_length=100, null=False, blank=True)
    target_users = models.ManyToManyField('TargetUser', related_name='projects')

    def __unicode__(self):
        return self.name


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
    date = models.DateTimeField(null=False)
    project = models.ForeignKey(Project, related_name="tweets")
    mentioned_users = models.ManyToManyField(TwitterUser, related_name='mentions')

    def __unicode__(self):
        return self.tweet_msg




