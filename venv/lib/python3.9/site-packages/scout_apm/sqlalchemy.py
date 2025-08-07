# coding=utf-8

from sqlalchemy import event

from scout_apm.core.tracked_request import TrackedRequest


def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if executemany:
        operation = "SQL/Many"
    else:
        operation = "SQL/Query"
    tracked_request = TrackedRequest.instance()
    span = tracked_request.start_span(operation=operation)
    span.tag("db.statement", statement)


def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    tracked_request = TrackedRequest.instance()
    span = tracked_request.current_span()
    if span is not None:
        if tracked_request.n_plus_one_tracker.should_capture_backtrace(
            sql=statement,
            duration=span.duration(),
            count=(1 if not executemany else len(parameters)),
        ):
            span.capture_backtrace()
        tracked_request.stop_span()


def instrument_sqlalchemy(engine):
    # We can get in the situation where we double-instrument the cursor. Avoid
    # it by setting a flag and checking it before adding these listeners
    if getattr(engine, "_scout_instrumented", False):
        return
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    engine._scout_instrumented = True
