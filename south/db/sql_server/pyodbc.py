from django.db import models
from django.db.models import fields
from south.db import generic

class DatabaseOperations(generic.DatabaseOperations):
    """
    django-pyodbc (sql_server.pyodbc) implementation of database operations.
    """
    
    backend_name = "pyodbc"
    
    add_column_string = 'ALTER TABLE %s ADD %s;'
    alter_string_set_type = 'ALTER COLUMN %(column)s %(type)s'
    alter_string_set_null = 'ALTER COLUMN %(column)s %(type)s NULL'
    alter_string_drop_null = 'ALTER COLUMN %(column)s %(type)s NOT NULL'
    
    allows_combined_alters = False

    drop_index_string = 'DROP INDEX %(index_name)s ON %(table_name)s'
    drop_constraint_string = 'ALTER TABLE %(table_name)s DROP CONSTRAINT %(constraint_name)s'
    delete_column_string = 'ALTER TABLE %s DROP COLUMN %s'
    
    default_schema_name = "dbo"


    def delete_column(self, table_name, name):
        q_table_name, q_name = (self.quote_name(table_name), self.quote_name(name))

        # Zap the indexes
        for ind in self._find_indexes_for_column(table_name,name):
            params = {'table_name':q_table_name, 'index_name': ind}
            sql = self.drop_index_string % params
            self.execute(sql, [])

        # Zap the constraints
        for const in self._find_constraints_for_column(table_name,name):
            params = {'table_name':q_table_name, 'constraint_name': const}
            sql = self.drop_constraint_string % params
            self.execute(sql, [])

        # Zap default if exists
        drop_default = self.drop_column_default_sql(table_name, name)
        if drop_default:
            sql = "ALTER TABLE [%s] %s" % (table_name, drop_default)
            self.execute(sql, [])

        # Finally zap the column itself
        self.execute(self.delete_column_string % (q_table_name, q_name), [])

    def _find_indexes_for_column(self, table_name, name):
        "Find the indexes that apply to a column, needed when deleting"

        sql = """
        SELECT si.name, si.id, sik.colid, sc.name
        FROM dbo.sysindexes SI WITH (NOLOCK)
        INNER JOIN dbo.sysindexkeys SIK WITH (NOLOCK)
            ON  SIK.id = Si.id
            AND SIK.indid = SI.indid
        INNER JOIN dbo.syscolumns SC WITH (NOLOCK)
            ON  SI.id = SC.id
            AND SIK.colid = SC.colid
        WHERE SI.indid !=0
            AND Si.id = OBJECT_ID('%s')
            AND SC.name = '%s'
        """
        idx = self.execute(sql % (table_name, name), [])
        return [i[0] for i in idx]


    def _find_constraints_for_column(self, table_name, name):
        """
        Find the constraints that apply to a column, needed when deleting. Defaults not included.
        This is more general than the parent _constraints_affecting_columns, as on MSSQL this
        includes PK and FK constraints.
        """

        sql = """
        SELECT  CONSTRAINT_NAME
        FROM INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE
        WHERE CONSTRAINT_CATALOG = TABLE_CATALOG
          AND CONSTRAINT_SCHEMA = TABLE_SCHEMA
          AND TABLE_CATALOG = %s
          AND TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s 
        """
        db_name = self._get_setting('name')
        schema_name = self._get_schema_name()
        cons = self.execute(sql, [db_name, schema_name, table_name, name])
        return [c[0] for c in cons]

    def _alter_set_defaults(self, field, name, params, sqls): 
        "Subcommand of alter_column that sets default values (overrideable)"
        # First drop the current default if one exists
        table_name = self.quote_name(params['table_name'])
        drop_default = self.drop_column_default_sql(table_name, name)
        if drop_default:
            sqls.append((drop_default, []))
            
        # Next, set any default
        
        if field.has_default(): # was: and not field.null
            default = field.get_default()
            sqls.append(('ADD DEFAULT %%s for %s' % (self.quote_name(name),), [default]))
        #else:
        #    sqls.append(('ALTER COLUMN %s DROP DEFAULT' % (self.quote_name(name),), []))

    def drop_column_default_sql(self, table_name, name, q_name=None):
        "MSSQL specific drop default, which is a pain"

        sql = """
        SELECT object_name(cdefault)
        FROM syscolumns
        WHERE id = object_id('%s')
        AND name = '%s'
        """
        cons = self.execute(sql % (table_name, name), [])
        if cons and cons[0] and cons[0][0]:
            return "DROP CONSTRAINT %s" % cons[0][0]
        return None

    def _fix_field_definition(self, field):
        if isinstance(field, fields.BooleanField):
            if field.default == True:
                field.default = 1
            if field.default == False:
                field.default = 0

    def add_column(self, table_name, name, field, keep_default=True):
        self._fix_field_definition(field)
        generic.DatabaseOperations.add_column(self, table_name, name, field, keep_default)

    def create_table(self, table_name, field_defs):
        # Tweak stuff as needed
        for _, f in field_defs:
            self._fix_field_definition(f)

        # Run
        generic.DatabaseOperations.create_table(self, table_name, field_defs)

    def _find_referencing_fks(self, table_name):
        "MSSQL does not support cascading FKs when dropping tables, we need to implement."

        # FK -- Foreign Keys
        # UCTU -- Unique Constraints Table Usage
        # FKTU -- Foreign Key Table Usage
        # (last two are both really CONSTRAINT_TABLE_USAGE, different join conditions)
        sql = """
        SELECT FKTU.TABLE_SCHEMA as REFING_TABLE_SCHEMA,
               FKTU.TABLE_NAME as REFING_TABLE_NAME,
               FK.[CONSTRAINT_NAME] as FK_NAME
        FROM [INFORMATION_SCHEMA].[REFERENTIAL_CONSTRAINTS] FK
        JOIN [INFORMATION_SCHEMA].[CONSTRAINT_TABLE_USAGE] UCTU
          ON FK.UNIQUE_CONSTRAINT_CATALOG = UCTU.CONSTRAINT_CATALOG and
             FK.UNIQUE_CONSTRAINT_NAME = UCTU.CONSTRAINT_NAME and
             FK.UNIQUE_CONSTRAINT_SCHEMA = UCTU.CONSTRAINT_SCHEMA
        JOIN [INFORMATION_SCHEMA].[CONSTRAINT_TABLE_USAGE] FKTU
          ON FK.CONSTRAINT_CATALOG = FKTU.CONSTRAINT_CATALOG and
             FK.CONSTRAINT_NAME = FKTU.CONSTRAINT_NAME and
             FK.CONSTRAINT_SCHEMA = FKTU.CONSTRAINT_SCHEMA
        WHERE FK.CONSTRAINT_CATALOG = %s
          AND UCTU.TABLE_SCHEMA = %s -- REFD_TABLE_SCHEMA
          AND UCTU.TABLE_NAME = %s -- REFD_TABLE_NAME
        """
        db_name = self._get_setting('name')
        schema_name = self._get_schema_name()
        return self.execute(sql, [db_name, schema_name, table_name])
                
    def delete_table(self, table_name, cascade=True):
        """
        Deletes the table 'table_name'.
        """
        if cascade:
            refing = self._find_referencing_fks(table_name)
            for schmea, table, constraint in refing:
                table = ".".join(map (self.quote_name, [schmea, table]))
                params = dict(table_name = table,
                              constraint_name = self.quote_name(constraint))
                sql = self.drop_constraint_string % params
                self.execute(sql, [])
            cascade = False
        super(DatabaseOperations, self).delete_table(table_name, cascade)
            
    def rename_column(self, table_name, old, new):
        """
        Renames the column of 'table_name' from 'old' to 'new'.
        WARNING - This isn't transactional on MSSQL!
        """
        if old == new:
            # No Operation
            return
        # Examples on the MS site show the table name not being quoted...
        params = (table_name, self.quote_name(old), self.quote_name(new))
        self.execute("EXEC sp_rename '%s.%s', %s, 'COLUMN'" % params)

    def rename_table(self, old_table_name, table_name):
        """
        Renames the table 'old_table_name' to 'table_name'.
        WARNING - This isn't transactional on MSSQL!
        """
        if old_table_name == table_name:
            # No Operation
            return
        params = (self.quote_name(old_table_name), self.quote_name(table_name))
        self.execute('EXEC sp_rename %s, %s' % params)

    # Copied from South's psycopg2 backend
    def _db_type_for_alter_column(self, field):
        """
        Returns a field's type suitable for ALTER COLUMN.
        Strips CHECKs from PositiveSmallIntegerField) and PositiveIntegerField
        @param field: The field to generate type for
        """
        super_result = super(DatabaseOperations, self)._db_type_for_alter_column(field)
        if isinstance(field, models.PositiveSmallIntegerField) or isinstance(field, models.PositiveIntegerField):
            return super_result.split(" ")[0]
        return super_result

