from core.models import TwitterBot, Proxy


from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):

    def handle(self, *args, **options):
        bots = None
        with open('bots proxies.tab.txt') as f:
            bots = f.readlines()
        bots = [b.replace('"', '').split('\t') for b in bots]
        for b in bots:
            proxy = b[10]
            username = b[3]
            bot = TwitterBot.objects.filter(username=username)
            if bot.exists():
                bot = bot.first()
                proxy = Proxy.objects.get(proxy=proxy)
                bot.proxy = proxy
                bot.save()
