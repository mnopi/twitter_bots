from django.contrib import admin
from project.models import *

# Register your models here.
admin.site.register(Project)
admin.site.register(TweetMsg)
admin.site.register(TargetUser)
admin.site.register(Follower)
admin.site.register(TwitterUser)
admin.site.register(Tweet)
