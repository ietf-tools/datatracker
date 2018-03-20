import debug    # pyflakes:ignore
import shutil
import os

from contextlib import closing
from tempfile import mkdtemp

from ietf.submit.tests import submission_file
from ietf.utils.test_utils import TestCase
from ietf.utils.draft import Draft, getmeta

class DraftTests(TestCase):

    def setUp(self):
        file,_ = submission_file(name='draft-test-draft-class',rev='00',format='txt',templatename='test_submission.txt',group=None)
        self.draft = Draft(text=file.getvalue(),source='draft-test-draft-class-00.txt',name_from_source=False)

    def test_get_status(self):
        self.assertEqual(self.draft.get_status(),'Informational')
    
    def test_get_authors(self):
        self.assertTrue(all([u'@' in author for author in self.draft.get_authors()]))

    def test_get_authors_with_firm(self):
        self.assertTrue(all([u'@' in author for author in self.draft.get_authors_with_firm()]))
        
    def test_old_get_refs(self):
        self.assertEqual(self.draft.old_get_refs()[1][0],u'rfc2119')

    def test_get_meta(self):
        tempdir = mkdtemp()
        filename = os.path.join(tempdir,self.draft.source)
        with closing(open(filename,'w')) as file:
            file.write(self.draft.text)
        self.assertEqual(getmeta(filename)['docdeststatus'],'Informational')
