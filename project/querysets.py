# -*- coding: utf-8 -*-

from core.scrapper.utils import utc_now
from itertools import chain
import datetime
from django.db import connection
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from twitter_bots import settings


class MyQuerySet(QuerySet):
    def union(self, qs, limit=None, order_by=None):
        """Retorna la union entre qs self y la qs dada"""
        c = connection.cursor()
        try:
            c.execute('Select cal.id from (%(q1)s union %(q2)s) cal %(order_by) %(limit)' %
                      {
                          'q1': self.query,
                          'q2': qs.query,
                          'order_by': 'ORDER BY %s %s' % (order_by, 'DESC' if order_by[0] == '-' else 'ASC') if order_by else '',
                          'limit': 'LIMIT %d' % limit if limit else ''
                      }
            )
            # return self.filter(pk__in=zip(*c.fetchall())[0])
            return self.filter(pk__in=[r[0] for r in c])
        finally:
            c.close()

    def get_pks_from_raw_query(self, raw_query):
        c = connection.cursor()
        try:
            c.execute(raw_query)
            return self.filter(pk__in=zip(*c.fetchall())[0])
        finally:
            c.close()

    def get_pks_distinct(self):
        return self.values_list('pk', flat=True).distinct()

    def get_chained_distinct(self, *pks):
        return self.filter(pk__in=list(set(chain(*pks))))

    def subtract(self, qs_to_subtract):
        pks_to_subtract = qs_to_subtract.values_list('pk', flat=True)
        return self.exclude(pk__in=pks_to_subtract)


class ExtractorQuerySet(QuerySet):
    def available(self, mode):
        """Devuelve los extractores que se pueden usar en el momento de ejecutar esto"""

        from project.models import Extractor

        available_extractors_ids = []
        for extractor in self.filter(Q(mode=mode) | Q(mode=Extractor.BOTH)):
            if extractor.is_available():
                available_extractors_ids.append(extractor.pk)

        return self.filter(id__in=available_extractors_ids)


class ProjectQuerySet(QuerySet):
    def running(self):
        "Filtra por proyectos que estén en marcha"
        return self.filter(is_running=True)

    def with_bot(self, bot):
        "Filtra por proyectos que correspondan al bot dado"
        return self.filter(proxies_groups__proxies__twitter_bots_using=bot)

    def with_unmentioned_users(self):
        "Filtra por proyectos que tengan usuarios todavía sin mencionar"
        return self.annotate(unmentioned_users_count=Count('target_users__twitter_users__mentions')) \
            .filter(unmentioned_users_count__gt=0)

    def order_by__queued_tweets(self, direction=''):
        """
        Ordena proyectos de menor a mayor por número de tweets pendientes de enviar

        :param direction -  símbolo de ordenación en queryset (direction='-' descendente, por defecto ascendente)
        """
        return self.extra(
            select={
                'queued_tweets_count': """  SELECT count(*) FROM project_tweet
                                            WHERE project_tweet.project_id = project_project.id
                                            AND project_tweet.sending=FALSE AND project_tweet.sent_ok=FALSE"""
            }
        ).order_by('%squeued_tweets_count' % direction)


class TargetUserQuerySet(MyQuerySet):
    def available_to_extract(self):
        return self.filter(is_active=True, is_suspended=False).exclude(next_cursor=None)

    def for_project(self, project):
        return self.filter(
            Q(tu_groups__projects=project) |
            Q(projects=project)
        )


class HashtagQuerySet(MyQuerySet):
    q__has_to_wait_for_next_round = (
        Q(last_round_end_date__isnull=False) &
        Q(last_round_end_date__lte=utc_now() - datetime.timedelta(seconds=settings.NEW_ROUND_TIMEWINDOW))
    )

    q__has_to_wait_timewindow_because_of_not_enough_new_twitterusers = (
        Q(has_to_wait_timewindow_because_of_not_enough_new_twitterusers=True) &
        Q(date_last_extraction__lte=utc_now() -
                                    datetime.timedelta(seconds=settings.HASHTAG_TIMEWINDOW_TO_WAIT_WHEN_NOT_ENOUGH_TWITTERUSERS))
    )

    def has_to_wait_for_next_round(self):
        return self.filter(self.q__has_to_wait_for_next_round)

    def has_to_wait_timewindow_because_of_not_enough_new_twitterusers(self):
        return self.filter(self.q__has_to_wait_timewindow_because_of_not_enough_new_twitterusers)

    def available_to_extract(self):
        """Los hashtags disponibles serán los que estén marcados como activos por el admin y los que, en caso de
        tener que esperar periodo ventana para comprobar si recoge suficiente número de twitterusers, hayan pasado
        dicho periodo ya"""
        return self.filter(
            Q(is_active=True) &

            (
                Q(has_to_wait_timewindow_because_of_not_enough_new_twitterusers=False) |
                self.q__has_to_wait_timewindow_because_of_not_enough_new_twitterusers
            ) &
            (
                Q(last_round_end_date__isnull=True) |
                self.q__has_to_wait_for_next_round
            )
        )

    def for_project(self, project):
        return self.filter(
            Q(hashtag_groups__projects=project) |
            Q(projects=project)
        )


class TweetQuerySet(QuerySet):
    def sent_ok(self):
        return self.filter(sent_ok=True)

    def by_bot(self, bot):
        return self.filter(bot_used=bot)

    def mentioning_bots(self):
        return self.filter(mentioned_bots__isnull=False)

    def not_checked_if_mention_arrives_ok(self):
        """Devuelve aquellos tweets de verificación que no tengan registro de verificación o bien el bot
        destino aún no comprobó si le llegó dicho tweet"""
        return self.filter(
            Q(tweet_checking_mention=None) |
            Q(tweet_checking_mention__destination_bot_checked_mention=False)
        )

    def pending_to_send(self):
        return self.filter(sent_ok=False)

    def with_not_ok_bots(self):
        """Saca los tweets donde su bot tenga un proxy que no conecte o bien esté suspendido/muerto"""
        with_not_connectable_proxy = (Q(bot_used__proxy_for_usage__is_in_proxies_txts=False) |
                                     Q(bot_used__proxy_for_usage__is_unavailable_for_use=True))
        with_not_ok_bot = (Q(bot_used__is_dead=True) |
                           Q(bot_used__is_suspended=True) |
                           Q(bot_used__twitter_confirmed_email_ok=False))
        return self.filter(
            with_not_connectable_proxy | with_not_ok_bot
        )

    def mctweets(self):
        """Filtra por los que son mctweets"""
        return self.filter(project__isnull=True, mentioned_bots__isnull=False)

    def mctweets_not_verified(self):
        """Filtra por los mctweets que aún no fueron verificados por bot destino"""
        return self.mctweets().filter(
            Q(tweet_checking_mention__isnull=True) |
            Q(tweet_checking_mention__destination_bot_checked_mention=False)
        )


class TwitterUserQuerySet(MyQuerySet):
    def for_project(self, project, order_by=None, limit=None):
        """Saca usuarios para un proyecto dado"""
        # q1 = self.filter(target_users__projects=project).values_list('pk', flat=True)
        # q2 = self.filter(hashtags__projects=project).values_list('pk', flat=True)
        #
        # # http://stackoverflow.com/questions/431628/how-to-combine-2-or-more-querysets-in-a-django-view
        # return self.filter(pk__in=chain(q1, q2))

        return self.filter(
            Q(target_users__projects=project) |
            Q(target_users__tu_groups__projects=project) |
            Q(hashtags__projects=project)
        ).distinct()

    def target_users_for_project(self, project):
        return self.filter(target_users__projects=project)

    def mentioned(self):
        return self.filter(mentions__isnull=False).distinct()

    def unmentioned(self):
        return self.filter(mentions__isnull=True).distinct()

    def mentioned_on_project(self, project):
        """Saca usuarios que hayan sido mencionados para el proyecto dado"""
        return self.filter(mentions__project=project).distinct()

    def unmentioned_on_project(self, project):
        """Saca usuarios que hayan sido mencionados para el proyecto dado"""
        return self.for_project(project).unmentioned().distinct()

    def mentioned_by_bot(self, bot):
        return self.mentioned().filter(mentions__bot_used=self).distinct()

    def unmentioned_by_bot(self, bot):
        """Saca usuarios que no hayan sido mencionados por el bot dado, es decir,
        de los mencionados, los que no hayan sido por el bot y todos los no mencionados """
        mentioned_not_from_bot_pks = self.filter(mentions__isnull=False).exclude(mentions__bot_used=bot).values_list('pk', flat=True)
        unmentioned = self.filter(mentions__isnull=True).values_list('pk', flat=True)
        return self.filter(pk__in=chain(mentioned_not_from_bot_pks, unmentioned))
        # return (
        #     self.filter(mentions__isnull=False).exclude(mentions__bot_used=bot).union_all(self.filter(mentions__isnull=True))
        # )

    def mentioned_by_bot_on_project(self, bot, project):
        return self.mentioned_by_bot(bot).mentioned_on_project(project).distinct()

    def saved_lte_days(self, days):
        """Saca los usuarios que fueron guardados hace :days o más días"""
        return self.filter(date_saved__lte=utc_now() - datetime.timedelta(days=days))

    def not_followed(self):
        """Saca los que nunca fueron seguidos por ningún bot"""
        return self.filter(tb_followings__isnull=True)


class FeedItemQuerySet(MyQuerySet):
    def not_sent_by_bot(self, bot):
        """Mira en los feeds asignados al grupo de proxies para el bot y saca los que este grupo
        todavía no haya enviado."""

        return self\
            .for_bot(bot)\
            .exclude(Q(tweets__bot_used=bot) & Q(tweets__sent_ok=True))

    def sent_by_bot(self, bot):
        return self\
            .for_bot(bot)\
            .filter(Q(tweets__bot_used=bot) & Q(tweets__sent_ok=True))

    def for_bot(self, bot):
        bot_group = bot.get_group()
        return self.filter(feed__feeds_groups__proxies_groups=bot_group)
