import inspect
import re

from django.db import connection
from django.db.models import ForeignKey

from south.db import generic

# from how .schema works as shown on http://www.sqlite.org/sqlite.html
GET_TABLE_DEF_SQL = """    
SELECT sql FROM
       (SELECT * FROM sqlite_master UNION ALL
        SELECT * FROM sqlite_temp_master)
    WHERE tbl_name LIKE '%s'
      AND type!='meta' AND sql NOT NULL AND name NOT LIKE 'sqlite_%%%%'
    ORDER BY substr(type,2,1), name;"""
    
class DatabaseOperations(generic.DatabaseOperations):

    """
    SQLite3 implementation of database operations.
    """
    
    backend_name = "sqlite3"

    # SQLite ignores foreign key constraints. I wish I could.
    supports_foreign_keys = False
    defered_alters = {}
    def __init__(self):
        super(DatabaseOperations, self).__init__()
        # holds fields defintions gotten from the sql schema.  the key is the table name and then
        # it's a list of 2 item lists.  the two items in the list are fieldname, sql definition
        self._fields = {}

    def _populate_current_structure(self, table_name, force=False):
        # get if we don't have it already or are being forced to refresh it
        if force or not table_name in self._fields.keys():
            cursor = connection.cursor()
            cursor.execute(GET_TABLE_DEF_SQL % table_name)
            create_table = cursor.fetchall()[0][0]
            first = create_table.find('(')
            last = create_table.rfind(')')
            # rip out the CREATE TABLE xxx ( ) and only get the field definitions plus
            # add the trailing comma to make the next part easier
            fields_part = create_table[first+1: last] + ','
            # pull out the field name and definition for each field
            self._fields[table_name] = re.findall(r'"(\S+?)"(.*?),', fields_part, re.DOTALL)
        
    def _rebuild_table(self, table_name, new_fields):
        """
        rebuilds the table using the new definitions.  only one change 
        can be made per call and it must be either a rename, alter or
        delete
        """
        self._populate_current_structure(table_name)
        
        current_fields = self._fields[table_name]
        temp_table_name = '%s_temp' % table_name
        operation = None
        changed_field = None
        
        if len(current_fields) != len(new_fields):
            if len(current_fields) - len(new_fields) != 1:
                raise ValueError('only one field can be deleted at a time, found %s missing fields' % str(len(current_fields) - len(new_fields)))
            operation = 'delete'
            current_field_names = [f[0] for f in current_fields]
            new_field_names = [f[0] for f in new_fields]
            # find the deleted field
            for f in current_field_names:
                if not f in new_field_names:
                    changed_field = f
                    break
        else:
            found = False
            for current, new in zip(current_fields, new_fields):
                if current[0] != new[0]:
                    if found:
                        raise ValueError('can only handle one change per call, found more than one')
                    operation = 'rename'
                    changed_field = (current[0], new[0])
                    found = True
                elif current[1] != new[1]:
                    if found:
                        raise ValueError('can only handle one change per call, found more than one')
                    operation = 'alter'
                    changed_field = current[0]
                    found = True
            if not found:
                raise ValueError('no changed found')
        # create new table as temp
        create = 'CREATE TABLE "%s" ( %s )'
        fields_sql = ','.join(['"%s" %s' % (f[0], f[1]) for f in new_fields])
        sql = create % (temp_table_name, fields_sql)
        
        cursor = connection.cursor()
        cursor.execute(sql)
        
        # copy over data
        # rename, redef or delete?
        if operation in ['rename', 'alter']:
            sql = 'insert into %s select * from %s' % (temp_table_name, table_name)
        elif operation == 'delete':
            new_field_names = ','.join(['"%s"' % f[0] for f in new_fields])
            sql = 'insert into %s select %s from %s' % (temp_table_name, new_field_names, table_name)
        cursor.execute(sql)
                                
        # remove existing table
        self.delete_table(table_name)
        
        # rename new table
        self.rename_table(temp_table_name, table_name)
        
        # repopulate field info
        self._populate_current_structure(table_name, force=True)

    def _defer_alter_sqlite_table(self, table_name, field_renames={}):
        table_renames = self.defered_alters.get(table_name, {})
        table_renames.update(field_renames)
        self.defered_alters[table_name] = table_renames

    # You can't add UNIQUE columns with an ALTER TABLE.
    def add_column(self, table_name, name, field, *args, **kwds):
        # Run ALTER TABLE with no unique column
        unique, field._unique, field.db_index = field.unique, False, False
        # If it's not nullable, and has no default, raise an error (SQLite is picky)
        if (not field.null and 
            (not field.has_default() or field.get_default() is None) and
            not field.empty_strings_allowed):
            raise ValueError("You cannot add a null=False column without a default value.")
        # Don't try and drop the default, it'll fail
        kwds['keep_default'] = True
        generic.DatabaseOperations.add_column(self, table_name, name, field, *args, **kwds)
        # If it _was_ unique, make an index on it.
        if unique:
            self.create_index(table_name, [field.column], unique=True)
    
    def _alter_sqlite_table(self, table_name, field_renames={}):
        
        # Detect the model for the given table name
        model = None
        for omodel in self.current_orm:
            if omodel._meta.db_table == table_name:
                model = omodel
        if model is None:
            raise ValueError("Cannot find ORM model for '%s'." % table_name)

        temp_name = table_name + "_temporary_for_schema_change"
        self.rename_table(table_name, temp_name)
        fields = [(fld.name, fld) for fld in model._meta.fields]
        self.create_table(table_name, fields)

        columns = [fld.column for name, fld in fields]
        self.copy_data(temp_name, table_name, columns, field_renames)
        self.delete_table(temp_name, cascade=False)
    
    def alter_column(self, table_name, name, field, explicit_name=True):
        self._populate_current_structure(table_name)
        new_fields = []
        for field_name, field_def in self._fields[table_name]:
            if field_name == name:
                if isinstance(field, ForeignKey):
                    field_name = name[:-3] # exclude the _id when calling column_sql
                else:
                    field_name = name
                new_fields.append((name, self.column_sql(table_name, field_name, field)))
            else:
                new_fields.append((field_name, field_def))
        self._rebuild_table(table_name, new_fields)
                

    def delete_column(self, table_name, column_name):
        self._populate_current_structure(table_name)
        new_fields = []
        for field_name, field_def in self._fields[table_name]:
            if field_name != column_name:
                new_fields.append((field_name, field_def))
        self._rebuild_table(table_name, new_fields)
    
    def rename_column(self, table_name, old, new):
        self._populate_current_structure(table_name)
        new_fields = []
        for field_name, field_def in self._fields[table_name]:
            if field_name == old:
                new_fields.append((new, field_def))
            else:
                new_fields.append((field_name, field_def))
        self._rebuild_table(table_name, new_fields)
            
    # Nor unique creation
    def create_unique(self, table_name, columns):
        """
        Not supported under SQLite.
        """
        print "   ! WARNING: SQLite does not support adding unique constraints. Ignored."
    
    # Nor unique deletion
    def delete_unique(self, table_name, columns):
        """
        Not supported under SQLite.
        """
        print "   ! WARNING: SQLite does not support removing unique constraints. Ignored."
    
    # No cascades on deletes
    def delete_table(self, table_name, cascade=True):
        generic.DatabaseOperations.delete_table(self, table_name, False)

    def copy_data(self, src, dst, fields, field_renames={}):
        qn = connection.ops.quote_name
        q_fields = [field for field in fields]
        for old, new in field_renames.items():
            q_fields[q_fields.index(new)] = "%s AS %s" % (old, qn(new))
        sql = "INSERT INTO %s SELECT %s FROM %s;" % (qn(dst), ', '.join(q_fields), qn(src))
        self.execute(sql)

    def execute_deferred_sql(self):
        """
        Executes all deferred SQL, resetting the deferred_sql list
        """
        for table_name, params in self.defered_alters.items():
            self._alter_sqlite_table(table_name, params)
        self.defered_alters = {}

        generic.DatabaseOperations.execute_deferred_sql(self)

    
