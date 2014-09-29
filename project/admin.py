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
            target_user.extract_followers_from_all_target_users()
            self.message_user(request, "Followers extracted ok from %s" % target_user.username)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    extract_followers.short_description = "Extract all followers"


class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        # 'followers_spammed',
        'get_followers_count',
    )
    search_fields = ('name',)
    list_display_links = ('name',)

    actions = [
        'create_tweets_android',
        'extract_followers_from_all_target_users',
    ]

    def create_tweets_android(self, request, queryset):
        if queryset.count() == 1:
            project = queryset[0]
            project.create_tweets(platform=TwitterUser.ANDROID)
            self.message_user(request, "Project %s with android tweets created ok" % project.name)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    create_tweets_android.short_description = "Create android tweets"

    def extract_followers_from_all_target_users(self, request, queryset):
        if queryset.count() == 1:
            project = queryset[0]
            project.extract_followers_from_all_target_users()
            self.message_user(request, "All followers for project %s extracted ok" % project.name)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    extract_followers_from_all_target_users.short_description = "Extract all followers from all target users"


class TweetAdmin(admin.ModelAdmin):
    list_display = (
        'compose',
        'length',
        'date_sent',
        'sending',
        'sent_ok',
        'bot_used',
    )

    search_fields = ('bot_used__username',)
    list_filter = ('sending', 'sent_ok', 'date_sent',)
    # ordering = ('-date',)
    # list_display_links = ('username',)


# Register your models here.
admin.site.register(Project, ProjectAdmin)
admin.site.register(TweetMsg)
admin.site.register(TargetUser, TargetUserAdmin)
admin.site.register(Follower)
admin.site.register(TwitterUser)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Link)



