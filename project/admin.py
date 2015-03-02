import datetime
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import SelectMultiple
from project.models import *
from django.contrib import messages


class TargetUserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'is_active',
        'is_suspended',
        'next_cursor',
        'followers_count',
        'followers_saved_today',
        'followers_saved_total',
        'followers_mentioned_today',
        'followers_mentioned_total',
    )

    list_editable = (
        'is_active',
        'next_cursor',
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

    search_fields = (
        'username',
        'next_cursor'
    )

    list_display_links = (
        'username',
    )

    list_filter = (
        'is_active',
        'tu_groups',
        'tu_groups__projects',
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


class HashtagAdmin(admin.ModelAdmin):
    list_display = (
        '__unicode__',
        'is_active',
        'is_available_to_extract',
        'geocode',
        'lang',
        'max_consecutive_pages_retrieved',
        'max_id',
        'current_round_user_count',
        'current_round_oldest_tweet_limit',
        'next_round_oldest_tweet_limit',
        'last_round_end_date',
        'date_last_extraction',

        'twitterusers_saved_last_hour',
        'twitterusers_saved_today',
        'twitterusers_saved_total',
        'twitterusers_mentioned_last_hour',
        'twitterusers_mentioned_today',
        'twitterusers_mentioned_total',

        'timewindow_waiting_for_next_round_passed',
        'timewindow_waiting_since_not_enough_twitterusers_passed',
    )

    list_editable = (
        'is_active',
        'geocode',
        'lang',
        'max_consecutive_pages_retrieved',
        'max_id',
    )

    def twitterusers_saved_last_hour(self, obj):
        time_threshold = utc_now() - datetime.timedelta(hours=1)
        return obj.twitter_users.filter(date_saved__gte=time_threshold).count()

    def twitterusers_mentioned_last_hour(self, obj):
        time_threshold = utc_now() - datetime.timedelta(hours=1)
        return obj.twitter_users\
            .mentioned()\
            .filter(mentions__date_sent__gte=time_threshold).count()

    def twitterusers_saved_today(self, obj):
        return obj.twitter_users.filter(date_saved__startswith=datetime.date.today()).count()

    def twitterusers_saved_total(self, obj):
        return obj.twitter_users.count()

    def twitterusers_mentioned_today(self, obj):
        return obj.twitter_users\
            .mentioned()\
            .filter(mentions__date_sent__startswith=datetime.date.today()).count()

    def twitterusers_mentioned_total(self, obj):
        return obj.twitter_users.mentioned().count()

    list_filter = (
        'is_active',
        'hashtag_groups',
        'hashtag_groups__projects',
    )


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
                        pagelink_forms = []
                        for form in self.forms:
                            if form.cleaned_data:
                                if form.cleaned_data['DELETE']:
                                    # form.instance.page_title = ''
                                    # form.instance.hashtags.all().delete()
                                    pass
                                else:
                                    pagelink_forms.append(form)

                        if pagelink_forms:
                            longest_page_link = max(pagelink_forms, key=lambda p: p.instance.length(p))
                            tweet_length += longest_page_link.instance.length(longest_page_link)
                            error_msg += ' page_announced: ' + longest_page_link.instance.page_title + ','
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
        'hashtags',
        'image',
        'languaje',
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
                            tweet_length += settings.TWEET_LINK_LENGTH + 1
                            error_msg += " link: igoo.co/x " + ','
                    if group.has_mentions:
                        mentions_length = 17 * group.max_num_mentions_per_tweet
                        tweet_length += mentions_length
                        error_msg += ' ' + str(group.max_num_mentions_per_tweet) + ' mentions,'
                    if group.has_tweet_img:
                        if project.tweet_imgs:
                            img_length = settings.TWEET_IMG_LENGTH
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
                        tweet_length += settings.TWEET_LINK_LENGTH + 1
                        error_msg += " link: igoo.co/x " + ','
                # if group.has_page_announced:
                #     if project.pagelink_set.all():
                #         longest_page = max(project.pagelink_set.all(), key = lambda r: r.page_link_length())
                #         if group.has_tweet_msg or group.has_link:
                #             tweet_length += 1
                #         tweet_length += longest_page.page_link_length()
                #         error_msg += " page_announced: " + longest_page.page_title + ','
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
    extra = 0

class FeedsGroupProxiesGroupInline(admin.TabularInline):
    model = FeedsGroup.proxies_groups.through
    extra = 0

class ProjectTUGroupInline(admin.TabularInline):
    model = TUGroup.projects.through
    extra = 0

class ProjectHashtagGroupInline(admin.TabularInline):
    model = HashtagGroup.projects.through
    extra = 0

class ProjectTweetMsgInline(admin.TabularInline):
    model = TweetMsg
    formset = TweetMsgInlineFormset
    extra = 0

class ProjectLinkInline(admin.TabularInline):
    model = Link
    extra = 0

class ProjectTweetImgInline(admin.TabularInline):
    model = TweetImg
    extra = 0

class ProjectPageLinkInline(admin.TabularInline):
    model = PageLink
    formset = PageLinkInlineFormset
    extra = 0

class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_running',
        # 'tu_group',
        # 'hashtag_group',
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
        ProjectTUGroupInline,
        ProjectHashtagGroupInline,
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
        'bot_used',
        'proxy_used',
        'type',
        'compose',
        'length',
        'date_created',
        'date_sent',
        'sending',
        'sent_ok',
        'page_announced',
        'project',
        'has_image',
    )

    def type(self, obj):
        return obj.print_type()

    def proxy_used(self, obj):
        return obj.bot_used.proxy_for_usage
    proxy_used.admin_order_field = 'bot_used__proxy_for_usage'

    list_display_links = ('compose',)

    ordering = ('-sending', '-sent_ok')

    exclude = (
        'mentioned_users',
    )

    list_per_page = 15

    search_fields = (
        'bot_used__username',
        'bot_used__proxy_for_usage__proxy',
        'bot_used__proxy_for_usage__proxy_provider',
        'tweet_msg__text',
        'link__url',
        'page_announced__page_title',
        'page_announced__page_link',
        'mentioned_users__username',
        # 'mentioned_bots__username',
    )

    class TypeFilter(admin.SimpleListFilter):
        title = 'Destination'
        parameter_name = 'destination'

        def lookups(self, request, model_admin):
            return (
                ('mutweet', 'MU Tweet',),
                ('mctweet', 'MC Tweet',),
                ('ftweet', 'F Tweet',),
            )

        def queryset(self, request, queryset):
            if self.value() == 'mutweet':
                return queryset.filter(mentioned_users__isnull=False, mentioned_bots__isnull=True)
            elif self.value() == 'mctweet':
                return queryset.filter(mentioned_users__isnull=True, mentioned_bots__isnull=False)
            elif self.value() == 'ftweet':
                return queryset.filter(project__isnull=True, feed_item__isnull=False)

    list_filter = (
        TypeFilter,
        'sending',
        'sent_ok',
        'date_created',
        'date_sent',
        'project',
        'bot_used__proxy_for_usage__proxy_provider',
        'link',
        'page_announced',
    )
    # ordering = ('-date',)
    # list_display_links = ('username',)

    actions = (
        'send_selected_tweets',
    )

    def send_selected_tweets(self, request, queryset):
        sent_ok_count = 0
        for tweet_to_send in queryset:
            tweet_to_send.sending = False
            tweet_to_send.save()
            if tweet_to_send.can_be_sent():
                tweet_to_send.sending = True
                tweet_to_send.save()
                tweet_to_send.send()
                sent_ok_count += 1
            else:
                self.message_user(request, 'Tweet %i can\'t be sent now' % tweet_to_send.pk, level=messages.WARNING)
        self.message_user(request, "%i tweets sent ok" % sent_ok_count)
    send_selected_tweets.short_description = "Send selected tweets"


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
        'is_mentioned',
    )

    def is_mentioned(self, obj):
        return obj.mentions.exists()
    is_mentioned.boolean = True

    search_fields = (
        'username',
        'hashtags__q',
    )

    class MentionedUnmentionedFilter(admin.SimpleListFilter):
        title = 'Mention'
        parameter_name = 'mention'

        def lookups(self, request, model_admin):
            return (
                ('mentioned', 'Mentioned',),
                ('unmentioned', 'Unmentioned',),
            )

        def queryset(self, request, queryset):
            if self.value() == 'mentioned':
                return queryset.filter(mentions__isnull=False)
            elif self.value() == 'unmentioned':
                return queryset.filter(mentions__isnull=True)

    list_filter = (
        MentionedUnmentionedFilter,
        'date_saved',
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
        'is_suspended',
        'date_suspended',
    )

    search_fields = (
        'twitter_bot__username',
    )
    list_filter = (
        'date_created',
        'last_request_date',
        'is_rate_limited',
        'is_suspended',
        'date_suspended',
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
        SubLinkInline
    ]


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
        'has_following_activated',

        'total_proxies',
        'proxies_avaiable_for_usage_num',
        'total_bots_num',
        'bots_using_num',

        'max_tw_bots_per_proxy_for_registration',
        'min_days_between_registrations_per_proxy',
        'max_tw_bots_per_proxy_for_usage',
        'time_between_tweets',
        'max_num_mentions_per_tweet',

    )

    def total_proxies(self, obj):
        return obj.proxies.count()

    def proxies_avaiable_for_usage_num(self, obj):
        return obj.proxies.available_to_assign_bots_for_use().count()

    def total_bots_num(self, obj):
        from core.models import TwitterBot
        return TwitterBot.objects.total_from_proxies_group(obj).count()

    def bots_using_num(self, obj):
        from core.models import TwitterBot
        return TwitterBot.objects.with_proxy_connecting_ok().using_proxies_group(obj).count()

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
        FeedsGroupProxiesGroupInline,
    ]


class TweetCheckingMentionAdmin(admin.ModelAdmin):
    list_display = (
        'compose',
        'destination_bot_is_checking_mention',
        'destination_bot_checked_mention',
        'destination_bot_checked_mention_date',
        'mentioning_works',
        # 'date_sent',
        # 'bot_used',
    )

    def compose(self, obj):
        return '%s -> %s' % (obj.tweet.bot_used.username, obj.tweet.compose())

    def date_sent(self, obj):
        return obj.tweet.date_sent

    def bot_used(self, obj):
        return obj.tweet.bot_used

    search_fields = (
        'tweet__bot_used__username',
        'tweet__tweet_msg__text',
        'tweet__link__url',
        'tweet__page_announced__page_title',
        'tweet__page_announced__page_link',
        'tweet__mentioned_bots__username',
    )

    list_filter = (
        'mentioning_works',
    )

    raw_id_fields = (
        'tweet',
    )


class TUGroupAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.ManyToManyField: {
            'widget': SelectMultiple(attrs={'size':'30'})
        },
    }


class TwitterBotFollowingAdmin(admin.ModelAdmin):
    list_display = (
        '__unicode__',
        'performed_follow',
        'followed_ok',
        'date_followed',
    )

    list_filter = (
        'performed_follow',
        'followed_ok',
        'date_followed',
    )


class FeedItemAdmin(admin.ModelAdmin):
    list_display = (
        '__unicode__',
        'feed'
    )

    list_filter = (
        'feed',
        'feed__feeds_groups'
    )


# Register your models here.
admin.site.register(Project, ProjectAdmin)
admin.site.register(TweetMsg, TweetMsgAdmin)
admin.site.register(TargetUser, TargetUserAdmin)
admin.site.register(Follower, FollowerAdmin)
admin.site.register(TwitterUser, TwitterUserAdmin)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Extractor, ExtractorAdmin)
admin.site.register(Link, LinkAdmin)
admin.site.register(Hashtag, HashtagAdmin)
admin.site.register(TwitterUserHasHashtag)
admin.site.register(TweetImg)
admin.site.register(ProxiesGroup, ProxiesGroupAdmin)
admin.site.register(PageLink)
admin.site.register(PageLinkHashtag)
admin.site.register(TUGroup, TUGroupAdmin)
admin.site.register(HashtagGroup)
admin.site.register(TweetCheckingMention, TweetCheckingMentionAdmin)

admin.site.register(Feed)
admin.site.register(FeedsGroup)
admin.site.register(FeedItem, FeedItemAdmin)

admin.site.register(TwitterBotFollowing, TwitterBotFollowingAdmin)



