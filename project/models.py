from django.db import models


# Create your models here.
class Project(models.Model):
    name = models.CharField(max_length=100, null=False, blank=True)

    def __unicode__(self):
        return self.name


class TweetMsg(models.Model):
    text = models.CharField(max_length=160, null=False, blank=True)
    project = models.ForeignKey(Project, related_name='tweet_msgs')

    def __unicode__(self):
        return '%s @ %s' % (self.text, self.project.name)


class TargetUser(models.Model):
    username = models.CharField(max_length=80, null=False, blank=True)
    projects = models.ManyToManyField(Project, related_name='target_users')

    def __unicode__(self):
        return self.username


class Follower(models.Model):
    target_user = models.ForeignKey(TargetUser, related_name='followers', null=False)
    # follower = models.ForeignKey('project.models.TwitterUser', related_name='twitter_user')
    twitter_user = models.OneToOneField('TwitterUser', related_name='follower', null=False)

    def __unicode__(self):
        return '%s -> %s' % (self.twitter_user, self.target_user)


class TwitterUser(models.Model):
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=160, null=False, blank=True)
    username = models.CharField(max_length=160, null=False, blank=True)
    twitter_id = models.BigIntegerField(null=False, blank=True)
    country = models.CharField(max_length=2, null=True, blank=True)
    language = models.CharField(max_length=2, null=False, blank=True, default='en')
    city = models.CharField(max_length=80, null=True, blank=True)
    created_date = models.DateTimeField(null=False, blank=True)

    def __unicode__(self):
        return self.username


class Tweet(models.Model):
    tweet_msg = models.ForeignKey(TweetMsg, null=False)
    date = models.DateTimeField(null=False)
    project = models.ForeignKey(Project, related_name="tweets")
    mentioned_users = models.ManyToManyField(TwitterUser, related_name='mentions')

    def __unicode__(self):
        return self.tweet_msg




