from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from core.forms import MyUserChangeForm
from core.models import User, TwitterBot, Proxy
from project.models import ProxiesGroup
from scrapper.scrapper import Scrapper
from django.contrib import messages
from scrapper.accounts.twitter import TwitterScrapper
from twitter_bots import settings


class MyUserAdmin(UserAdmin):
    form = MyUserChangeForm


class ValidBotListFilter(admin.SimpleListFilter):
    title = 'Bot type'
    parameter_name = 'bot_type'

    def lookups(self, request, model_admin):
        return (
            ('completed', 'completed'),
            ('uncompleted', 'uncompleted'),
            ('unregistered', 'unregistered'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'uncompleted':
            return TwitterBot.objects.get_uncompleted_bots()
        if self.value() == 'completed':
            return TwitterBot.objects.get_completed_bots()
        if self.value() == 'unregistered':
            return TwitterBot.objects.get_unregistered_bots()

class TwitterBotAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'is_being_created',
        'is_dead',
        'is_suspended',
        'is_suspended_email',
        # 'is_manually_registered',
        'email_registered_ok',
        'twitter_registered_ok',
        'twitter_confirmed_email_ok',
        'twitter_avatar_completed',
        'twitter_bio_completed',
        'date',
        'proxy_for_registration',
        'proxy',
        # 'user_agent',
        'webdriver',
    )
    search_fields = (
        'real_name',
        'username',
        'email',
        'proxy__proxy',
        'proxy__proxy_provider',
    )
    list_filter = (
        ValidBotListFilter,
        'webdriver',
        'date',
        'is_dead',
        'is_suspended',
        'is_suspended_email',
        'proxy__proxy_provider',
    )
    ordering = ('-date',)
    list_display_links = ('username',)

    actions = [
        'open_browser_instance',
        'login_email_account',
        'login_twitter_account',
        'complete_creation',
        'set_twitter_profile',
        'confirm_twitter_email',
        'send_tweet_from_selected_bot',
        # 'send_mention',
        # 'send_mention_from_any_valid_bot',
        # 'send_mentions_from_any_valid_bot',
        'create_bot_from_fixed_ip',
        'send_pending_tweets',
        'send_pending_tweet_from_selected_bot',
        'make_feed_tweet_to_send_for_selected_bot',
    ]

    def open_browser_instance(self, request, queryset):
        if queryset.count() == 1:
            user = queryset[0]
            scr = Scrapper(user, force_firefox=True)
            scr.open_browser()
            scr.wait_until_closed_windows()
            scr.close_browser()
            self.message_user(request, "Browser instance closed for user %s" % user.username)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    open_browser_instance.short_description = "Open browser instance"

    def login_email_account(self, request, queryset):
        if queryset.count() == 1:
            user = queryset[0]
            scr = Scrapper(user)
            try:
                scr.login_email_account()
                scr.wait_until_closed_windows()
                self.message_user(request, "Login performed sucessfully for user %s" % user.username)
            except Exception:
                self.message_user(request, "Invalid login for %s. Was put as invalid." % user.email, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    login_email_account.short_description = "Perform login on email account"

    def login_twitter_account(self, request, queryset):
        if queryset.count() == 1:
            user = queryset[0]
            scr = TwitterScrapper(user)
            try:
                scr.open_browser()
                scr.login()
                # mantenemos hasta que se cierre la ventana de firefox
                scr.wait_until_closed_windows()
                scr.close_browser()
                self.message_user(request, "Login performed sucessfully for user %s" % user.username)
            except Exception:
                self.message_user(request, "Invalid login for %s. Was put as invalid." % user.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    login_twitter_account.short_description = "Perform login on twitter"

    def complete_creation(self, request, queryset):
        if queryset.count() == 1:
            bot = queryset[0]
            try:
                bot.complete_creation()
                self.message_user(request, "Bot %s creation completed ok" % bot.username)
            except Exception:
                self.message_user(request, "Error completing bot %s creation" % bot.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one bot for this action", level=messages.WARNING)
    complete_creation.short_description = "Complete bot creation"

    def create_new_bot(self, request, queryset):
        try:
            TwitterBot.objects.clean_unregistered_bots()
            TwitterBot.objects.create_bot()
            self.message_user(request, "Bot created successfully")
        except Exception:
            self.message_user(request, 'Error creating bot', level=messages.ERROR)
    create_new_bot.short_description = "Create new bot"

    def process_bot(self, request, queryset):
        if queryset.count() == 1:
            bot = queryset[0]
            try:
                bot.complete_creation()
                self.message_user(request, "Bot %s processed ok" % bot.username)
            except Exception:
                self.message_user(request, "There was errors processing bot %s." % bot.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    process_bot.short_description = "Process bot"

    def process_all_bots(self, request, queryset):
        try:
            TwitterBot.objects.process_all_bots()
            self.message_user(request, "All bots processed sucessfully")
        except Exception:
            msg = "There were errors processing bots"
            settings.LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    process_all_bots.short_description = "Process all bots"

    def set_twitter_profile(self, request, queryset):
        if queryset.count() == 1:
            bot = queryset[0]
            try:
                bot.set_tw_profile()
                self.message_user(request, "Profile set ok for twitter user: %s" % bot.username)
            except Exception:
                self.message_user(request, "There was errors setting twitter profile for user: %s." % bot.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    set_twitter_profile.short_description = "Set twitter profile"

    def confirm_twitter_email(self, request, queryset):
        if queryset.count() == 1:
            bot = queryset[0]
            try:
                bot.confirm_tw_email()
                self.message_user(request, "Email confirmed ok for bot: %s" % bot.username)
            except Exception:
                self.message_user(request, "There was errors confirming twitter email for bot: %s." % bot.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    confirm_twitter_email.short_description = "Confirm twitter email"

    def create_bot_from_fixed_ip(self, request, queryset):
        try:
            TwitterBot.objects.create_bot(proxy='23.106.201.32:29842', proxy_provider='myprivateproxy')
            self.message_user(request, "Bot created successfully")
        except Exception:
            msg = "There were errors creating 1 bot"
            settings.LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    create_bot_from_fixed_ip.short_description = "Create 1 bot [from fixed ip]"

    def send_tweet_from_pendings(self, request, queryset):
        TwitterBot.objects.send_tweet_from_pending_queue()
        self.message_user(request, "Tweet sent sucessfully")
    send_tweet_from_pendings.short_description = "Send pending tweet"

    def send_pending_tweets(self, request, queryset):
        try:
            TwitterBot.objects.send_pending_tweets()
            self.message_user(request, "All pending tweets sent sucessfully")
        except Exception:
            msg = "There were errors sending pending tweets"
            settings.LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    send_pending_tweets.short_description = "Send all pending tweets"

    def make_feed_tweet_to_send_for_selected_bot(self, request, queryset):
        if queryset.count() == 1:
            bot = queryset[0]
            try:
                bot.make_feed_tweet_to_send()
                self.message_user(request, "feed tweet creted ok")
            except Exception as e:
                self.message_user(request, "Error creating feed tweet", level=messages.ERROR)
                raise e
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    make_feed_tweet_to_send_for_selected_bot.short_description = "Make feed tweet for selected bot"


class ProxyAdmin(admin.ModelAdmin):
    list_display = (
        'proxy',
        'proxy_provider',
        'proxies_group',
        'is_in_proxies_txts',
        'num_bots_registered',
        'num_bots_using',
        'is_unavailable_for_registration',
        'date_unavailable_for_registration',
        'is_unavailable_for_use',
        'date_unavailable_for_use',
        'is_phone_required',
        'date_phone_required',
    )
    def num_bots_registered(self, obj):
        return obj.twitter_bots_registered.count()

    def num_bots_using(self, obj):
        return obj.twitter_bots_using.count()

    search_fields = (
        'proxy',
    )

    # FILTERS

    class HasBotsListFilter(admin.SimpleListFilter):
        title = 'Has bots'
        parameter_name = 'has_bots'

        def lookups(self, request, model_admin):
            return (
                ('bots_registered', 'with bots registered',),
                ('no_bots_registered', 'without bots registered',),

                ('bots_using', 'with bots using'),
                ('no_bots_using', 'without bots using'),

                ('at_least_one_bot', 'with at least one bot'),
                ('no_bots', 'without bots'),
            )

        def queryset(self, request, queryset):
            if self.value() == 'bots_registered':
                return Proxy.objects.with_bots_registered(queryset)
            if self.value() == 'no_bots_registered':
                return Proxy.objects.without_bots_registered()

            if self.value() == 'bots_using':
                return Proxy.objects.with_bots_using()
            if self.value() == 'no_bots_using':
                return Proxy.objects.without_bots_using()

            if self.value() == 'at_least_one_bot':
                return Proxy.objects.with_bots()
            if self.value() == 'no_bots':
                return Proxy.objects.without_bots()


    list_filter = (
        HasBotsListFilter,
        'proxies_group',
        'proxy_provider',
        'is_in_proxies_txts',

        'date_not_in_proxies_txts',
        'is_unavailable_for_registration',
        'date_unavailable_for_registration',
        'is_unavailable_for_use',
        'date_unavailable_for_use',
        'is_phone_required',
        'date_phone_required',
    )

    actions = [
        'assign_proxies_group',
    ]

    def assign_proxies_group(self, request, queryset):
        # http://www.jpichon.net/blog/2010/08/django-admin-actions-and-intermediate-pages/
        # http://sysmagazine.com/posts/140409/
        from django import forms
        class AssignProxiesForm(forms.Form):
            _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
            action = forms.CharField(widget=forms.HiddenInput)
            proxies_group = forms.ModelChoiceField(queryset=ProxiesGroup.objects.all(), required=False)

        if 'apply' in request.POST:
            form = AssignProxiesForm(request.POST)

            if form.is_valid():
                proxies_group = form.cleaned_data['proxies_group']

                count = 0
                for proxy in queryset:
                    proxy.proxies_group = proxies_group
                    proxy.save()
                    count += 1

                self.message_user(request, 'Successfully assigned proxies_group "%s" to %d proxies' % (proxies_group, count))
                return HttpResponseRedirect(request.get_full_path())
        else:
            ctx = {
                'proxies_group_form': AssignProxiesForm(
                    initial={
                        '_selected_action': [obj.pk for obj in queryset],
                        'action': request.POST.get('action'),
                    }
                )
            }
            return render_to_response('core/assign_proxies_group.html', context_instance=RequestContext(request, ctx))


admin.site.register(User, MyUserAdmin)
admin.site.register(TwitterBot, TwitterBotAdmin)
admin.site.register(Proxy, ProxyAdmin)