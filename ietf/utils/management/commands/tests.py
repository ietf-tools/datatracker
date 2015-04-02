from django.core.management import call_command
from django.test import TestCase
from django.utils.six import StringIO

import debug                            # pyflakes:ignore

class CoverageChangeTestCase(TestCase):

    def test_coverage_change(self):
        master = StringIO(
            """{
              "5.12.0": {
                "code": {
                  "coverage": 0.5921474057048117, 
                  "covered": {
                    "ietf/api": 0.6493506493506493, 
                    "ietf/community/constants": 0.0, 
                    "ietf/dbtemplate/forms": 0.4782608695652174
                  }
                }, 
                "template": {
                  "coverage": 0.7604166666666666, 
                  "covered": {
                    "admin/group/group/change_form.html": false, 
                    "base.html": true, 
                    "community/customize_display.html": false, 
                    "doc/add_comment.html": true
                  }
                }, 
                "time": "2015-02-25T22:01:02Z", 
                "url": {
                  "coverage": 0.5374732334047109, 
                  "covered": {
                    "^$": true, 
                    "^accounts/$": true, 
                    "^api/v1/?$": true, 
                    "^community/personal/$": false
                  }
                }
              }, 
              "version": "5.12.0"
            }
            """)
        latest = StringIO(
            """{
              "latest": {
                "code": {
                  "coverage": 0.5921474057048117, 
                  "covered": {
                    "ietf/api": 0.65,
                    "ietf/community/constants": 0.50, 
                    "ietf/dbtemplate/forms": 0.4782608695652174
                  }
                }, 
                "template": {
                  "coverage": 0.7604166666666666, 
                  "covered": {
                    "admin/group/group/change_form.html": true, 
                    "base.html": true, 
                    "community/customize_display.html": false, 
                    "doc/add_comment.html": true
                  }
                }, 
                "time": "2015-02-25T22:01:02Z", 
                "url": {
                  "coverage": 0.5374732334047109, 
                  "covered": {
                    "^$": true, 
                    "^accounts/$": true, 
                    "^api/v1/?$": false, 
                    "^community/personal/$": true
                  }
                }
              },
              "version":"latest"
            }
            """)
        output = StringIO()
        call_command('coverage_changes', master, latest, stdout=output)
        text = output.getvalue()
        
        for l in [
            r"admin/group/group/change_form.html                             False      True",
            r"^api/v1/?$                                                      True     False",
            r"^community/personal/$                                          False      True",
            r"ietf/community/constants                                           -   50.0  %",
            ]:
            self.assertTrue(l in text, msg="Missing line in coverage_change output:\n'%s'\n"%l)
