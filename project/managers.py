# -*- coding: utf-8 -*-

import time
import random
from django.db.models import Count
from project.exceptions import RateLimitedException
from twitter_bots import settings
from django.db import models


class TargetUserManager(models.Manager):
    def create(self, **kwargs):
        target_user_created = super(TargetUserManager, self).create(**kwargs)
        target_user_created.complete_creation()


class TweetManager(models.Manager):
    def get_sent_ok(self):
        return self.filter(sent_ok=True)

    def all_sent_ok(self):
        return self.get_sent_ok().count() == self.all().count()

    def clean_not_sent_ok(self):
        self.filter(sent_ok=False).delete()
        settings.LOGGER.info('Deleted previous sending tweets')

    def create_tweet(self, platform=None):
        "Crea un tweet para un proyecto aleatorio entre los marcados como running"
        from .models import Project
        project = Project.objects.get_pending_to_process().order_by('?')[0]
        project.create_tweet()


class ProjectManager(models.Manager):
    def get_pending_to_process(self):
        "Devuelve todos los proyectos activos que tengan followers por mencionar"
        return self\
            .filter(running=True)\
            .annotate(unmentioned_users_count=Count('target_users__followers__twitter_user__mentions'))\
            .filter(unmentioned_users_count__gt=0)


class ExtractorManager(models.Manager):
    def display_extractor_mode(self, mode):
        from .models import Extractor
        if mode == Extractor.FOLLOWER_MODE:
            return 'follower'
        elif mode == Extractor.HASHTAG_MODE:
            return 'hashtag'

    def log_extractor_being_used(self, extractor):
        settings.LOGGER.info('### Using extractor: %s behind proxy %s ###' %
                             (extractor.twitter_bot.username,
                              extractor.twitter_bot.proxy.__unicode__()))

    def get_available_extractors(self, mode):

        available_extractors = [
            extractor for extractor in self.filter(mode=mode) if extractor.is_available()
        ]

        if not available_extractors:
            last_used_extractor = self.latest('last_request_date')
            settings.LOGGER.warning('No available %s extractors at this moment. Last used was %s at %s' %
                                    (self.display_extractor_mode(mode), last_used_extractor.twitter_bot.username,
                                     last_used_extractor.last_request_date))
        return available_extractors

    def extract_followers(self):
        from .models import Extractor
        for extractor in self.get_available_extractors(Extractor.FOLLOWER_MODE):
            try:
                self.log_extractor_being_used(extractor)
                extractor.extract_followers_from_all_target_users()
            except RateLimitedException:
                continue

        time.sleep(random.randint(5, 15))

    def extract_hashtags(self):
        from .models import Extractor
        for extractor in self.get_available_extractors(Extractor.HASHTAG_MODE):
            try:
                self.log_extractor_being_used(extractor)
                extractor.extract_twitter_users_from_all_hashtags()
            except RateLimitedException:
                continue

        time.sleep(random.randint(5, 15))