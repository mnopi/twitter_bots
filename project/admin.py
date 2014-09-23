from django.contrib import admin
from project.models import *
from django.contrib import messages


class TargetUserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'next_cursor',
        'followers_count',
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
            target_user.extract_followers()
            self.message_user(request, "Followers extracted ok from %s" % target_user.username)
        else:
            self.message_user(request, "Only select one user for this action", level=messages.WARNING)
    extract_followers.short_description = "Extract all followers"


# Register your models here.
admin.site.register(Project)
admin.site.register(TweetMsg)
admin.site.register(TargetUser, TargetUserAdmin)
admin.site.register(Follower)
admin.site.register(TwitterUser)
admin.site.register(Tweet)


