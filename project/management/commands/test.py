# import copy
# from multiprocessing import Pool
# import random
# import time
# from project.exceptions import RateLimitedException
# from project.models import Project, TargetUser, Extractor
# from twitter_bots.settings import set_logger
from django.core.management.base import BaseCommand, CommandError
#
# set_logger('hashtag_extractor')
#
class Command(BaseCommand):

    def handle(self, *args, **options):
        print 'He procesando id %i' % int(args[0])

