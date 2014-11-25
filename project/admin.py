from django.contrib import admin
from project.models import *
from django.contrib import messages


class TargetUserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'is_active',
        'next_cursor',
        'followers_count',
        'followers_android',
        'followers_saved',
    )
    search_fields = ('username', 'next_cursor')
    list_display_links = ('username',)

    list_filter = (
        'is_active',
    )

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


# PROJECT ADMIN

# tabular inlines
class ProjectProxiesGroupInline(admin.TabularInline):
    model = ProxiesGroup.projects.through

class ProjectLinkInline(admin.TabularInline):
    model = Link

class ProjectTweetImgInline(admin.TabularInline):
    model = TweetImg

class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_running',
    )

    list_editable = (
        'is_running',
    )

    search_fields = ('name',)
    list_display_links = ('name',)


    inlines = [
        ProjectProxiesGroupInline,
        ProjectLinkInline,
        ProjectTweetImgInline,
    ]


class PageLinkHashtagAdmin(admin.ModelAdmin):
    list_display = (
        'name'
    )


class TweetAdmin(admin.ModelAdmin):
    list_display = (
        'compose',
        'length',
        'date_created',
        'date_sent',
        'sending',
        'sent_ok',
        'bot_used',
        'page_announced',
        'project',
        'has_image',
    )

    ordering = ('-sending', '-sent_ok')

    exclude = (
        'mentioned_users',
    )

    list_per_page = 15

    search_fields = (
        'bot_used__username',
        'compose',
    )
    list_filter = (
        'sending',
        'sent_ok',
        'date_created',
        'date_sent',
       # 'link__platform'
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
    list_filter = (
        'date_saved',
        'target_users__projects',
        'source',
        'target_users',
        'hashtags__q',
    )


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

class SubLinkInline(admin.TabularInline):
    model = Sublink


class PageLinkAdmin(admin.ModelAdmin):
    list_display = (
        'page_title',
        'page_link',
        'project',
        'is_active',
        'hastag',
    )

    list_filter = (
        'project',
    )


class LinkAdmin(admin.ModelAdmin):
    list_display = (
        'url',
        'project',
        #'platform',
        'is_active',
    )

    list_filter = (
        'project',
    )

    inlines = [
        SubLinkInline]


class ProxiesGroupAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'webdriver',

        'is_bot_creation_enabled',
        'is_bot_usage_enabled',

        'reuse_proxies_with_suspended_bots',

        'has_tweet_msg',
        'has_link',
        'has_tweet_img',
        'has_page_announced',
        'has_mentions',

        'total_bots_count',
        'bots_registered_count',
        'bots_using_count',

        'max_tw_bots_per_proxy_for_registration',
        'min_days_between_registrations_per_proxy',
        'max_tw_bots_per_proxy_for_usage',
        'time_between_tweets',
        'max_num_mentions_per_tweet',

    )

    def total_bots_count(self, obj):
        from core.models import TwitterBot
        return TwitterBot.objects.total_from_proxies_group(obj).count()

    def bots_registered_count(self, obj):
        from core.models import TwitterBot
        return TwitterBot.objects.registered_by_proxies_group(obj).count()

    def bots_using_count(self, obj):
        from core.models import TwitterBot
        return TwitterBot.objects.using_proxies_group(obj).count()

    exclude = ('projects',)

    list_editable = (
        'is_bot_creation_enabled',
        'is_bot_usage_enabled',
    )

    list_filter = (
        'has_tweet_msg',
        'has_link',
        'has_tweet_img',
        'has_page_announced',
        'has_mentions',
    )

    search_fields = (
        'name',
        'projects__name',
    )

    inlines = [
        ProjectProxiesGroupInline,
    ]


# Register your models here.
admin.site.register(Project, ProjectAdmin)
admin.site.register(TweetMsg)
admin.site.register(TargetUser, TargetUserAdmin)
admin.site.register(Follower, FollowerAdmin)
admin.site.register(TwitterUser, TwitterUserAdmin)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Extractor, ExtractorAdmin)
admin.site.register(Link, LinkAdmin)
admin.site.register(Hashtag)
admin.site.register(TwitterUserHasHashtag)
admin.site.register(TweetImg)
admin.site.register(ProxiesGroup, ProxiesGroupAdmin)
admin.site.register(PageLink)
admin.site.register(PageLinkHashtag)



