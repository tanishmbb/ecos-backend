# config/__init__.py  (or project/__init__.py — the package that contains settings.py)
# import pymysql
# pymysql.install_as_MySQLdb()
from .celery import app as celery_app

__all__ = ("celery_app",)
