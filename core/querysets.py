# -*- coding: utf-8 -*-
from django.db.models import Q, Count, Max
from django.db.models.query import QuerySet
from project.querysets import MyQuerySet
from scrapper.utils import is_lte_than_days_ago
from twitter_bots import settings


class TwitterBotQuerySet(QuerySet):
    def without_any_account_registered(self):
        return self.filter(email_registered_ok=False, twitter_registered_ok=False)

    def usable(self):
        return self.filter(
                is_being_created=False,
                is_dead=False
            ).\
            with_valid_proxy_for_usage()

    def registrable(self):
        """
            Saca robots que puedan continuar el registro.
            No vamos a continuar con aquellos que estén registrados en twitter pero no tengan correo
        """
        return self.filter(
            is_being_created=False,
            is_dead=False,
            is_suspended_email=False
        )\
        .exclude(Q(email_registered_ok=False) & Q(twitter_registered_ok=True))\
        .with_valid_proxy_for_registration()

    def with_valid_proxy_for_registration(self):
        qs = self.filter(
                proxy_for_usage__is_unavailable_for_registration=False,
                proxy_for_usage__is_unavailable_for_use=False,
            )\
            .exclude(proxy_for_registration__proxy='tor')\
            .exclude(proxy_for_usage__proxy='tor')

        if not settings.REUSE_PROXIES_REQUIRING_PHONE_VERIFICATION:
            qs = qs.filter(proxy_for_usage__is_phone_required=False)

        return qs

    def with_valid_proxy_for_usage(self):
        return self.filter(
                proxy_for_usage__is_unavailable_for_use=False,
            )\
            .exclude(proxy_for_registration__proxy='tor')\
            .exclude(proxy_for_usage__proxy='tor')

    def uncompleted(self):
        """Devuelve todos los robots pendientes de terminar registros, perfil, etc"""
        uncompleted = self.registrable()\
            .filter(
                Q(twitter_registered_ok=False) |
                Q(twitter_confirmed_email_ok=False) |
                Q(twitter_avatar_completed=False) |
                Q(twitter_bio_completed=False) |
                Q(is_suspended=True)
            )\
            .filter_suspended_bots()

        if settings.PRIORIZE_RUNNING_PROJECTS_FOR_BOT_CREATION:
            uncompleted = uncompleted.order_by__priorizing_running_projects()

        return uncompleted.distinct()

    def on_running_projects(self):
        return self.filter(proxy_for_usage__proxies_group__projects__is_running=True)

    def order_by__priorizing_running_projects(self):
        return self.order_by('-proxy_for_usage__proxies_group__projects__is_running')

    def completed(self):
        """De los bots que toma devuelve sólo aquellos que estén completamente creados"""
        return self.usable()\
            .filter(
                twitter_registered_ok=True,
                twitter_confirmed_email_ok=True,
                twitter_avatar_completed=True,
                twitter_bio_completed=True,
                is_suspended=False,
            ).distinct()

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
        raise NotImplementedError

    def total_from_proxies_group(self, proxies_group):
        # puede ser que un mismo bot esté registrado y usando el mismo proxy, así que quitamos twitterbots duplicados
        return (self.using_proxies_group(proxies_group) | self.registered_by_proxies_group(proxies_group)).distinct()

    def registered_by_proxies_group(self, proxies_group):
        return self.filter(twitter_registered_ok=False, proxy_for_registration__proxies_group=proxies_group)

    def using_proxies_group(self, proxies_group):
        """Saca robots usándose en el grupo de proxies dado"""
        return self.filter(proxy_for_usage__proxies_group=proxies_group)

    def using_in_project(self, project):
        """Saca robots usándose en el proyecto dado"""
        return self.filter(proxy_for_usage__proxies_group__projects=project)

    def using_in_running_projects(self):
        """Saca bots usándose en proyectos que estén en ejecución"""
        return self.filter(proxy_for_usage__proxies_group__projects__is_running=True)

    def pendant_to_finish_creation(self):
        """Saca los bots pendientes de completar y que sean de grupos que tengan activado el crear bots"""
        return self.uncompleted().filter(proxy_for_usage__proxies_group__is_bot_creation_enabled=True)

    q__without_any_suspended_bot = ~(
        Q(is_suspended=True) |
        Q(num_suspensions_lifted__gt=0)
    )

    def filter_suspended_bots(self):
        return self.filter(
            (
                Q(proxy_for_usage__proxies_group__reuse_proxies_with_suspended_bots=False) &
                self.q__without_any_suspended_bot
            ) |
            (
                Q(proxy_for_usage__proxies_group__reuse_proxies_with_suspended_bots=True)
            )
        )\
        .distinct()


class ProxyQuerySet(MyQuerySet):
    q__without_any_suspended_bot = ~(
        Q(twitter_bots_using__is_suspended=True) |
        Q(twitter_bots_using__num_suspensions_lifted__gt=0)
    )

    def available_for_usage(self):
        """Devuelve proxies disponibles para iniciar sesión con bot y tuitear etc"""

        # base de proxies aptos usar robots ya registrados
        proxies_base = self\
            .with_proxies_group_assigned()\
            .with_proxies_group_enabling_bot_usage()\
            .filter(
                is_in_proxies_txts=True,
                is_unavailable_for_use=False,
            )
        if not settings.REUSE_PROXIES_REQUIRING_PHONE_VERIFICATION:
            proxies_base = proxies_base.filter(is_phone_required=False)

        available_proxies_for_usage_ids = []

        # cogemos todos los proxies sin bots
        proxies_without_bots = proxies_base.filter(twitter_bots_registered=None, twitter_bots_using=None)
        available_proxies_for_usage_ids.extend([result['id'] for result in proxies_without_bots.values('id')])

        # de los proxies con bots, cogemos los que cumplan todas estas características:
        #   - que no tengan ningún robot muerto
        #   - que tengan un número de bots para uso inferior al límite marcado por su grupo
        proxies_with_bots = proxies_base\
            .with_enough_space_for_usage()
        available_proxies_for_usage_ids.extend([result['id'] for result in proxies_with_bots.values('id')])

        return self.filter(id__in=available_proxies_for_usage_ids)

    def unavailable_for_usage(self):
        return self.subtract(self.available_for_usage())

    def available_for_registration(self):
        """
        Devuelve proxies disponibles para crear un bot
        """

        # base de proxies aptos para el registro. Quitamos los que tengan bots suspendidos o muertos.
        # Primero colocamos el filtro de la subnet /24 por si se cambiaron los proxies recientemente
        proxies_base = self\
            .with_enough_time_ago_for_last_registration_under_subnets_24()\
            .filter(
                is_in_proxies_txts=True,
                is_unavailable_for_registration=False,  # registro de email
                is_unavailable_for_use=False,
            )\
            .with_proxies_group_assigned()\
            .with_proxies_group_enabling_bot_creation()

        if not settings.REUSE_PROXIES_REQUIRING_PHONE_VERIFICATION:
            proxies_base = proxies_base.filter(is_phone_required=False)

        available_proxies_for_reg_ids = []

        # cogemos todos los proxies sin bots
        proxies_without_bots = proxies_base.without_bots()
        available_proxies_for_reg_ids.extend([result['id'] for result in proxies_without_bots.values('id')])

        # de los proxies con bots cogemos los que cumplan todas estas características:
        #   - que no tengan ningún robot muerto
        #   - que tengan asignado una cantidad de bots inferior al límite para el registro
        #   - que el bot más recientemente creado bajo su subnet /24 sea igual o más antiguo que la fecha de ahora menos los días dados
        proxies_with_bots = proxies_base\
            .filter_suspended_bots()\
            .with_enough_space_for_registration()\
            .with_enough_time_ago_for_last_registration()
        available_proxies_for_reg_ids.extend([result['id'] for result in proxies_with_bots.values('id')])

        return self.filter(id__in=available_proxies_for_reg_ids)

    def unavailable_for_registration(self):
        return self.subtract(self.available_for_registration())

    def with_some_registered_bot(self):
        return self.filter(twitter_bots_registered__isnull=False).distinct()

    def without_any_bot_registered(self):
        return self.filter(twitter_bots_registered__isnull=True).distinct()

    def with_some_bot_using(self):
        return self.filter(twitter_bots_using__isnull=False).distinct()

    def without_bots_using(self):
        return self.filter(twitter_bots_using__isnull=True).distinct()

    def with_bots(self):
        """Devuelve todos aquellos proxies que estén o hayan sido usados por al menos un robot"""
        return self.with_some_registered_bot() | self.with_some_bot_using()

    def without_bots(self):
        return self.without_any_bot_registered() & self.without_bots_using()

    def with_proxies_group_assigned(self):
        return self.filter(proxies_group__isnull=False)

    def with_proxies_group_enabling_bot_creation(self):
        return self.filter(proxies_group__is_bot_creation_enabled=True)

    def with_proxies_group_enabling_bot_usage(self):
        return self.filter(proxies_group__is_bot_usage_enabled=True)

    def without_proxies_group_assigned(self):
        return self.filter(proxies_group__isnull=True)

    def without_any_suspended_bot(self):
        return self.filter(self.q__without_any_suspended_bot).distinct()

    def without_any_dead_bot(self):
        return self.filter(
            Q(twitter_bots_using__isnull=True) |
            Q(twitter_bots_using__is_dead=False)
        ).distinct()

    def filter_suspended_bots(self):
        return self.filter(
            (
                Q(proxies_group__reuse_proxies_with_suspended_bots=False) &
                self.q__without_any_suspended_bot
            ) |
            (
                Q(proxies_group__reuse_proxies_with_suspended_bots=True)
            )
        )\
        .distinct()

    def with_some_dead_bot(self):
        return self.filter(twitter_bots_using__is_dead=True).distinct()

    def _annotate__num_bots_registered(self):
        return self.annotate(num_bots_registered=Count('twitter_bots_registered'))

    def _annotate__num_bots_using(self):
        return self.annotate(num_bots_using=Count('twitter_bots_using'))

    def _annotate__latest_bot_registered_date(self):
        return self.annotate(latest_bot_registered_date=Max('twitter_bots_registered__date'))

    def with_enough_space_for_registration(self):
        """Saca los que tengan espacio para crear nuevos bots"""
        proxies_with_enought_space_pks = []
        for proxy in self.select_related('proxies_group', 'twitter_bots_registered'):
            if proxy.twitter_bots_registered.count() < proxy.proxies_group.max_tw_bots_per_proxy_for_registration:
                proxies_with_enought_space_pks.append(proxy.pk)

        return self.filter(pk__in=proxies_with_enought_space_pks)

    def with_enough_space_for_usage(self):
        """Saca los que tengan espacio para crear nuevos bots"""
        proxies_with_enought_space_pks = [
            proxy.pk
            for proxy in self._annotate__num_bots_using().select_related('proxies_group')
            if proxy.num_bots_using < proxy.proxies_group.max_tw_bots_per_proxy_for_usage
        ]
        return self.filter(pk__in=proxies_with_enought_space_pks)

    def with_enough_time_ago_for_last_registration(self):
        """Sacas los proxies donde el último registro se realizó hace el tiempo suficiente para crear nuevo bot"""
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

    def with_subnet_24(self, subnet_24):
        return self.filter(proxy__startswith=subnet_24)

    def with_enough_time_ago_for_last_registration_under_subnets_24(self):
        """Saca los proxies de cada subnet /24 donde el último registro se realizó hace el tiempo
        suficiente para registrar bots en nuevos proxies bajo esa misma subnet.

        Por ejemplo, si tenemos 40 proxies bajo la subnet s1 y el último bot de ahí
        se registró hace 5 minutos, entonces no escogeremos ningún proxy de esa subnet
        """
        from core.models import Proxy, TwitterBot

        proxies_with_enought_time_ago_pks = []

        subnets = Proxy.objects.get_subnets_24(self)
        for subnet in subnets:
            proxies_in_subnet = self.with_subnet_24(subnet)
            bots_registered_in_subnet = TwitterBot.objects.filter(proxy_for_registration__in=proxies_in_subnet)
            if bots_registered_in_subnet:
                # si la subnet tiene algún proxy con bot registrado, comprobamos que la última
                # fecha de registro tenga la antiguedad mínima necesaria
                last_bot_registered = bots_registered_in_subnet.latest('date')
                last_bot_is_old_enough = is_lte_than_days_ago(
                    last_bot_registered.date,
                    last_bot_registered.get_group().min_days_between_registrations_per_proxy_under_same_subnet
                )
                if last_bot_is_old_enough:
                    proxies_with_enought_time_ago_pks.extend(proxies_in_subnet.values_list('pk', flat=True))
            else:
                # si la subnet no tiene ningún proxy que tenga un bot registrado, entonces agregamos todos sus proxies
                proxies_with_enought_time_ago_pks.extend(proxies_in_subnet.values_list('pk', flat=True))

        return self.filter(pk__in=proxies_with_enought_time_ago_pks)

    def using_in_running_projects(self):
        """Saca proxies usándose en proyectos que estén en ejecución"""
        return self.filter(proxies_group__projects__is_running=True)

    def for_group(self, group):
        return self.filter(proxies_group=group)

    def with_some_suspended_bot(self):
        return self.filter(
            Q(twitter_bots_using__is_suspended=True) |
            Q(twitter_bots_using__num_suspensions_lifted__gt=0)
        ).distinct()

    def valid_for_assign_proxies_group(self):
        """Saca proxies válidos para asignarles un grupo"""
        return self.without_bots().filter(is_in_proxies_txts=True)

    def with_completed_bots(self):
        """Saca proxies que tengan al menos un bot completamente creado"""
        return self.filter(
            twitter_bots_using__is_being_created=False,
            twitter_bots_using__is_dead=False,
            twitter_bots_using__is_suspended=False,
            twitter_bots_using__twitter_registered_ok=True,
            twitter_bots_using__twitter_confirmed_email_ok=True,
            twitter_bots_using__twitter_avatar_completed=True,
            twitter_bots_using__twitter_bio_completed=True,
        )

    def without_completed_bots(self):
        """Saca proxies que no tengan ningún bot completamente creado"""
        return self.filter(
            Q(twitter_bots_using__is_dead=True) |
            Q(twitter_bots_using__is_suspended=True) |
            Q(twitter_bots_using__twitter_registered_ok=False) |
            Q(twitter_bots_using__twitter_confirmed_email_ok=False) |
            Q(twitter_bots_using__twitter_avatar_completed=False) |
            Q(twitter_bots_using__twitter_bio_completed=False)
        )

    def invalid_for_assign_proxies_group(self):
        return self.subtract(self.valid_for_assign_proxies_group())