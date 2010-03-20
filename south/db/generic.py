
import datetime
import string
import random
import re
import sys

from django.core.management.color import no_style
from django.db import connection, transaction, models
from django.db.backends.util import truncate_name
from django.db.models.fields import NOT_PROVIDED
from django.dispatch import dispatcher
from django.conf import settings
from django.utils.datastructures import SortedDict

from south.logger import get_logger

def alias(attrname):
    """
    Returns a function which calls 'attrname' - for function aliasing.
    We can't just use foo = bar, as this breaks subclassing.
    """
    def func(self, *args, **kwds):
        return getattr(self, attrname)(*args, **kwds)
    return func


class DatabaseOperations(object):

    """
    Generic SQL implementation of the DatabaseOperations.
    Some of this code comes from Django Evolution.
    """

    # We assume the generic DB can handle DDL transactions. MySQL wil change this.
    has_ddl_transactions = True

    alter_string_set_type = 'ALTER COLUMN %(column)s TYPE %(type)s'
    alter_string_set_null = 'ALTER COLUMN %(column)s DROP NOT NULL'
    alter_string_drop_null = 'ALTER COLUMN %(column)s SET NOT NULL'
    has_check_constraints = True
    delete_check_sql = 'ALTER TABLE %(table)s DROP CONSTRAINT %(constraint)s'
    allows_combined_alters = True
    add_column_string = 'ALTER TABLE %s ADD COLUMN %s;'
    delete_unique_sql = "ALTER TABLE %s DROP CONSTRAINT %s"
    delete_foreign_key_sql = 'ALTER TABLE %s DROP CONSTRAINT %s'
    supports_foreign_keys = True
    max_index_name_length = 63
    drop_index_string = 'DROP INDEX %(index_name)s'
    delete_column_string = 'ALTER TABLE %s DROP COLUMN %s CASCADE;'
    create_primary_key_string = "ALTER TABLE %(table)s ADD CONSTRAINT %(constraint)s PRIMARY KEY (%(columns)s)"
    drop_primary_key_string = "ALTER TABLE %(table)s DROP CONSTRAINT %(constraint)s"
    backend_name = None

    def __init__(self):
        self.debug = False
        self.deferred_sql = []
        self.dry_run = False
        self.pending_transactions = 0
        self.pending_create_signals = []
    

    def connection_init(self):
        """
        Run before any SQL to let database-specific config be sent as a command,
        e.g. which storage engine (MySQL) or transaction serialisability level.
        """
        pass
    

    def execute(self, sql, params=[]):
        """
        Executes the given SQL statement, with optional parameters.
        If the instance's debug attribute is True, prints out what it executes.
        """
        self.connection_init()
        cursor = connection.cursor()
        if self.debug:
            print "   = %s" % sql, params

        get_logger().debug('south execute "%s" with params "%s"' % (sql, params))
        
        if self.dry_run:
            return []

        cursor.execute(sql, params)
        try:
            return cursor.fetchall()
        except:
            return []
    
    
    def execute_many(self, sql, regex=r"(?mx) ([^';]* (?:'[^']*'[^';]*)*)", comment_regex=r"(?mx) (?:^\s*$)|(?:--.*$)"):
        """
        Takes a SQL file and executes it as many separate statements.
        (Some backends, such as Postgres, don't work otherwise.)
        """
        # Be warned: This function is full of dark magic. Make sure you really
        # know regexes before trying to edit it.
        # First, strip comments
        sql = "\n".join([x.strip().replace("%", "%%") for x in re.split(comment_regex, sql) if x.strip()])
        # Now execute each statement
        for st in re.split(regex, sql)[1:][::2]:
            self.execute(st)

    
    def add_deferred_sql(self, sql):
        """
        Add a SQL statement to the deferred list, that won't be executed until
        this instance's execute_deferred_sql method is run.
        """
        self.deferred_sql.append(sql)


    def execute_deferred_sql(self):
        """
        Executes all deferred SQL, resetting the deferred_sql list
        """
        for sql in self.deferred_sql:
            self.execute(sql)

        self.deferred_sql = []


    def clear_deferred_sql(self):
        """
        Resets the deferred_sql list to empty.
        """
        self.deferred_sql = []
    
    
    def clear_run_data(self, pending_creates = None):
        """
        Resets variables to how they should be before a run. Used for dry runs.
        If you want, pass in an old panding_creates to reset to.
        """
        self.clear_deferred_sql()
        self.pending_create_signals = pending_creates or []
    
    
    def get_pending_creates(self):
        return self.pending_create_signals


    def create_table(self, table_name, fields):
        """
        Creates the table 'table_name'. 'fields' is a tuple of fields,
        each repsented by a 2-part tuple of field name and a
        django.db.models.fields.Field object
        """
        qn = connection.ops.quote_name

        # allow fields to be a dictionary
        # removed for now - philosophical reasons (this is almost certainly not what you want)
        #try:
        #    fields = fields.items()
        #except AttributeError:
        #    pass
        
        if len(table_name) > 63:
            print "   ! WARNING: You have a table name longer than 63 characters; this will not fully work on PostgreSQL or MySQL."

        columns = [
            self.column_sql(table_name, field_name, field)
            for field_name, field in fields
        ]

        self.execute('CREATE TABLE %s (%s);' % (qn(table_name), ', '.join([col for col in columns if col])))

    add_table = alias('create_table') # Alias for consistency's sake


    def rename_table(self, old_table_name, table_name):
        """
        Renames the table 'old_table_name' to 'table_name'.
        """
        if old_table_name == table_name:
            # No Operation
            return
        qn = connection.ops.quote_name
        params = (qn(old_table_name), qn(table_name))
        self.execute('ALTER TABLE %s RENAME TO %s;' % params)


    def delete_table(self, table_name, cascade=True):
        """
        Deletes the table 'table_name'.
        """
        qn = connection.ops.quote_name
        params = (qn(table_name), )
        if cascade:
            self.execute('DROP TABLE %s CASCADE;' % params)
        else:
            self.execute('DROP TABLE %s;' % params)

    drop_table = alias('delete_table')


    def clear_table(self, table_name):
        """
        Deletes all rows from 'table_name'.
        """
        qn = connection.ops.quote_name
        params = (qn(table_name), )
        self.execute('DELETE FROM %s;' % params)

    

    def add_column(self, table_name, name, field, keep_default=True):
        """
        Adds the column 'name' to the table 'table_name'.
        Uses the 'field' paramater, a django.db.models.fields.Field instance,
        to generate the necessary sql

        @param table_name: The name of the table to add the column to
        @param name: The name of the column to add
        @param field: The field to use
        """
        qn = connection.ops.quote_name
        sql = self.column_sql(table_name, name, field)
        if sql:
            params = (
                qn(table_name),
                sql,
            )
            sql = self.add_column_string % params
            self.execute(sql)

            # Now, drop the default if we need to
            if not keep_default and field.default is not None:
                field.default = NOT_PROVIDED
                self.alter_column(table_name, name, field, explicit_name=False)
    

    def _db_type_for_alter_column(self, field):
        """
        Returns a field's type suitable for ALTER COLUMN.
        By default it just returns field.db_type().
        To be overriden by backend specific subclasses
        @param field: The field to generate type for
        """
        return field.db_type()
    
    def alter_column(self, table_name, name, field, explicit_name=True):
        """
        Alters the given column name so it will match the given field.
        Note that conversion between the two by the database must be possible.
        Will not automatically add _id by default; to have this behavour, pass
        explicit_name=False.

        @param table_name: The name of the table to add the column to
        @param name: The name of the column to alter
        @param field: The new field definition to use
        """

        # hook for the field to do any resolution prior to it's attributes being queried
        if hasattr(field, 'south_init'):
            field.south_init()

        qn = connection.ops.quote_name
        
        # Add _id or whatever if we need to
        field.set_attributes_from_name(name)
        if not explicit_name:
            name = field.column
        
        # Drop all check constraints. TODO: Add the right ones back.
        if self.has_check_constraints:
            check_constraints = self._constraints_affecting_columns(table_name, [name], "CHECK")
            for constraint in check_constraints:
                self.execute(self.delete_check_sql % {'table': qn(table_name), 'constraint': qn(constraint)})

        # First, change the type
        params = {
            "column": qn(name),
            "type": self._db_type_for_alter_column(field)            
        }

        # SQLs is a list of (SQL, values) pairs.
        sqls = [(self.alter_string_set_type % params, [])]

        # Next, set any default
        if not field.null and field.has_default():
            default = field.get_default()
            sqls.append(('ALTER COLUMN %s SET DEFAULT %%s ' % (qn(name),), [default]))
        else:
            sqls.append(('ALTER COLUMN %s DROP DEFAULT' % (qn(name),), []))


        # Next, nullity
        params = {
            "column": qn(name),
            "type": field.db_type(),
        }
        if field.null:
            sqls.append((self.alter_string_set_null % params, []))
        else:
            sqls.append((self.alter_string_drop_null % params, []))
        
        # TODO: Unique

        if self.allows_combined_alters:
            sqls, values = zip(*sqls)
            self.execute(
                "ALTER TABLE %s %s;" % (qn(table_name), ", ".join(sqls)),
                flatten(values),
            )
        else:
            # Databases like e.g. MySQL don't like more than one alter at once.
            for sql, values in sqls:
                self.execute("ALTER TABLE %s %s;" % (qn(table_name), sql), values)
    
    
    def _constraints_affecting_columns(self, table_name, columns, type="UNIQUE"):
        """
        Gets the names of the constraints affecting the given columns.
        """
        
        if self.dry_run:
            raise ValueError("Cannot get constraints for columns during a dry run.")
        
        columns = set(columns)
        
        if type == "CHECK":
            ifsc_table = "constraint_column_usage"
        else:
            ifsc_table = "key_column_usage"
        
        # First, load all constraint->col mappings for this table.
        rows = self.execute("""
            SELECT kc.constraint_name, kc.column_name
            FROM information_schema.%s AS kc
            JOIN information_schema.table_constraints AS c ON
                kc.table_schema = c.table_schema AND
                kc.table_name = c.table_name AND
                kc.constraint_name = c.constraint_name
            WHERE
                kc.table_schema = %%s AND
                kc.table_name = %%s AND
                c.constraint_type = %%s
        """ % ifsc_table, ['public', table_name, type])
        # Load into a dict
        mapping = {}
        for constraint, column in rows:
            mapping.setdefault(constraint, set())
            mapping[constraint].add(column)
        # Find ones affecting these columns
        for constraint, itscols in mapping.items():
            if itscols == columns:
                yield constraint
    
    
    def create_unique(self, table_name, columns):
        """
        Creates a UNIQUE constraint on the columns on the given table.
        """
        qn = connection.ops.quote_name
        
        if not isinstance(columns, (list, tuple)):
            columns = [columns]
        
        name = self.create_index_name(table_name, columns, suffix="_uniq")
        
        cols = ", ".join(map(qn, columns))
        self.execute("ALTER TABLE %s ADD CONSTRAINT %s UNIQUE (%s)" % (qn(table_name), qn(name), cols))
        return name
    
    
    
    def delete_unique(self, table_name, columns):
        """
        Deletes a UNIQUE constraint on precisely the columns on the given table.
        """
        qn = connection.ops.quote_name
        
        if not isinstance(columns, (list, tuple)):
            columns = [columns]
        
        # Dry runs mean we can't do anything.
        if self.dry_run:
            return
        
        constraints = list(self._constraints_affecting_columns(table_name, columns))
        if not constraints:
            raise ValueError("Cannot find a UNIQUE constraint on table %s, columns %r" % (table_name, columns))
        for constraint in constraints:
            self.execute(self.delete_unique_sql % (qn(table_name), qn(constraint)))


    def column_sql(self, table_name, field_name, field, tablespace=''):
        """
        Creates the SQL snippet for a column. Used by add_column and add_table.
        """
        qn = connection.ops.quote_name
        
        field.set_attributes_from_name(field_name)
        
        # hook for the field to do any resolution prior to it's attributes being queried
        if hasattr(field, 'south_init'):
            field.south_init()
        
        # Possible hook to fiddle with the fields (e.g. defaults & TEXT on MySQL)
        field = self._field_sanity(field)
        
        sql = field.db_type()
        if sql:        
            field_output = [qn(field.column), sql]
            field_output.append('%sNULL' % (not field.null and 'NOT ' or ''))
            if field.primary_key:
                field_output.append('PRIMARY KEY')
            elif field.unique:
                # Just use UNIQUE (no indexes any more, we have delete_unique)
                field_output.append('UNIQUE')
            
            tablespace = field.db_tablespace or tablespace
            if tablespace and connection.features.supports_tablespaces and field.unique:
                # We must specify the index tablespace inline, because we
                # won't be generating a CREATE INDEX statement for this field.
                field_output.append(connection.ops.tablespace_sql(tablespace, inline=True))
            
            sql = ' '.join(field_output)
            sqlparams = ()
            # if the field is "NOT NULL" and a default value is provided, create the column with it
            # this allows the addition of a NOT NULL field to a table with existing rows
            if not field.null and not getattr(field, '_suppress_default', False) and field.has_default():
                default = field.get_default()
                # If the default is actually None, don't add a default term
                if default is not None:
                    # If the default is a callable, then call it!
                    if callable(default):
                        default = default()
                    # Now do some very cheap quoting. TODO: Redesign return values to avoid this.
                    if isinstance(default, basestring):
                        default = "'%s'" % default.replace("'", "''")
                    elif isinstance(default, (datetime.date, datetime.time, datetime.datetime)):
                        default = "'%s'" % default
                    sql += " DEFAULT %s"
                    sqlparams = (default)
            elif (not field.null and field.blank) or ((field.get_default() == '') and (not getattr(field, '_suppress_default', False))):
                if field.empty_strings_allowed and connection.features.interprets_empty_strings_as_nulls:
                    sql += " DEFAULT ''"
                # Error here would be nice, but doesn't seem to play fair.
                #else:
                #    raise ValueError("Attempting to add a non null column that isn't character based without an explicit default value.")

            if field.rel and self.supports_foreign_keys:
                self.add_deferred_sql(
                    self.foreign_key_sql(
                        table_name,
                        field.column,
                        field.rel.to._meta.db_table,
                        field.rel.to._meta.get_field(field.rel.field_name).column
                    )
                )

            if field.db_index and not field.unique:
                self.add_deferred_sql(self.create_index_sql(table_name, [field.column]))

        if hasattr(field, 'post_create_sql'):
            style = no_style()
            for stmt in field.post_create_sql(style, table_name):
                self.add_deferred_sql(stmt)

        if sql:
            return sql % sqlparams
        else:
            return None
    
    
    def _field_sanity(self, field):
        """
        Placeholder for DBMS-specific field alterations (some combos aren't valid,
        e.g. DEFAULT and TEXT on MySQL)
        """
        return field
    

    def foreign_key_sql(self, from_table_name, from_column_name, to_table_name, to_column_name):
        """
        Generates a full SQL statement to add a foreign key constraint
        """
        qn = connection.ops.quote_name
        constraint_name = '%s_refs_%s_%x' % (from_column_name, to_column_name, abs(hash((from_table_name, to_table_name))))
        return 'ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s (%s)%s;' % (
            qn(from_table_name),
            qn(truncate_name(constraint_name, connection.ops.max_name_length())),
            qn(from_column_name),
            qn(to_table_name),
            qn(to_column_name),
            connection.ops.deferrable_sql() # Django knows this
        )


    def delete_foreign_key(self, table_name, column):
        "Drop a foreign key constraint"
        qn = connection.ops.quote_name
        if self.dry_run:
            return # We can't look at the DB to get the constraints
        constraints = list(self._constraints_affecting_columns(table_name, [column], "FOREIGN KEY"))
        if not constraints:
            raise ValueError("Cannot find a FOREIGN KEY constraint on table %s, column %s" % (table_name, column))
        for constraint_name in constraints:
            self.execute(self.delete_foreign_key_sql % (qn(table_name), qn(constraint_name)))
    
    drop_foreign_key = alias('delete_foreign_key')

    
    def create_index_name(self, table_name, column_names, suffix=""):
        """
        Generate a unique name for the index
        """
        index_unique_name = ''
        
        if len(column_names) > 1:
            index_unique_name = '_%x' % abs(hash((table_name, ','.join(column_names))))
        
        # If the index name is too long, truncate it
        index_name = ('%s_%s%s%s' % (table_name, column_names[0], index_unique_name, suffix))
        if len(index_name) > self.max_index_name_length:
            part = ('_%s%s%s' % (column_names[0], index_unique_name, suffix))
            index_name = '%s%s' % (table_name[:(self.max_index_name_length-len(part))], part)
        
        return index_name


    def create_index_sql(self, table_name, column_names, unique=False, db_tablespace=''):
        """
        Generates a create index statement on 'table_name' for a list of 'column_names'
        """
        qn = connection.ops.quote_name
        if not column_names:
            print "No column names supplied on which to create an index"
            return ''

        if db_tablespace and connection.features.supports_tablespaces:
            tablespace_sql = ' ' + connection.ops.tablespace_sql(db_tablespace)
        else:
            tablespace_sql = ''

        index_name = self.create_index_name(table_name, column_names)
        qn = connection.ops.quote_name
        return 'CREATE %sINDEX %s ON %s (%s)%s;' % (
            unique and 'UNIQUE ' or '',
            qn(index_name),
            qn(table_name),
            ','.join([qn(field) for field in column_names]),
            tablespace_sql
        )

    def create_index(self, table_name, column_names, unique=False, db_tablespace=''):
        """ Executes a create index statement """
        sql = self.create_index_sql(table_name, column_names, unique, db_tablespace)
        self.execute(sql)


    def delete_index(self, table_name, column_names, db_tablespace=''):
        """
        Deletes an index created with create_index.
        This is possible using only columns due to the deterministic
        index naming function which relies on column names.
        """
        if isinstance(column_names, (str, unicode)):
            column_names = [column_names]
        name = self.create_index_name(table_name, column_names)
        qn = connection.ops.quote_name
        sql = self.drop_index_string % {"index_name": qn(name), "table_name": qn(table_name)}
        self.execute(sql)

    drop_index = alias('delete_index')
    

    def delete_column(self, table_name, name):
        """
        Deletes the column 'column_name' from the table 'table_name'.
        """
        qn = connection.ops.quote_name
        params = (qn(table_name), qn(name))
        self.execute(self.delete_column_string % params, [])

    drop_column = alias('delete_column')


    def rename_column(self, table_name, old, new):
        """
        Renames the column 'old' from the table 'table_name' to 'new'.
        """
        raise NotImplementedError("rename_column has no generic SQL syntax")

    
    def drop_primary_key(self, table_name):
        """
        Drops the old primary key.
        """
        qn = connection.ops.quote_name
        self.execute(self.drop_primary_key_string % {
            "table": qn(table_name),
            "constraint": qn(table_name+"_pkey"),
        })

    delete_primary_key = alias('drop_primary_key')

    
    def create_primary_key(self, table_name, columns):
        """
        Creates a new primary key on the specified columns.
        """
        if not isinstance(columns, (list, tuple)):
            columns = [columns]
        qn = connection.ops.quote_name
        self.execute(self.create_primary_key_string % {
            "table": qn(table_name),
            "constraint": qn(table_name+"_pkey"),
            "columns": ", ".join(map(qn, columns)),
        })
    
    
    def start_transaction(self):
        """
        Makes sure the following commands are inside a transaction.
        Must be followed by a (commit|rollback)_transaction call.
        """
        if self.dry_run:
            self.pending_transactions += 1
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)


    def commit_transaction(self):
        """
        Commits the current transaction.
        Must be preceded by a start_transaction call.
        """
        if self.dry_run:
            return
        transaction.commit()
        transaction.leave_transaction_management()


    def rollback_transaction(self):
        """
        Rolls back the current transaction.
        Must be preceded by a start_transaction call.
        """
        if self.dry_run:
            self.pending_transactions -= 1
        transaction.rollback()
        transaction.leave_transaction_management()

    def rollback_transactions_dry_run(self):
        """
        Rolls back all pending_transactions during this dry run.
        """
        if not self.dry_run:
            return
        while self.pending_transactions > 0:
            self.rollback_transaction()
        if transaction.is_dirty():
            # Force an exception, if we're still in a dirty transaction.
            # This means we are missing a COMMIT/ROLLBACK.
            transaction.leave_transaction_management()


    def send_create_signal(self, app_label, model_names):
        self.pending_create_signals.append((app_label, model_names))


    def send_pending_create_signals(self):
        # Group app_labels together
        signals = SortedDict()
        for (app_label, model_names) in self.pending_create_signals:
            try:
                signals[app_label].extend(model_names)
            except KeyError:
                signals[app_label] = list(model_names)
        # Send only one signal per app.
        for (app_label, model_names) in signals.iteritems():
            self.really_send_create_signal(app_label, list(set(model_names)))
        self.pending_create_signals = []


    def really_send_create_signal(self, app_label, model_names):
        """
        Sends a post_syncdb signal for the model specified.

        If the model is not found (perhaps it's been deleted?),
        no signal is sent.

        TODO: The behavior of django.contrib.* apps seems flawed in that
        they don't respect created_models.  Rather, they blindly execute
        over all models within the app sending the signal.  This is a
        patch we should push Django to make  For now, this should work.
        """
        if self.debug:
            print " - Sending post_syncdb signal for %s: %s" % (app_label, model_names)
        app = models.get_app(app_label)
        if not app:
            return

        created_models = []
        for model_name in model_names:
            model = models.get_model(app_label, model_name)
            if model:
                created_models.append(model)

        if created_models:
            # syncdb defaults -- perhaps take these as options?
            verbosity = 1
            interactive = True

            if hasattr(dispatcher, "send"):
                dispatcher.send(signal=models.signals.post_syncdb, sender=app,
                                app=app, created_models=created_models,
                                verbosity=verbosity, interactive=interactive)
            else:
                models.signals.post_syncdb.send(sender=app,
                                                app=app, created_models=created_models,
                                                verbosity=verbosity, interactive=interactive)

    
    def mock_model(self, model_name, db_table, db_tablespace='', 
                   pk_field_name='id', pk_field_type=models.AutoField,
                   pk_field_args=[], pk_field_kwargs={}):
        """
        Generates a MockModel class that provides enough information
        to be used by a foreign key/many-to-many relationship.

        Migrations should prefer to use these rather than actual models
        as models could get deleted over time, but these can remain in
        migration files forever.
        
        Depreciated.
        """
        class MockOptions(object):
            def __init__(self):
                self.db_table = db_table
                self.db_tablespace = db_tablespace or settings.DEFAULT_TABLESPACE
                self.object_name = model_name
                self.module_name = model_name.lower()

                if pk_field_type == models.AutoField:
                    pk_field_kwargs['primary_key'] = True

                self.pk = pk_field_type(*pk_field_args, **pk_field_kwargs)
                self.pk.set_attributes_from_name(pk_field_name)
                self.abstract = False

            def get_field_by_name(self, field_name):
                # we only care about the pk field
                return (self.pk, self.model, True, False)

            def get_field(self, name):
                # we only care about the pk field
                return self.pk

        class MockModel(object):
            _meta = None

        # We need to return an actual class object here, not an instance
        MockModel._meta = MockOptions()
        MockModel._meta.model = MockModel
        return MockModel


# Single-level flattening of lists
def flatten(ls):
    nl = []
    for l in ls:
        nl += l
    return nl
