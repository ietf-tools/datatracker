from __future__ import print_function

import debug
debug.debug = True

from django.core.urlresolvers import reverse
from django.test import TestCase

from tastypie.test import ResourceTestCaseMixin

from ietf.utils.test_data import make_test_data

class RestApi(ResourceTestCaseMixin, TestCase):
    def list_recursively(self, resource, format):
        """
        Recurse down all the app trees, retrieving all the data available.  This ensures
        that all the data represented in our test fixtures can be retrieved without raising
        any exceptions.
        """
        # print('  fetching %s' % resource)
        r = self.api_client.get(resource, format=format)
        if format == 'json':
            self.assertValidJSONResponse(r)
        elif format == 'xml':
            self.assertValidXMLResponse(r)
        else:
            raise Exception("Unknown format found when testing the RestApi: %s" % (format, ))
        data = self.deserialize(r)
        for name in data:
            if 'list_endpoint' in data[name]:
                resource = data[name]['list_endpoint']
                self.list_recursively(resource, format)

    def test_json_api_explore(self):
        make_test_data()
        apitop = reverse('ietf.api.top_level')
        self.list_recursively('%s/'%apitop, format='json')

    def test_xml_api_explore(self):
        apitop = reverse('ietf.api.top_level')
        self.assertValidXMLResponse(self.api_client.get('%s/doc/'%apitop, format='xml'))

    def test_json_doc_document(self):
        """
        Retrieve the test-data doc_document instances, and verify that some of the expected
        test-data documents are included.  There's assumption here that we don't have more
        than 100 documents in the test-data (the current count is 10)
        """
        make_test_data()
        apitop = reverse('ietf.api.top_level')
        r = self.api_client.get('%s/doc/document/'%apitop, format='json', limit=100)
        doclist = self.deserialize(r)["objects"]
        docs = dict( (doc["name"], doc) for doc in doclist )
        for name in (
                "charter-ietf-mars", 
                "charter-ietf-ames", 
                "draft-ietf-mars-test", 
                "conflict-review-imaginary-irtf-submission", 
                "status-change-imaginary-mid-review", 
                "draft-was-never-issued",
            ):
            self.assertIn(name, docs)

    def test_json_doc_relationships(self):
        """
        Follow all the relations given in the test documents, this testing that representation
        of relationships give URLs which are handled without raising exceptions.
        """
        make_test_data()
        apitop = reverse('ietf.api.top_level')
        r = self.api_client.get('%s/doc/document/'%apitop, format='json')
        doclist = self.deserialize(r)["objects"]
        for doc in doclist:
            for key in doc:
                value = doc[key]
                if isinstance(value, basestring) and value.startswith('%s/'%apitop):
                    self.api_client.get(value, format='json')
                    
