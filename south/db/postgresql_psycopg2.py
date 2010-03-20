
from django.db import connection, models
from south.db import generic

class DatabaseOperations(generic.DatabaseOperations):

    """
    PsycoPG2 implementation of database operations.
    """
    
    backend_name = "postgres"

    def rename_column(self, table_name, old, new):
        if old == new:
            return []
        qn = connection.ops.quote_name
        params = (qn(table_name), qn(old), qn(new))
        self.execute('ALTER TABLE %s RENAME COLUMN %s TO %s;' % params)
    
    def rename_table(self, old_table_name, table_name):
        "will rename the table and an associated ID sequence and primary key index"
        # First, rename the table
        generic.DatabaseOperations.rename_table(self, old_table_name, table_name)
        # Then, try renaming the ID sequence
        # (if you're using other AutoFields... your problem, unfortunately)
        self.commit_transaction()
        self.start_transaction()
        try:
            generic.DatabaseOperations.rename_table(self, old_table_name+"_id_seq", table_name+"_id_seq")
        except:
            if self.debug:
                print "   ~ No such sequence (ignoring error)"
            self.rollback_transaction()
        else:
            self.commit_transaction()
        self.start_transaction()

        # Rename primary key index, will not rename other indices on
        # the table that are used by django (e.g. foreign keys). Until
        # figure out how, you need to do this yourself.
        try:
            generic.DatabaseOperations.rename_table(self, old_table_name+"_pkey", table_name+ "_pkey")
        except:
            if self.debug:
                print "   ~ No such primary key (ignoring error)"
            self.rollback_transaction()
        else:
            self.commit_transaction()
        self.start_transaction()


    def rename_index(self, old_index_name, index_name):
        "Rename an index individually"
        generic.DatabaseOperations.rename_table(self, old_index_name, index_name)

    def _db_type_for_alter_column(self, field):
        """
        Returns a field's type suitable for ALTER COLUMN.
        Strips CHECKs from PositiveSmallIntegerField) and PositiveIntegerField
        @param field: The field to generate type for
        """
        if isinstance(field, models.PositiveSmallIntegerField) or isinstance(field, models.PositiveIntegerField):
            return field.db_type().split(" ")[0]
        return super(DatabaseOperations, self)._db_type_for_alter_column(field)
