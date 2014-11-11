# -*- coding: utf-8 -*-


def create_gitignored_folders():
    # creamos estas carpetas si no existen, ya que las hemos añadido al gitignore
    import scrapper.utils as utils
    import settings

    utils.mkdir_if_not_exists(settings.SCREENSHOTS_DIR)
    utils.mkdir_if_not_exists(settings.AVATARS_DIR)
    utils.mkdir_if_not_exists(settings.PHANTOMJS_COOKIES_DIR)
    utils.mkdir_if_not_exists(settings.LOGS_DIR)
    utils.mkdir_if_not_exists(settings.SUPERVISOR_LOGS_DIR)


create_gitignored_folders()