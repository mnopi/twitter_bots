from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from core.forms import MyUserChangeForm, TwitterBotForm
from core.models import User, TwitterBot
from scrapper.scrapper import Scrapper
from django.contrib import messages
from scrapper.accounts.twitter import TwitterScrapper
from twitter_bots.settings import LOGGER


class MyUserAdmin(UserAdmin):
    form = MyUserChangeForm


class TwitterBotAdmin(admin.ModelAdmin):
    list_display = ('username', 'it_works', 'is_manually_registered',
                    'email_registered_ok', 'twitter_registered_ok', 'twitter_confirmed_email_ok',
                    'date', 'proxy', 'proxy_provider', 'user_agent', 'webdriver')
    search_fields = ('real_name', 'username', 'email', 'real_name')
    ordering = ('-date',)
    list_display_links = ('username',)

    actions = [
        'open_browser_instance',
        'login_email_account',
        'login_twitter_account',
        'perform_registrations',
        'create_new_bot',
        'set_tw_profile',
        'confirm_twitter_email',
        'create_bots',
        'create_kamikaze_bot',
        'create_n_kamikaze_bots',
        'send_tweet',
        'send_tweet_from_any_valid_kamikaze_bot',
        'send_tweets_from_any_valid_kamikaze_bot',
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

    def perform_registrations(self, request, queryset):
        if queryset.count() == 1:
            user = queryset[0]
            try:
                user.perform_registrations()
                self.message_user(request, "Registrations performed sucessfully for user %s" % user.username)
            except Exception:
                self.message_user(request, "There was errors performing registrations for %s." % user.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    perform_registrations.short_description = "Perform registrations"

    def create_new_bot(self, request, queryset):
        bot = None
        try:
            bot = TwitterBot.objects.create_bots(1)[0]
            bot.perform_registrations()
            self.message_user(request, "Bot %s created successfully" % bot.username)
        except Exception:
            if hasattr(bot, 'username'):
                msg = "There was errors creating bot \"%s\"." % bot.username
            else:
                msg = "Fatal error creating bot"
            LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    create_new_bot.short_description = "Create new bot"

    def set_twitter_profile(self, request, queryset):
        if queryset.count() == 1:
            user = queryset[0]
            try:
                user.set_tw_profile()
                self.message_user(request, "Profile set ok for twitter user: %s" % user.username)
            except Exception:
                self.message_user(request, "There was errors setting twitter profile for user: %s." % user.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    set_twitter_profile.short_description = "Set twitter profile"

    def confirm_twitter_email(self, request, queryset):
        if queryset.count() == 1:
            user = queryset[0]
            try:
                user.confirm_tw_email()
                self.message_user(request, "Email confirmed ok for twitter user: %s" % user.username)
            except Exception:
                self.message_user(request, "There was errors confirming twitter email for user: %s." % user.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    confirm_twitter_email.short_description = "Confirm twitter email"

    def create_kamikaze_bot(self, request, queryset):
        try:
            TwitterBot.objects.create_bot(is_kamikaze=True, proxy='23.105.144.241:29842', proxy_provider='myprivateproxy')
            self.message_user(request, "Kamikaze bots created successfully")
        except Exception:
            msg = "There were errors creating 1 kamikaze bot"
            LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    create_kamikaze_bot.short_description = "Create 1 kamikaze bot"

    def create_n_kamikaze_bots(self, request, queryset):
        try:
            bots = TwitterBot.objects.create_bots(2, is_kamikaze=True, proxy='23.106.201.32:29842', proxy_provider='myprivateproxy')
            self.message_user(request, "Kamikaze bots created successfully")
        except Exception:
            msg = "There were errors creating kamikaze bots"
            LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    create_n_kamikaze_bots.short_description = "Create N kamikaze bots"

    def send_tweet(self, request, queryset):
        if queryset.count() == 1:
            user = queryset[0]
            try:
                user.scrapper.login()
                user.scrapper.send_mention('dmatthews555', 'hola q tal? ;-)')
                user.scrapper.close_browser()
                self.message_user(request, "%s sent tweet ok" % user.username)
            except Exception:
                self.message_user(request, "There was errors confirming twitter email for user: %s." % user.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    send_tweet.short_description = "Send tweet"

    # def create_kamikaze_bots_and_send_tweets(self, request, queryset):
    #     try:
    #         bots = TwitterBot.objects.create_bots(2, is_kamikaze=True, proxy='23.106.201.32:29842', proxy_provider='myprivateproxy')
    #         self.message_user(request, "Kamikaze bots created successfully")
    #         pass
    #     except Exception:
    #         msg = "There were errors creating kamikaze bots"
    #         LOGGER.exception(msg)
    #         self.message_user(request, msg, level=messages.ERROR)
    # create_kamikaze_bots_and_send_tweets.short_description = "Create N kamikaze bots and send tweets"

    def send_tweet_from_any_valid_kamikaze_bot(self, request, queryset):
        try:
            TwitterBot.objects.send_mention('dmatthews555', 'hola q tal? ;-)', from_kamikaze=True)
            self.message_user(request, "Tweet sent sucessfully")
        except Exception:
            msg = "There were errors creating kamikaze bots"
            LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    send_tweet_from_any_valid_kamikaze_bot.short_description = "Send tweet from any valid kamikaze bot"

    def send_tweets_from_any_valid_kamikaze_bot(self, request, queryset):
        try:
            user_list = [u.username for u in TwitterBot.objects.filter(it_works=True, is_kamikaze=True)]
            TwitterBot.objects.send_mentions(user_list, 'hola q tal? ;-)', from_kamikaze=True)
            self.message_user(request, "Tweet sent sucessfully")
        except Exception:
            msg = "There were errors creating kamikaze bots"
            LOGGER.exception(msg)
            self.message_user(request, msg, level=messages.ERROR)
    send_tweets_from_any_valid_kamikaze_bot.short_description = "Send tweets from any valid kamikaze bot"

    class CreateBotsForm(forms.Form):
        num_bots = forms.IntegerField()

    def create_bots(self, request, queryset):
        form = None

        if 'create_bots' in request.POST:
            form = self.CreateBotsForm(request.POST)

            if form.is_valid():
                num_bots = form.cleaned_data['num_bots']
                TwitterBot.objects.create_bots(num_bots)

                plural = ''
                if num_bots != 1:
                    plural = 's'

                self.message_user(request, "Successfully created %d bot%s" % (num_bots, plural))
                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = self.CreateBotsForm(initial={'num_bots': 1})

        return render_to_response('core/create_bots.html', {'bots_form': form,})
    create_bots.short_description = "Create bots [with form]"


admin.site.register(User, MyUserAdmin)
admin.site.register(TwitterBot, TwitterBotAdmin)
