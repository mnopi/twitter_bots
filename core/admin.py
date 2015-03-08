from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from core.forms import MyUserChangeForm
from core.models import User, TwitterBot, Proxy
from project.exceptions import NoAvailableProxiesToAssignBotsForUse, NoMoreAvailableProxiesForRegistration
from project.models import ProxiesGroup
from core.scrapper.scrapper import Scrapper
from django.contrib import messages
from core.scrapper.accounts.twitter import TwitterScrapper
from twitter_bots import settings

class YesNoFilter(admin.SimpleListFilter):
    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes',),
            ('0', 'No',),
        )

    def yes(self):
        return self.value() == '1'

    def no(self):
        return self.value() == '0'


class MyUserAdmin(UserAdmin):
    form = MyUserChangeForm


class TwitterBotAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'get_group',
        'is_being_created',
        'is_dead',
        'date_death',
        'is_suspended',
        'date_suspended_twitter',
        'num_suspensions_lifted',
        'is_suspended_email',
        'email_registered_ok',
        'twitter_registered_ok',
        'twitter_confirmed_email_ok',
        'twitter_avatar_completed',
        'twitter_bio_completed',
        'date',
        'proxy_for_registration',
        'proxy_for_usage',
        'get_webdriver',
    )

    list_select_related = (
        'proxy_for_registration',
        'proxy_for_usage',
        'proxy_for_usage__proxies_group'
    )

    list_per_page = 50

    search_fields = (
        'real_name',
        'username',
        'email',
        'proxy_for_registration__proxy',
        'proxy_for_registration__proxy_provider',
        'proxy_for_usage__proxy',
        'proxy_for_usage__proxy_provider',
    )

    class BotCompletedFilter(YesNoFilter):
        title = 'Is completed'
        parameter_name = 'is_completed'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.completed()
            elif self.no():
                return queryset.uncompleted()

    class BotUsableFilter(YesNoFilter):
        title = 'Usable (reg. proxy)'
        parameter_name = 'usable'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.usable_regardless_of_proxy()
            elif self.no():
                return queryset.unusable_regardless_of_proxy()

    class HasSomeAccountFilter(YesNoFilter):
        title = 'Has some account'
        parameter_name = 'has_some_account'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.with_some_account_registered()
            elif self.no():
                return queryset.without_any_account_registered()

    class HasProxyWorkingFilter(YesNoFilter):
        title = 'Has proxy working'
        parameter_name = 'has_proxy_working'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.with_proxy_connecting_ok()
            elif self.no():
                return queryset.with_proxy_not_connecting_ok()

    list_filter = (
        BotCompletedFilter,
        BotUsableFilter,
        HasSomeAccountFilter,
        HasProxyWorkingFilter,
        'proxy_for_usage__proxies_group__webdriver',
        'proxy_for_usage__proxies_group',
        'proxy_for_usage__is_in_proxies_txts',
        'date',
        'is_dead',
        'is_suspended',
        'is_suspended_email',
        'twitter_registered_ok',
    )
    ordering = ('-date',)
    list_display_links = (
        'username',
    )

    actions = [
        'open_browser_instance',
        # 'login_email_account',
        # 'login_twitter_account',
        'complete_creation',
        # 'set_twitter_profile',
        # 'confirm_twitter_email',
        'send_tweet_from_selected_bot',
        # 'send_mention',
        # 'send_mention_from_any_valid_bot',
        # 'send_mentions_from_any_valid_bot',
        # 'create_bot_from_fixed_ip',
        'send_pending_tweets',
        'send_pending_tweet_from_selected_bot',
        'make_feed_tweet_to_send_for_selected_bot',
        'move_to_another_proxies',
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
                if bot.has_to_complete_creation():
                    self.message_user(request, "Bot %s not completed ok yet" % bot.username, level=messages.WARNING)
                else:
                    self.message_user(request, "Bot %s creation completed ok" % bot.username)
            except Exception:
                self.message_user(request, "Error completing bot %s creation" % bot.username, level=messages.ERROR)
        else:
            self.message_user(request, "Only select one bot for this action", level=messages.WARNING)
    complete_creation.short_description = "Complete bot creation"

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
        TwitterBot.objects.send_twusermention_from_pending_queue()
        self.message_user(request, "Tweet sent sucessfully")
    send_tweet_from_pendings.short_description = "Send pending tweet"

    def send_pending_tweets(self, request, queryset):
        try:
            TwitterBot.objects.send_mentions_from_queue()
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

    def move_to_another_proxies(self, request, queryset):
        """Al bot se le asignan proxies del grupo elegido"""

        # http://www.jpichon.net/blog/2010/08/django-admin-actions-and-intermediate-pages/
        # http://sysmagazine.com/posts/140409/
        from django import forms
        from querysets import TwitterBotQuerySet
        class AssignProxiesForm(forms.Form):
            _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
            action = forms.CharField(widget=forms.HiddenInput)
            proxies_group = forms.ModelChoiceField(queryset=ProxiesGroup.objects.all(), required=False)

        if 'apply' in request.POST:
            form = AssignProxiesForm(request.POST)

            if form.is_valid():
                proxies_group = form.cleaned_data['proxies_group']

                assigned_count = 0
                for bot in queryset:
                    try:
                        bot.assign_proxy(proxies_group=proxies_group)
                        assigned_count += 1
                    except (NoMoreAvailableProxiesForRegistration,
                        NoAvailableProxiesToAssignBotsForUse):
                        self.message_user(request, '%d bots with new proxy. %d left to assign (group completed)' %
                                          (assigned_count, (queryset.count() - assigned_count)), level=messages.ERROR)

                self.message_user(request, '%d bots assigned ok to group %s' % (assigned_count, proxies_group))
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

    raw_id_fields = (
        'proxy_for_registration',
        'proxy_for_usage',
    )


class ProxyAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        return super(ProxyAdmin, self).queryset(request)\
            .select_related('proxies_group', 'twitter_bots_registered', 'twitter_bots_using')
            # .annotate(num_bots_registered=Count('twitter_bots_registered'))\
            # .annotate(num_bots_using=Count('twitter_bots_using'))

    list_display = (
        'proxy',
        'proxy_provider',
        'proxies_group',
        'is_in_proxies_txts',
        'num_bots_registered',
        'num_bots_active',
        'num_bots_suspended',
        'num_bots_dead',
        'date_added',
        'is_unavailable_for_registration',
        'date_unavailable_for_registration',
        'is_unavailable_for_use',
        'date_unavailable_for_use',
        'is_phone_required',
        'date_phone_required',
    )

    def num_bots_registered(self, obj):
        return obj.twitter_bots_registered.count()

    def num_bots_active(self, obj):
        return obj.get_active_bots_using().count()

    def num_bots_suspended(self, obj):
        return obj.get_suspended_bots().count()

    def num_bots_dead(self, obj):
        return obj.get_dead_bots().count()

    list_select_related = (
        'proxies_group',
        'twitter_bots_registered',
        'twitter_bots_using',
    )

    list_per_page = 100

    search_fields = (
        'proxy',
    )

    ordering = ('-date_added',)

    # FILTERS

    class IsConnectionOkListFilter(YesNoFilter):
        title = 'Is connection ok'
        parameter_name = 'is_connection_ok'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.connection_ok()
            elif self.no():
                return queryset.connection_fail()

    class ValidForBotRegistrationListFilter(YesNoFilter):
        title = 'Valid for bot registration'
        parameter_name = 'valid_for_bot_registration'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.available_to_assign_bots_for_registration()
            elif self.no():
                return queryset.unavailable_to_assign_bots_for_registration()

    class ValidForBotUsageListFilter(YesNoFilter):
        title = 'Valid for bot usage'
        parameter_name = 'valid_for_bot_usage'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.available_to_assign_bots_for_use()
            elif self.no():
                return queryset.unavailable_to_assign_bots_for_use()

    class HasCompletedBotsListFilter(YesNoFilter):
        title = 'Has completed bots'
        parameter_name = 'has_completed_bots'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.with_completed_bots()
            elif self.no():
                return queryset.without_completed_bots()

    class HasRegisteredBotsListFilter(YesNoFilter):
        title = 'Has registered bots'
        parameter_name = 'has_registered_bots'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.with_some_registered_bot()
            elif self.no():
                return queryset.without_any_bot_registered()

    class HasBotsUsingListFilter(YesNoFilter):
        title = 'Has bots using'
        parameter_name = 'has_bots_using'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.with_some_bot_using()
            elif self.no():
                return queryset.without_bots_using()

    class HasSuspendedBotsListFilter(YesNoFilter):
        title = 'Has suspended bots'
        parameter_name = 'has_suspended_bots'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.with_some_suspended_bot()
            elif self.no():
                return queryset.without_any_suspended_bot()

    class HasDeadBotsListFilter(YesNoFilter):
        title = 'Has dead bots'
        parameter_name = 'has_dead_bots'

        def queryset(self, request, queryset):
            if self.yes():
                return queryset.with_some_dead_bot()
            elif self.no():
                return queryset.without_any_dead_bot()

    list_filter = (
        IsConnectionOkListFilter,
        ValidForBotRegistrationListFilter,
        ValidForBotUsageListFilter,
        # ValidForAssignGroupListFilter,
        HasCompletedBotsListFilter,
        HasRegisteredBotsListFilter,
        HasBotsUsingListFilter,
        HasSuspendedBotsListFilter,
        HasDeadBotsListFilter,
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
        'mark_as_unavailable_for_use',
        'mark_as_available_for_use',
    ]

    def assign_proxies_group(self, request, queryset):
        return assign_proxies_group(self, request, queryset)

    def mark_as_unavailable_for_use(self, request, queryset):
        try:
            Proxy.objects.mark_as_unavailable_for_use(queryset)
            self.message_user(request, 'proxies successfully marked as unavailable for use')
        except Exception as e:
            self.message_user(request, 'Error marking proxies as unavailable', level=messages.ERROR)
            raise e

    def mark_as_available_for_use(self, request, queryset):
        try:
            Proxy.objects.mark_as_available_for_use(queryset)
            self.message_user(request, 'proxies successfully marked as unavailable for use')
        except:
            self.message_user(request, 'Error marking proxies as unavailable', level=messages.ERROR)

def assign_proxies_group(admin_obj, request, queryset):
    """Al proxy se le asigna otro grupo"""

    # http://www.jpichon.net/blog/2010/08/django-admin-actions-and-intermediate-pages/
    # http://sysmagazine.com/posts/140409/
    from django import forms
    from querysets import TwitterBotQuerySet
    class AssignProxiesForm(forms.Form):
        _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
        action = forms.CharField(widget=forms.HiddenInput)
        proxies_group = forms.ModelChoiceField(queryset=ProxiesGroup.objects.all(), required=False)

    def get_proxy_queryset():
        if type(queryset) is TwitterBotQuerySet:
            proxies_pks = queryset.values_list('proxy_for_usage__pk', flat=True)
            return Proxy.objects.filter(pk__in=proxies_pks)
        else:
            return queryset

    def sucessfull_msg():
        if type(queryset) is TwitterBotQuerySet:
            return 'Successfully assigned proxies_group "%s" to %d proxies (%d bots were reassigned)' % \
                   (proxies_group, count, TwitterBot.objects.using_proxies_group(proxies_group).count())
        else:
            return 'Successfully assigned proxies_group "%s" to %d proxies' % (proxies_group, count)

    if 'apply' in request.POST:
        form = AssignProxiesForm(request.POST)

        if form.is_valid():
            proxies_group = form.cleaned_data['proxies_group']

            count = 0
            for proxy in get_proxy_queryset():
                proxy.proxies_group = proxies_group
                proxy.save()
                count += 1

            admin_obj.message_user(request, sucessfull_msg())
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