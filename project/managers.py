from django.db.models import Count
from twitter_bots import settings
from django.db import models


class TargetUserManager(models.Manager):
    def create(self, **kwargs):
        target_user_created = super(TargetUserManager, self).create(**kwargs)
        target_user_created.register_accounts()


class TweetManager(models.Manager):
    def get_pending(self):
        return self.filter(sending=False, sent_ok=False)
        settings.LOGGER.info('Pending tweets to send retrieved')

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



