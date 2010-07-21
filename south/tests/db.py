import unittest

from south.db import db
from django.db import connection, models

# Create a list of error classes from the various database libraries
errors = []
try:
    from psycopg2 import ProgrammingError
    errors.append(ProgrammingError)
except ImportError:
    pass
errors = tuple(errors)

class TestOperations(unittest.TestCase):

    """
    Tests if the various DB abstraction calls work.
    Can only test a limited amount due to DB differences.
    """

    def setUp(self):
        db.debug = False
        db.clear_deferred_sql()

    def test_create(self):
        """
        Test creation and deletion of tables.
        """
        cursor = connection.cursor()
        # It needs to take at least 2 args
        self.assertRaises(TypeError, db.create_table)
        self.assertRaises(TypeError, db.create_table, "test1")
        # Empty tables (i.e. no columns) are not fine, so make at least 1
        db.create_table("test1", [('email_confirmed', models.BooleanField(default=False))])
        db.start_transaction()
        # And should exist
        cursor.execute("SELECT * FROM test1")
        # Make sure we can't do the same query on an empty table
        try:
            cursor.execute("SELECT * FROM nottheretest1")
            self.fail("Non-existent table could be selected!")
        except:
            pass
        # Clear the dirty transaction
        db.rollback_transaction()
        db.start_transaction()
        # Remove the table
        db.drop_table("test1")
        # Make sure it went
        try:
            cursor.execute("SELECT * FROM test1")
            self.fail("Just-deleted table could be selected!")
        except:
            pass
        # Clear the dirty transaction
        db.rollback_transaction()
        db.start_transaction()
        # Try deleting a nonexistent one
        try:
            db.delete_table("nottheretest1")
            self.fail("Non-existent table could be deleted!")
        except:
            pass
        db.rollback_transaction()
    
    def test_foreign_keys(self):
        """
        Tests foreign key creation, especially uppercase (see #61)
        """
        Test = db.mock_model(model_name='Test', db_table='test5a',
                             db_tablespace='', pk_field_name='ID',
                             pk_field_type=models.AutoField, pk_field_args=[])
        db.start_transaction()
        db.create_table("test5a", [('ID', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True))])
        db.create_table("test5b", [
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('UNIQUE', models.ForeignKey(Test)),
        ])
        db.execute_deferred_sql()
        db.rollback_transaction()
    
    def test_rename(self):
        """
        Test column renaming
        """
        cursor = connection.cursor()
        db.create_table("test_rn", [('spam', models.BooleanField(default=False))])
        db.start_transaction()
        # Make sure we can select the column
        cursor.execute("SELECT spam FROM test_rn")
        # Rename it
        db.rename_column("test_rn", "spam", "eggs")
        cursor.execute("SELECT eggs FROM test_rn")
        try:
            cursor.execute("SELECT spam FROM test_rn")
            self.fail("Just-renamed column could be selected!")
        except:
            pass
        db.rollback_transaction()
        db.delete_table("test_rn")
    
    def test_dry_rename(self):
        """
        Test column renaming while --dry-run is turned on (should do nothing)
        See ticket #65
        """
        cursor = connection.cursor()
        db.create_table("test_drn", [('spam', models.BooleanField(default=False))])
        db.start_transaction()
        # Make sure we can select the column
        cursor.execute("SELECT spam FROM test_drn")
        # Rename it
        db.dry_run = True
        db.rename_column("test_drn", "spam", "eggs")
        db.dry_run = False
        cursor.execute("SELECT spam FROM test_drn")
        try:
            cursor.execute("SELECT eggs FROM test_drn")
            self.fail("Dry-renamed new column could be selected!")
        except:
            pass
        db.rollback_transaction()
        db.delete_table("test_drn")
    
    def test_table_rename(self):
        """
        Test column renaming
        """
        cursor = connection.cursor()
        db.create_table("testtr", [('spam', models.BooleanField(default=False))])
        db.start_transaction()
        # Make sure we can select the column
        cursor.execute("SELECT spam FROM testtr")
        # Rename it
        db.rename_table("testtr", "testtr2")
        cursor.execute("SELECT spam FROM testtr2")
        try:
            cursor.execute("SELECT spam FROM testtr")
            self.fail("Just-renamed column could be selected!")
        except:
            pass
        db.rollback_transaction()
        db.delete_table("testtr2")
    
    def test_index(self):
        """
        Test the index operations
        """
        db.create_table("test3", [
            ('SELECT', models.BooleanField(default=False)),
            ('eggs', models.IntegerField(unique=True)),
        ])
        db.execute_deferred_sql()
        db.start_transaction()
        # Add an index on that column
        db.create_index("test3", ["SELECT"])
        # Add another index on two columns
        db.create_index("test3", ["SELECT", "eggs"])
        # Delete them both
        db.delete_index("test3", ["SELECT"])
        db.delete_index("test3", ["SELECT", "eggs"])
        # Delete the unique index/constraint
        db.delete_unique("test3", ["eggs"])
        db.rollback_transaction()
        db.delete_table("test3")
    
    def test_primary_key(self):
        """
        Test the primary key operations
        """
        db.create_table("test_pk", [
            ('id', models.IntegerField(primary_key=True)),
            ('new_pkey', models.IntegerField()),
            ('eggs', models.IntegerField(unique=True)),
        ])
        db.execute_deferred_sql()
        db.start_transaction()
        # Remove the default primary key, and make eggs it
        db.drop_primary_key("test_pk")
        db.create_primary_key("test_pk", "new_pkey")
        # Try inserting a now-valid row pair
        db.execute("INSERT INTO test_pk (id, new_pkey, eggs) VALUES (1, 2, 3), (1, 3, 4)")
        db.rollback_transaction()
        db.delete_table("test_pk")
    
    def test_alter(self):
        """
        Test altering columns/tables
        """
        db.create_table("test4", [
            ('spam', models.BooleanField(default=False)),
            ('eggs', models.IntegerField()),
        ])
        db.start_transaction()
        # Add a column
        db.add_column("test4", "add1", models.IntegerField(default=3), keep_default=False)
        # Add a FK with keep_default=False (#69)
        User = db.mock_model(model_name='User', db_table='auth_user', db_tablespace='', pk_field_name='id', pk_field_type=models.AutoField, pk_field_args=[], pk_field_kwargs={})
        db.add_column("test4", "user", models.ForeignKey(User, null=True), keep_default=False)
        db.delete_column("test4", "add1")
        
        db.rollback_transaction()
        db.delete_table("test4")
        
    def test_alter_column_postgres_multiword(self):
        """
        Tests altering columns with multiple words in Postgres types (issue #125)
        e.g. 'datetime with time zone', look at django/db/backends/postgresql/creation.py
        """
        db.create_table("test_multiword", [
            ('col_datetime', models.DateTimeField(null=True)),
            ('col_integer', models.PositiveIntegerField(null=True)),
            ('col_smallint', models.PositiveSmallIntegerField(null=True)),
            ('col_float', models.FloatField(null=True)),
        ])
        
        # test if 'double precision' is preserved
        db.alter_column('test_multiword', 'col_float', models.FloatField('float', null=True))

        # test if 'CHECK ("%(column)s" >= 0)' is stripped
        db.alter_column('test_multiword', 'col_integer', models.PositiveIntegerField(null=True))
        db.alter_column('test_multiword', 'col_smallint', models.PositiveSmallIntegerField(null=True))

        # test if 'with timezone' is preserved
        if db.backend_name == "postgres":
            db.start_transaction()
            db.execute("INSERT INTO test_multiword (col_datetime) VALUES ('2009-04-24 14:20:55+02')")
            db.alter_column('test_multiword', 'col_datetime', models.DateTimeField(auto_now=True))
            assert db.execute("SELECT col_datetime = '2009-04-24 14:20:55+02' FROM test_multiword")[0][0]
            db.rollback_transaction()

        
        db.delete_table("test_multiword")
    
    def test_alter_constraints(self):
        """
        Tests that going from a PostiveIntegerField to an IntegerField drops
        the constraint on the database.
        """
        db.create_table("test_alterc", [
            ('num', models.PositiveIntegerField()),
        ])
        # Add in some test values
        db.execute("INSERT INTO test_alterc (num) VALUES (1), (2)")
        # Ensure that adding a negative number is bad
        db.start_transaction()
        try:
            db.execute("INSERT INTO test_alterc (num) VALUES (-3)")
        except:
            db.rollback_transaction()
        else:
            self.fail("Could insert a negative integer into a PositiveIntegerField.")
        # Alter it to a normal IntegerField
        db.alter_column("test_alterc", "num", models.IntegerField())
        # It should now work
        db.execute("INSERT INTO test_alterc (num) VALUES (-3)")
        db.delete_table("test_alterc")
    
    def test_unique(self):
        """
        Tests creating/deleting unique constraints.
        """
        db.create_table("test_unique2", [
            ('id', models.AutoField(primary_key=True)),
        ])
        db.create_table("test_unique", [
            ('spam', models.BooleanField(default=False)),
            ('eggs', models.IntegerField()),
            ('ham', models.ForeignKey(db.mock_model('Unique2', 'test_unique2'))),
        ])
        # Add a constraint
        db.create_unique("test_unique", ["spam"])
        # Shouldn't do anything during dry-run
        db.dry_run = True
        db.delete_unique("test_unique", ["spam"])
        db.dry_run = False
        db.delete_unique("test_unique", ["spam"])
        db.create_unique("test_unique", ["spam"])
        db.start_transaction()
        # Test it works
        db.execute("INSERT INTO test_unique2 (id) VALUES (1), (2)")
        db.execute("INSERT INTO test_unique (spam, eggs, ham_id) VALUES (true, 0, 1), (false, 1, 2)")
        try:
            db.execute("INSERT INTO test_unique (spam, eggs, ham_id) VALUES (true, 2, 1)")
        except:
            db.rollback_transaction()
        else:
            self.fail("Could insert non-unique item.")
        # Drop that, add one only on eggs
        db.delete_unique("test_unique", ["spam"])
        db.execute("DELETE FROM test_unique")
        db.create_unique("test_unique", ["eggs"])
        db.start_transaction()
        # Test similarly
        db.execute("INSERT INTO test_unique (spam, eggs, ham_id) VALUES (true, 0, 1), (false, 1, 2)")
        try:
            db.execute("INSERT INTO test_unique (spam, eggs, ham_id) VALUES (true, 1, 1)")
        except:
            db.rollback_transaction()
        else:
            self.fail("Could insert non-unique item.")
        # Drop those, test combined constraints
        db.delete_unique("test_unique", ["eggs"])
        db.execute("DELETE FROM test_unique")
        db.create_unique("test_unique", ["spam", "eggs", "ham_id"])
        db.start_transaction()
        # Test similarly
        db.execute("INSERT INTO test_unique (spam, eggs, ham_id) VALUES (true, 0, 1), (false, 1, 1)")
        try:
            db.execute("INSERT INTO test_unique (spam, eggs, ham_id) VALUES (true, 0, 1)")
        except:
            db.rollback_transaction()
        else:
            self.fail("Could insert non-unique pair.")
        db.delete_unique("test_unique", ["spam", "eggs", "ham_id"])
    
    def test_capitalised_constraints(self):
        """
        Under PostgreSQL at least, capitalised constrains must be quoted.
        """
        db.start_transaction()
        try:
            db.create_table("test_capconst", [
                ('SOMECOL', models.PositiveIntegerField(primary_key=True)),
            ])
            # Alter it so it's not got the check constraint
            db.alter_column("test_capconst", "SOMECOL", models.IntegerField())
        finally:
            db.rollback_transaction()
    
    def test_text_default(self):
        """
        MySQL cannot have blank defaults on TEXT columns.
        """
        db.start_transaction()
        try:
            db.create_table("test_textdef", [
                ('textcol', models.TextField(blank=True)),
            ])
        finally:
            db.rollback_transaction()
    
    def test_add_unique_fk(self):
        """
        Test adding a ForeignKey with unique=True or a OneToOneField
        """
        db.create_table("test_add_unique_fk", [
            ('spam', models.BooleanField(default=False))
        ])
        db.start_transaction()
        
        db.add_column("test_add_unique_fk", "mock1", models.ForeignKey(db.mock_model('Mock', 'mock'), null=True, unique=True))
        db.add_column("test_add_unique_fk", "mock2", models.OneToOneField(db.mock_model('Mock', 'mock'), null=True))
        
        db.rollback_transaction()
        db.delete_table("test_add_unique_fk")
