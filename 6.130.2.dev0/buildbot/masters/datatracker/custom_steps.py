# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import re

from buildbot.plugins import steps

class TestCrawlerShellCommand(steps.WarningCountingShellCommand):
    name = "testcrawl"
    haltOnFailure = 1
    flunkOnFailure = 1
    descriptionDone = ["test crawler"]
    command=["bin/test-crawl"]

    warningPatterns = {
        "exceptions":       "^(Traceback|  File|    |.*Error|.*Exception)",
        "failed":           " FAIL  ",
        "warnings":         " WARN",
        "slow":             " SLOW",
        "invalid_html":     " invalid html:",
    }

    logline = "^ *(?P<elapsed>\d+:\d+:\d+) +(?P<pages>\d+) +(?P<queue>\d+) +(?P<result>\d+) +(?P<runtime>\d+.\d+)s +(?P<message>.+)"
    
    def setTestResults(self, **kwargs):
        """
        Called by subclasses to set the relevant statistics; this actually
        adds to any statistics already present
        """
        for kw in kwargs:
            value = kwargs[kw]
            if value.isdigit():
                # Counter
                value = int(value)
                value += self.step_status.getStatistic(kw, 0)
            elif re.search("^[0-9]+\.[0-9]+$", value):
                # Runtime
                value = float(value)
                value += self.step_status.getStatistic(kw, 0)
            else:
                # This is a percentage, and we can't add them
                pass                    
            self.step_status.setStatistic(kw, value)

    def createSummary(self, log):
        """
        Match log lines against warningPattern.

        Warnings are collected into another log for this step, and the
        build-wide 'warnings-count' is updated."""

        warnings = {}
        wregex = {}

        regex_class = re.compile("").__class__

        if not isinstance(self.logline, regex_class):
            self.logline = re.compile(self.logline)

        for key in self.warningPatterns:
            warnings[key] = []
            pattern = self.warningPatterns[key]
            if not isinstance(pattern, regex_class):
                wregex[key] = re.compile(pattern)
            else:
                wregex[key] = pattern

        # Count matches to the various warning patterns
        last_line = None
        for line in log.getText().split("\n"):
            for key in wregex:
                match = re.search(wregex[key], line)
                if match:
                    warnings[key].append(line)
            if re.search(self.logline, line):
                last_line = line

        # If there were any warnings, make the log if lines with warnings
        # available
        for key in warnings:
            if len(warnings[key]) > 0:
                self.addCompleteLog("%s (%d)" % (key, len(warnings[key])),
                        "\n".join(warnings[key]) + "\n")
                self.step_status.setStatistic(key, len(warnings[key]))
            self.setProperty(key, len(warnings[key]), "TestCrawlerShellCommand")

        if last_line:
            match = re.search(self.logline, last_line)
            for key in ['elapsed', 'pages']:
                info = match.group(key)
                self.step_status.setStatistic(key, info)
                self.setProperty(key, info, "TestCrawlerShellCommand")

    def describe(self, done=False):
        description = steps.WarningCountingShellCommand.describe(self, done)
        if done:
            description = description[:]  # make a private copy
            for name in ["time", "elapsed", "pages", "failed", "warnings", "slow", "invalid_html", ]:
                if name in self.step_status.statistics:
                    value = self.step_status.getStatistic(name)
                    displayName = name.replace('_', ' ')
                    # special case. Mph.
                    if   type(value) is float: # this is run-time
                        description.append('%s: %.2fs' % (displayName, value))
                    elif type(value) is int:
                        description.append('%s: %d' % (displayName, value))
                    else:
                        description.append('%s: %s' % (displayName, value))
        return description


class DjangoTest(steps.WarningCountingShellCommand):

    name = "test"
    warnOnFailure = 1
    description = ["testing"]
    descriptionDone = ["test"]
    command = ["manage.py", "test", ]

    regexPatterns = {
        "tests":            "Ran (\d+) tests in [0-9.]+s",
        "time":             "Ran \d+ tests in ([0-9.]+)s",
        "skipped":          "(?:OK|FAILED).*skipped=(\d+)",
        "failed":           "FAILED.*failures=(\d+)",
        "errors":           "FAILED.*errors=(\d+)",
        "template_coverage":" +Template coverage: +([0-9.]+%)",
        "url_coverage":     " +Url coverage: +([0-9.]+%)",
        "code_coverage":    " +Code coverage: +([0-9.]+%)",
    }

    def setTestResults(self, **kwargs):
        """
        Called by subclasses to set the relevant statistics; this actually
        adds to any statistics already present
        """
        for kw in kwargs:
            value = kwargs[kw]
            if value.isdigit():
                # Counter
                value = int(value)
                value += self.step_status.getStatistic(kw, 0)
            elif re.search("^[0-9]+\.[0-9]+$", value):
                # Runtime
                value = float(value)
                value += self.step_status.getStatistic(kw, 0)
            else:
                # This is a percentage, and we can't add them
                pass                    
            self.step_status.setStatistic(kw, value)

    def createSummary(self, log):
        info = {}
        for line in log.getText().split("\n"):
            for key in self.regexPatterns:
                regex = self.regexPatterns[key]
                match = re.search(regex, line)
                if match:
                    info[key] = match.group(1)
        self.setTestResults(**info)

    def describe(self, done=False):
        description = steps.WarningCountingShellCommand.describe(self, done)
        if done:
            description = description[:]  # make a private copy
            self.step_status.statistics["passed"] = (
                self.step_status.getStatistic("tests",0) -
                self.step_status.getStatistic("skipped",0) -
                self.step_status.getStatistic("failed",0) -
                self.step_status.getStatistic("errors",0))
            for name in ["time", "tests", "passed", "skipped", "failed", "errors", "template_coverage", "url_coverage", "code_coverage", ]:
                if name in self.step_status.statistics:
                    value = self.step_status.getStatistic(name)
                    displayName = name.replace('_', ' ')
                    # special case. Mph.
                    if displayName == 'template coverage':
                        displayName = 'templ. coverage'
                    if   type(value) is float: # this is run-time
                        description.append('%s: %.2fs' % (displayName, value))
                    elif type(value) is int:
                        description.append('%s: %d' % (displayName, value))
                    else:
                        description.append('%s: %s' % (displayName, value))
        return description
