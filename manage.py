#!/usr/bin/env python
import os
import sys
from core.scrapper.utils import create_gitignored_folders

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twitter_bots.settings")

    from django.core.management import execute_from_command_line

    try:
        execute_from_command_line(sys.argv)
    except ValueError, e:
        create_gitignored_folders()
        execute_from_command_line(sys.argv)
