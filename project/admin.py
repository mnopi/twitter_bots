from daterange_filter.filter import DateRangeFilter, DateTimeRangeFilter
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
    list_filter = (
        'sending',
        'sent_ok',
        'date_sent',
        'link__platform'
    )
    # ordering = ('-date',)
    # list_display_links = ('username',)


class FollowerAdmin(admin.ModelAdmin):
    list_display = (
        'target_user',
        'twitter_user',
        'date_saved',
    )

    search_fields = (
        'target_user__username',
        'twitter_user__username',
    )
    list_filter = ('target_user', 'date_saved',)


class TwitterUserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'date_saved',
    )

    search_fields = (
        'username',
        'hashtags__q',
    )
    list_filter = ('date_saved',)


class ExtractorAdmin(admin.ModelAdmin):
    list_display = (
        'twitter_bot',
        'date_created',
        'last_request_date',
        'is_rate_limited',
    )

    search_fields = (
        'twitter_bot__username',
    )
    list_filter = (
        'date_created',
        'last_request_date',
        'is_rate_limited',
        'mode',
    )


# Register your models here.
admin.site.register(Project, ProjectAdmin)
admin.site.register(TweetMsg)
admin.site.register(TargetUser, TargetUserAdmin)
admin.site.register(Follower, FollowerAdmin)
admin.site.register(TwitterUser, TwitterUserAdmin)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Extractor, ExtractorAdmin)
admin.site.register(Link)
admin.site.register(Hashtag)
admin.site.register(TwitterUserHasHashtag)



