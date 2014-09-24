from django.contrib import admin
from project.models import *
from django.contrib import messages


class TargetUserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'next_cursor',
        'followers_count',
        'followers_android',
        'followers_saved',
    )
    search_fields = ('username', 'next_cursor')
    list_display_links = ('username',)

    actions = [
        'extract_followers',
    ]

    def extract_followers(self, request, queryset):
        if queryset.count() == 1:
            target_user = queryset[0]
            target_user.extract_followers()
            self.message_user(request, "Followers extracted ok from %s" % target_user.username)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    extract_followers.short_description = "Extract all followers"


class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        # 'followers_spammed',
        'total_followers',
    )
    search_fields = ('name',)
    list_display_links = ('name',)

    actions = [
        'create_tweets_android',
    ]

    def create_tweets_android(self, request, queryset):
        if queryset.count() == 1:
            project = queryset[0]
            project.create_tweets(platform=TwitterUser.ANDROID)
            self.message_user(request, "Project %s with android tweets created ok" % project.name)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    create_tweets_android.short_description = "Create android tweets"


class TweetAdmin(admin.ModelAdmin):
    list_display = (
        'compose',
        'length',
        'sending',
        'sent_ok',
    )


# Register your models here.
admin.site.register(Project, ProjectAdmin)
admin.site.register(TweetMsg)
admin.site.register(TargetUser, TargetUserAdmin)
admin.site.register(Follower)
admin.site.register(TwitterUser)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Link)



