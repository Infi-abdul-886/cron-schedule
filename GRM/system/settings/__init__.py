import pymysql
pymysql.install_as_MySQLdb()
# GRM/system/__init__.py
# The rest of your __init__.py file (like the celery import) comes after
from ..celery import app as celery_app

__all__ = ('celery_app',)