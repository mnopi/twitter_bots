import copy
from core.models import TwitterBot
from twitter_bots.settings import set_logger

__author__ = 'Michel'

LOGGING = set_logger('follower_extractor')

from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Creates bots'

    def handle(self, *args, **options):
        TwitterBot.objects.create_bots(1)

        # for poll_id in args:
        #     try:
        #         poll = Poll.objects.get(pk=int(poll_id))
        #     except Poll.DoesNotExist:
        #         raise CommandError('Poll "%s" does not exist' % poll_id)
        #
        #     poll.opened = False
        #     poll.save()
        #
        #     self.stdout.write('Successfully closed poll "%s"' % poll_id)