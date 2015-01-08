# import copy
# from multiprocessing import Pool
# import random
# import time
# from project.exceptions import RateLimitedException
# from project.models import Project, TargetUser, Extractor
# from twitter_bots.settings import set_logger
# from django.core.management.base import BaseCommand, CommandError
#
# set_logger('hashtag_extractor')
#
# class Command(BaseCommand):
#     help = 'Extract twitter users from all hashtags to track'
#
#     def handle(self, *args, **options):
#         def f(x):
#             return x*x
#
#         p = Pool(5)
#         p.map(f, [1,2,3])

