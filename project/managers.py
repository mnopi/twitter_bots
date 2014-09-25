
__author__ = 'Michel'

from django.db import models


class TargetUserManager(models.Manager):
    def create(self, **kwargs):
        target_user_created = super(TargetUserManager, self).create(**kwargs)
        target_user_created.process()


class TweetManager(models.Manager):
    def get_pending(self):
        return self.filter(sending=False, sent_ok=False)

    def get_sent_ok(self):
        return self.filter(sent_ok=True)

    def all_sent_ok(self):
        return self.get_sent_ok().count() == self.all().count()