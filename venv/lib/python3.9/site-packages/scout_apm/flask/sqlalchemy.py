# coding=utf-8

import wrapt
from flask_sqlalchemy import SQLAlchemy

import scout_apm.sqlalchemy


def instrument_sqlalchemy(db):
    # Version 3 of flask_sqlalchemy changed how engines are created
    if hasattr(db, "_make_engine"):
        db._make_engine = wrapped_make_engine(db._make_engine)
    else:
        SQLAlchemy.get_engine = wrapped_get_engine(SQLAlchemy.get_engine)


@wrapt.decorator
def wrapped_get_engine(wrapped, instance, args, kwargs):
    engine = wrapped(*args, **kwargs)
    scout_apm.sqlalchemy.instrument_sqlalchemy(engine)
    return engine


@wrapt.decorator
def wrapped_make_engine(wrapped, instance, args, kwargs):
    engine = wrapped(*args, **kwargs)
    scout_apm.sqlalchemy.instrument_sqlalchemy(engine)
    return engine
