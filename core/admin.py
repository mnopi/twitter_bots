import datetime
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from core.forms import MyUserChangeForm, TwitterBotForm
from core.models import User, TwitterBot, Proxy
from project.models import Tweet
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
            ('valid', 'valid'),
            ('test', 'test'),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value() == 'valid':
            return queryset\
                .filter(it_works=True, webdriver='PH')\
                .exclude(proxy='tor', must_verify_phone=True)
        if self.value() == 'test':
            return queryset.filter(webdriver='FI')

class TwitterBotAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'is_active',
        # 'is_manually_registered',
        'email_registered_ok',
        'twitter_registered_ok',
        'twitter_confirmed_email_ok',
        'twitter_avatar_completed',
        'twitter_bio_completed',
        'date',
        'proxy',
        # 'user_agent',
        'webdriver',
    )
    search_fields = ('real_name', 'username', 'email', 'real_name')
    list_filter = (ValidBotListFilter,)
    ordering = ('-date',)
    list_display_links = ('username',)

    actions = [
        'open_browser_instance',
        'login_email_account',
        'login_twitter_account',
        'process_bot',
        'process_all_bots',
        'create_new_bot',
        'create_bots',
        'set_twitter_profile',
        'confirm_twitter_email',
        'send_tweet_from_selected_bot',
        # 'send_mention',
        # 'send_mention_from_any_valid_bot',
        # 'send_mentions_from_any_valid_bot',
        'create_bot_from_fixed_ip',
        'send_pending_tweets',
        'send_pending_tweet_from_selected_bot',
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
                bot.register_accounts()
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

    def send_tweet_from_selected_bot(self, request, queryset):
        if queryset.count() == 1:
            bot = queryset[0]
            try:
                tweet = bot.make_tweet_to_send()
                if tweet:
                    bot.send_tweet(tweet)
                self.message_user(request, "%s sent tweet ok" % bot.username)
            except Exception:
                self.message_user(request, "Error sending tweet from bot %s" % bot.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    send_tweet_from_selected_bot.short_description = "Send tweet from selected bot"

    def send_tweet_from_pendings(self, request, queryset):
        TwitterBot.objects.send_tweet()
        self.message_user(request, "Tweet sent sucessfully")
    send_tweet_from_pendings.short_description = "Send pending tweet"

    def send_pending_tweets(self, request, queryset):
        try:
            TwitterBot.objects.send_tweets()
            self.message_user(request, "All pending tweets sent sucessfully")
        except Exception:
            msg = "There were errors sending pending tweets"
            settings.LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    send_pending_tweets.short_description = "Send all pending tweets"


class ProxyAdmin(admin.ModelAdmin):
    list_display = (
        'proxy',
        'proxy_provider',
        'is_unavailable_for_registration',
        'date_unavailable_for_registration',
        'is_unavailable_for_use',
        'date_unavailable_for_use',
        'is_phone_required',
        'date_phone_required',
    )

    search_fields = (
        'proxy',
    )
    list_filter = (
        'proxy_provider',
        'is_unavailable_for_registration',
        'date_unavailable_for_registration',
        'is_unavailable_for_use',
        'date_unavailable_for_use',
        'is_phone_required',
        'date_phone_required',
    )


admin.site.register(User, MyUserAdmin)
admin.site.register(TwitterBot, TwitterBotAdmin)
admin.site.register(Proxy, ProxyAdmin)
