import datetime
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from project.models import *
from django.contrib import messages


class TargetUserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'is_active',
        'next_cursor',
        'followers_count',
        'followers_saved_today',
        'followers_saved_total',
        'followers_mentioned_today',
        'followers_mentioned_total',
    )

    def followers_saved_today(self, obj):
        return obj.followers.filter(date_saved__startswith=datetime.date.today()).count()

    def followers_saved_total(self, obj):
        return obj.followers.count()

    def followers_mentioned_today(self, obj):
        return obj.get_followers_mentioned()\
            .filter(twitter_user__mentions__date_sent__startswith=datetime.date.today()).count()

    def followers_mentioned_total(self, obj):
        return obj.get_followers_mentioned().count()

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
class PageLinkInlineFormset(forms.models.BaseInlineFormSet):
    def clean(self):
        if self.forms:
            project = self.instance
            if project.pk:
                for group in project.proxies_groups.all():
                    tweet_length = 0
                    error_msg = 'The group: ' + group.name + ' can\'t create tweet composed by'
                    if group.has_page_announced:
                        for form in self.forms:
                            if form.cleaned_data:
                                if form.cleaned_data['DELETE']:
                                    form.instance.page_title = ''
                                    form.instance.hastag = None
                        longest_page_link = max(self.forms, key = lambda p: p.instance.page_link_length()).instance
                        tweet_length += longest_page_link.page_link_length()
                        error_msg += ' page_announced: ' + longest_page_link.page_title + ','
                    if group.has_mentions:
                        mentions_length = 17 * group.max_num_mentions_per_tweet
                        tweet_length += mentions_length
                        error_msg += ' ' + str(group.max_num_mentions_per_tweet) + ' mentions,'
                    if group.has_tweet_img:
                        if project.tweet_imgs:
                            img_length = 23
                            tweet_length += img_length
                            error_msg += " and image"
                    if tweet_length > 140:
                        error_msg += ' because is too long (' + str(tweet_length) + ')'
                        raise ValidationError(error_msg)
        super(PageLinkInlineFormset, self).clean()

class PageLinkAdmin(admin.ModelAdmin):
    list_display = (
        'page_link',
        'page_title',
        'project',
        'is_active',
        'hastag',
    )

    list_filter = (
        'project',
    )


class TweetMsgInlineFormset(forms.models.BaseInlineFormSet):
    def clean(self):
        if self.forms:
            project = self.instance
            if project.pk:
                for group in project.proxies_groups.all():
                    tweet_length = 0
                    error_msg = 'The group: ' + group.name + ' can\'t create tweet composed by'
                    if group.has_tweet_msg:
                        for form in self.forms:
                            if form.cleaned_data:
                                if form.cleaned_data['DELETE']:
                                    form.instance.text = ''
                        longest_msg = max(self.forms, key = lambda p: len(p.instance.text)).instance
                        tweet_length += len(longest_msg.text)
                        error_msg += " tweet_msg: " + longest_msg.text + ','
                    if group.has_link:
                        if project.links.all():
                            longest_link = 22
                            tweet_length += longest_link + 1
                            error_msg += " link: igoo.co/x " + ','
                    if group.has_mentions:
                        mentions_length = 17 * group.max_num_mentions_per_tweet
                        tweet_length += mentions_length
                        error_msg += ' ' + str(group.max_num_mentions_per_tweet) + ' mentions,'
                    if group.has_tweet_img:
                        if project.tweet_imgs:
                            img_length = 23
                            tweet_length += img_length
                            error_msg += " and image"
                    if tweet_length > 140:
                        error_msg += ' because is too long (' + str(tweet_length) + ')'
                        raise ValidationError(error_msg)
        super(TweetMsgInlineFormset, self).clean()

class TweetMsgAdmin(admin.ModelAdmin):
    list_display = (
        'text',
        'project',
        'language',
    )

    list_filter = (
        'project',
        'language',
    )

class ProjectAdminForm(forms.ModelForm):
    class Meta:
        model = Project
    def clean(self):
        project = self.instance
        if project.pk:
            for group in project.proxies_groups.all():
                tweet_length = 0
                error_msg = 'The group: ' + group.name + ' can\'t create tweet composed by'
                if group.has_tweet_msg:
                    if project.tweet_msgs.all():
                        longest_msg = max(project.tweet_msgs.all(), key = lambda p: len(p.text))
                        tweet_length += len(longest_msg.text)
                        error_msg += " tweet_msg: " + longest_msg.text + ','
                if group.has_link:
                    if project.links.all():
                        longest_link = 22
                        tweet_length += longest_link + 1
                        error_msg += " link: igoo.co/x " + ','
                if group.has_page_announced:
                    if project.pagelink_set.all():
                        longest_page = max(project.pagelink_set.all(), key = lambda r: r.page_link_length())
                        if group.has_tweet_msg or group.has_link:
                            tweet_length += 1
                        tweet_length += longest_page.page_link_length()
                        error_msg += " page_announced: " + longest_page.page_title + ','
                if group.has_mentions:
                    mentions_length = 17 * group.max_num_mentions_per_tweet
                    tweet_length += mentions_length
                    error_msg += ' ' + str(group.max_num_mentions_per_tweet) + ' mentions,'
                if group.has_tweet_img:
                    if project.tweet_imgs:
                        img_length = 23
                        tweet_length += img_length
                        error_msg += " and image"
                if tweet_length > 140:
                    error_msg += ' because is too long (' + str(tweet_length) + ')'
                    raise ValidationError(error_msg)
        return super(ProjectAdminForm, self).clean()


class ProjectProxiesGroupInline(admin.TabularInline):
    model = ProxiesGroup.projects.through

class ProjectTweetMsgInline(admin.TabularInline):
    model = TweetMsg
    formset = TweetMsgInlineFormset

class ProjectLinkInline(admin.TabularInline):
    model = Link

class ProjectTweetImgInline(admin.TabularInline):
    model = TweetImg

class ProjectPageLinkInline(admin.TabularInline):
    model = PageLink
    formset = PageLinkInlineFormset

class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_running',
        'tweets_sent',
    )

    def tweets_sent(self, obj):
        return obj.get_tweets_sent().count()

    list_editable = (
        'is_running',
    )

    form = ProjectAdminForm

    search_fields = ('name',)
    list_display_links = ('name',)


    inlines = [
        ProjectProxiesGroupInline,
        ProjectLinkInline,
        ProjectTweetImgInline,
        ProjectPageLinkInline,
        ProjectTweetMsgInline,
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
        'bot_used__proxy_for_usage__proxy',
        'tweet_msg__text',
        'link__url',
        'page_announced__page_title',
        'page_announced__page_link',
        'mentioned_users__username',
    )

    list_filter = (
        'sending',
        'sent_ok',
        'date_created',
        'date_sent',
        'project',
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
        'language',
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
admin.site.register(TweetMsg, TweetMsgAdmin)
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



