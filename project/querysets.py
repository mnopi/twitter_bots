# -*- coding: utf-8 -*-
from array import array
from itertools import chain
from django.db import connection

from django.db.models import Count, Q
from django.db.models.query import QuerySet
from twitter_bots import settings


class ExtractorQuerySet(QuerySet):
    def available(self, mode):
        from project.models import Extractor

        available_extractors_ids = [
            extractor.pk for extractor in self.filter(mode=mode) if extractor.is_available()
        ]
        available_extractors = Extractor.objects.filter(id__in=available_extractors_ids)

        # if not available_extractors:
        # last_used_extractor = self.latest('last_request_date')
        #     settings.LOGGER.warning('No available %s extractors at this moment. Last used was %s at %s' %
        #                             (self.display_extractor_mode(mode), last_used_extractor.twitter_bot.username,
        #                              last_used_extractor.last_request_date))
        return available_extractors


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


class TargetUserQuerySet(QuerySet):
    def available_to_extract(self):
        return self.filter(is_active=True, projects__is_running=True).exclude(next_cursor=None)


class TweetQuerySet(QuerySet):
    def sent_ok(self):
        return self.filter(sent_ok=True)

    def queued_to_send(self):
        return self.filter(sending=False, sent_ok=False)


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

    def get_chained_distinct(self, *pks):
        return self.filter(pk__in=list(set(chain(*pks))))

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
            Q(hashtags__projects=project)
        )

    def target_users_for_project(self, project):
        return self.filter(target_users__projects=project)

    def mentioned(self):
        return self.filter(mentions__isnull=False).distinct()

    def unmentioned(self):
        return self.filter(mentions__isnull=True).distinct()

    def mentioned_on_project(self, project):
        """Saca usuarios que hayan sido mencionados para el proyecto dado"""
        return self.filter(mentions__project=project).distinct()

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


