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
        'create_bots',
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

    def set_tw_profile(self, request, queryset):
        if queryset.count() == 1:
            user = queryset[0]
            try:
                user.set_tw_profile()
                self.message_user(request, "Profile set ok for twitter user: %s" % user.username)
            except Exception:
                self.message_user(request, "There was errors setting twitter profile for user: %s." % user.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    set_tw_profile.short_description = "Set twitter profile"

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
