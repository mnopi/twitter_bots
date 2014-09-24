
__author__ = 'Michel'

from django.db import models


class TargetUserManager(models.Manager):
    def create(self, **kwargs):
        target_user_created = super(TargetUserManager, self).create(**kwargs)
        target_user_created.process()


class TweetManager(models.Manager):
    def get_pending(self):
        return self.filter(sending=False, sent_ok=False).first()