# -*- coding: utf-8 -*-
import datetime
from django.db.models import Q, Count, Max
from django.db.models.query import QuerySet
from scrapper.exceptions import NoMoreAvailableProxiesForUsage, NoMoreAvailableProxiesForRegistration
from scrapper.utils import utc_now, is_lte_than_days_ago
from twitter_bots import settings


class TwitterBotQuerySet(QuerySet):
    def unregistered(self):
        return self.filter(email_registered_ok=False, twitter_registered_ok=False)

    def usable(self):
        return self.filter(
                webdriver='PH',
                is_being_created=False
            ).\
            with_valid_proxy_for_usage()

    def registrable(self):
        "Saca robots que puedan continuar el registro"
        self.filter(
                webdriver='PH',
                is_being_created=False,
                is_suspended_email=False
            )\
            .with_valid_proxy_for_registration()

    def with_valid_proxy_for_registration(self):
        return self.filter(
                proxy_for_usage__is_unavailable_for_registration=False,
                proxy_for_usage__is_unavailable_for_use=False,
                proxy_for_usage__is_phone_required=False,
            )\
            .exclude(proxy_for_registration__proxy='tor')\
            .exclude(proxy_for_usage__proxy='tor')

    def with_valid_proxy_for_usage(self):
        return self.filter(
                proxy_for_usage__is_unavailable_for_use=False,
            )\
            .exclude(proxy_for_registration__proxy='tor')\
            .exclude(proxy_for_usage__proxy='tor')

    def uncompleted(self):
        """Devuelve todos los robots pendientes de terminar registros, perfil, etc"""
        return self.registrable()\
            .filter(
                Q(twitter_registered_ok=False) |
                Q(twitter_confirmed_email_ok=False) |
                Q(twitter_avatar_completed=False) |
                Q(twitter_bio_completed=False) |
                Q(is_suspended=True)
            )

    def completed(self):
        """De los bots que toma devuelve sólo aquellos que estén completamente creados"""
        return self.usable()\
            .filter(
                twitter_registered_ok=True,
                twitter_confirmed_email_ok=True,
                twitter_avatar_completed=True,
                twitter_bio_completed=True,
                is_suspended=False,
            )

    def twitteable(self):
        """
        Entre los completamente creados coge los que no sean extractores, para evitar que twitter detecte
        actividad múltiple desde misma cuenta
        """
        return self.completed().filter(extractor=None)

    def _annotate_tweets_queued_to_send(self):
        return self.extra(
            select={
                'tweets_queued_to_send': """
                  select count(id) from project_tweet
                  WHERE project_tweet.bot_used_id = core_twitterbot.id
                  AND project_tweet.sending=FALSE AND project_tweet.sent_ok=FALSE
                """
            }
        )

    def without_tweet_to_send_queue_full(self):
        """Saca bots que no tengan llena su cola de tweets pendientes de enviar llena"""
        valid_pks = [
            bot.pk for bot in self.twitteable()._annotate_tweets_queued_to_send() if bot.tweets_queued_to_send < settings.MAX_QUEUED_TWEETS_TO_SEND_PER_BOT
        ]
        return self.filter(pk__in=valid_pks)

    def order_by__tweets_queued_to_send(self):
        pass

    def total_from_proxies_group(self, proxies_group):
        # puede ser que un mismo bot esté registrado y usando el mismo proxy, así que quitamos twitterbots duplicados
        return (self.using_proxies_group(proxies_group) | self.registered_by_proxies_group(proxies_group)).distinct()

    def registered_by_proxies_group(self, proxies_group):
        return self.filter(proxy_for_registration__proxies_group=proxies_group)

    def using_proxies_group(self, proxies_group):
        """Saca robots usándose en el grupo de proxies dado"""
        return self.filter(proxy_for_usage__proxies_group=proxies_group)

    def using_in_project(self, project):
        """Saca robots usándose en el proyecto dado"""
        return self.filter(proxy_for_usage__proxies_group__projects=project)

    def using_in_running_projects(self):
        """Saca bots usándose en proyectos que estén en ejecución"""
        return self.filter(proxy_for_usage__proxies_group__projects__is_running=True)


class ProxyQuerySet(QuerySet):
    def available_for_usage(self):
        """Devuelve proxies disponibles para iniciar sesión con bot y tuitear etc"""

        # base de proxies aptos usar robots ya registrados
        proxies_base = self.with_proxies_group_assigned().filter(
            is_in_proxies_txts=True,
            is_unavailable_for_use=False,
        )

        available_proxies_for_usage_ids = []

        # cogemos todos los proxies sin bots
        proxies_without_bots = proxies_base.filter(twitter_bots_registered=None, twitter_bots_using=None)
        available_proxies_for_usage_ids.extend([result['id'] for result in proxies_without_bots.values('id')])

        # de los proxies con bots, cogemos los que cumplan todas estas características:
        #   - que no tengan ningún robot muerto
        proxies_with_bots = proxies_base.filter(twitter_bots_registered__is_dead=False, twitter_bots_using__is_dead=False)
        #   - que tengan un número de bots para uso inferior al límite para el uso (usage)
        proxies_with_bots = proxies_with_bots\
            .annotate(num_bots=Count('twitter_bots_using'))\
            .filter(num_bots__lt=settings.MAX_TWT_BOTS_PER_PROXY_FOR_USAGE)
        available_proxies_for_usage_ids.extend([result['id'] for result in proxies_with_bots.values('id')])

        available_proxies_for_usage = self.filter(id__in=available_proxies_for_usage_ids)

        if not available_proxies_for_usage:
            raise NoMoreAvailableProxiesForUsage()

        return available_proxies_for_usage

    def available_for_registration(self):
        """
        Devuelve proxies disponibles para registrar un bot
        """

        # base de proxies aptos para el registro
        proxies_base = self.with_proxies_group_assigned().filter(
            is_in_proxies_txts=True,
            is_unavailable_for_registration=False,  # registro de email
            is_unavailable_for_use=False,
            is_phone_required=False,
        )

        available_proxies_for_reg_ids = []

        # cogemos todos los proxies sin bots
        proxies_without_bots = proxies_base.without_bots()
        available_proxies_for_reg_ids.extend([result['id'] for result in proxies_without_bots.values('id')])

        # de los proxies con bots cogemos los que cumplan todas estas características:
        #   - que no tengan ningún robot muerto
        #   - que tengan asignado una cantidad de bots inferior al límite para el registro
        #   - que el bot más recientemente creado sea igual o más antiguo que la fecha de ahora menos los días dados
        valid_proxies_with_bots = proxies_base.without_any_dead_bot()\
            .with_enough_space_for_registration()\
            .with_enough_time_ago_for_last_registration()
        available_proxies_for_reg_ids.extend([result['id'] for result in valid_proxies_with_bots.values('id')])

        available_proxies_for_reg = self.filter(id__in=available_proxies_for_reg_ids)

        if not available_proxies_for_reg:
            raise NoMoreAvailableProxiesForRegistration()

        return available_proxies_for_reg

    def with_bots_registered(self):
        return self.filter(twitter_bots_registered__isnull=False).distinct()

    def without_bots_registered(self):
        return self.filter(twitter_bots_registered__isnull=True).distinct()

    def with_bots_using(self):
        return self.filter(twitter_bots_using__isnull=False).distinct()

    def without_bots_using(self):
        return self.filter(twitter_bots_using__isnull=True).distinct()

    def with_bots(self):
        """Devuelve todos aquellos proxies que estén o hayan sido usados por al menos un robot"""
        return self.with_bots_registered() | self.with_bots_using()

    def without_bots(self):
        return self.without_bots_registered() & self.without_bots_using()

    def with_proxies_group_assigned(self):
        return self.filter(proxies_group__isnull=False)

    def without_proxies_group_assigned(self):
        return self.filter(proxies_group__isnull=True)

    def without_any_dead_bot(self):
        return self.filter(
            Q(twitter_bots_using__isnull=True) |
            Q(twitter_bots_using__is_dead=False)
        ).distinct()

    def with_at_least_one_dead_bot(self):
        return self.filter(
            Q(twitter_bots_using__is_dead=True)
        ).distinct()

    def _annotate__num_bots_registered(self):
        return self.annotate(num_bots_registered=Count('twitter_bots_registered'))

    def _annotate__latest_bot_registered_date(self):
        return self.annotate(latest_bot_registered_date=Max('twitter_bots_registered__date'))

    def with_enough_space_for_registration(self):
        """Saca los que tengan espacio para crear nuevos bots"""
        proxies_with_enought_space_pks = [
            proxy.pk
            for proxy in self._annotate__num_bots_registered().select_related('proxies_group')
            if proxy.num_bots_registered < proxy.proxies_group.max_tw_bots_per_proxy_for_registration
        ]
        return self.filter(pk__in=proxies_with_enought_space_pks)

    def with_enough_time_ago_for_last_registration(self):
        """Sacas los que el último registro se realizó hace el tiempo suficiente para crear nuevo bot"""
        proxies_with_enought_time_ago_pks = []
        for proxy in self._annotate__latest_bot_registered_date():
            if proxy.twitter_bots_registered.exists():
                latest_bot_is_old_enough = is_lte_than_days_ago(
                    proxy.latest_bot_registered_date,
                    proxy.proxies_group.min_days_between_registrations_per_proxy
                )
                if latest_bot_is_old_enough:
                    proxies_with_enought_time_ago_pks.append(proxy.pk)
            else:
                # si el proxy no tiene bots, obviamente es válido
                proxies_with_enought_time_ago_pks.append(proxy.pk)

        return self.filter(pk__in=proxies_with_enought_time_ago_pks)

    def using_in_running_projects(self):
        """Saca proxies usándose en proyectos que estén en ejecución"""
        return self.filter(proxies_group__projects__is_running=True)