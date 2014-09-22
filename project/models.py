from django.db import models


# Create your models here.
class Project(models.Model):
    name = models.CharField(max_length=100, null=False, blank=True)


class TweetMsg(models.Model):
    text = models.CharField(max_length=160, null=False, blank=True)
    project = models.ForeignKey(Project, related_name='tweet_msgs')


class TargetUser(models.Model):
    username = models.CharField(max_length=80, null=False, blank=True)
    projects = models.ManyToManyField(Project, related_name='target_users')


class Follower(models.Model):
    target_user = models.ForeignKey(TargetUser, related_name='followers')
    # follower = models.ForeignKey('project.models.TwitterUser', related_name='twitter_user')
    twitter_user = models.OneToOneField('TwitterUser', related_name='follower')


class TwitterUser(models.Model):
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=160, null=False, blank=True)
    username = models.CharField(max_length=160, null=False, blank=True)
    twitter_id = models.BigIntegerField(null=False, blank=True)
    country = models.CharField(max_length=2, null=True, blank=True)
    language = models.CharField(max_length=2, null=True, blank=True)
    city = models.CharField(max_length=80, null=True, blank=True)
    created_date = models.DateTimeField(null=False, blank=True)


class Tweet(models.Model):
    text = models.CharField(max_length=160, null=False)
    date = models.DateTimeField(null=False)
    project = models.ForeignKey(Project, related_name="tweets")
    mentioned_users = models.ManyToManyField(TwitterUser, related_name='mentions')




