# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase
#from io import StringIO

import debug                            # pyflakes:ignore

class CoverageChangeTestCase(TestCase):

    def test_coverage_change(self):
        master_txt ="""{
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
            """
        latest_txt = """{
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
            """
        mfh, master = tempfile.mkstemp(suffix='.json')
        with io.open(master, "w") as file:
            file.write(master_txt)
        lfh, latest = tempfile.mkstemp(suffix='.json')
        with io.open(latest, "w") as file:
            file.write(latest_txt)
        output = io.StringIO()
        call_command('coverage_changes', master, latest, stdout=output)
        text = output.getvalue()
        os.unlink(master)
        os.unlink(latest)

        for l in [
            r"   False      True  admin/group/group/change_form.html                        ",
            r"    True     False  ^api/v1/?$                                                ",
            r"   False      True  ^community/personal/$                                     ",
            r"       -   50.0  %  ietf/community/constants                                  ",
            ]:
            self.assertTrue(l in text, msg="Missing line in coverage_change output:\n'%s'\n"%l)
