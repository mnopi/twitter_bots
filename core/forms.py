from django.contrib.auth.forms import UserChangeForm
from django.forms import ModelForm
from core.models import User, TwitterBot
from scrapper.utils import *
import random


class MyUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class TwitterBotForm(ModelForm):
    class Meta:
        model = TwitterBot

    # def _auto_populate_form(self):
    #     full_name = names.get_full_name()
    #
    #     self.data['real_name'] = full_name
    #     self.data['email'] = generate_random_username(full_name) + '@hushmail.com'
    #     self.data['username'] = generate_random_username(full_name)
    #     self.data['password_email'] = generate_random_string()
    #     self.data['password_twitter'] = generate_random_string()
    #     self.data['user_agent'] = ua.random

    def full_clean(self):
        # self._auto_populate_form()
        super(TwitterBotForm, self).full_clean()