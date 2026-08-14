# Copyright The IETF Trust 2025, All Rights Reserved
from coverage import Coverage, CoverageData, FileReporter
from coverage.control import override_config as override_coverage_config
from coverage.results import Numbers
from coverage.report_core import get_analysis_to_report
from coverage.results import Analysis
from django.conf import settings


class CoverageManager:
    checker: Coverage | None = None
    started = False

    def start(self):
        if settings.SERVER_MODE != "production" and not self.started:
            self.checker = Coverage(
                source=[settings.BASE_DIR],
                cover_pylib=False,
                omit=settings.TEST_CODE_COVERAGE_EXCLUDE_FILES,
            )
            for exclude_regex in getattr(
                settings,
                "TEST_CODE_COVERAGE_EXCLUDE_LINES",
                [],
            ):
                self.checker.exclude(exclude_regex)
            self.checker.start()
            self.started = True

    def stop(self):
        if self.checker is not None:
            self.checker.stop()

    def save(self):
        if self.checker is not None:
            self.checker.save()

    def report(self, include: list[str] | None = None):
        if self.checker is None:
            return None
        reporter = CustomDictReporter()
        with override_coverage_config(
            self.checker,
            report_include=include,
        ):
            return reporter.report(self.checker)


class CustomDictReporter:  # pragma: no cover
    total = Numbers()

    def report(self, coverage):
        coverage_data = coverage.get_data()
        coverage_data.set_query_contexts(None)
        measured_files = {}
        for file_reporter, analysis in get_analysis_to_report(coverage, None):
            measured_files[file_reporter.relative_filename()] = self.report_one_file(
                coverage_data,
                analysis,
                file_reporter,
            )
        tot_numer, tot_denom = self.total.ratio_covered
        return {
            "coverage": 1 if tot_denom == 0 else tot_numer / tot_denom,
            "covered": measured_files,
            "format": 5,
        }

    def report_one_file(
        self,
        coverage_data: CoverageData,
        analysis: Analysis,
        file_reporter: FileReporter,
    ):
        """Extract the relevant report data for a single file."""
        nums = analysis.numbers
        self.total += nums
        n_statements = nums.n_statements
        numer, denom = nums.ratio_covered
        fraction_covered = 1 if denom == 0 else numer / denom
        missing_line_nums = sorted(analysis.missing)
        # Extract missing lines from source files
        source_lines = file_reporter.source().splitlines()
        missing_lines = [source_lines[num - 1] for num in missing_line_nums]
        return (
            n_statements,
            fraction_covered,
            missing_line_nums,
            missing_lines,
        )
