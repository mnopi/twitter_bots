# CELERY_ROUTES = {
#     'celery_tasks.add': 'mentions_processor',
# }

# CELERY_RESULT_SERIALIZER = 'json'
# CELERY_ACCEPT_CONTENT = ['application/json', 'json']
CELERY_ACCEPT_CONTENT = ['pickle', 'json', 'msgpack', 'yaml']
