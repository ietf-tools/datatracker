# coding=utf-8

import random
from typing import Dict, Optional, Tuple


class Sampler:
    """
    Handles sampling decision logic for Scout APM.

    This class encapsulates all sampling-related functionality including:
    - Loading and managing sampling configuration
    - Pattern matching for operations (endpoints and jobs)
    - Making sampling decisions based on operation type and patterns
    """

    # Constants for operation type detection
    CONTROLLER_PREFIX = "Controller/"
    JOB_PREFIX = "Job/"

    def __init__(self, config):
        """
        Initialize sampler with Scout configuration.

        Args:
            config: ScoutConfig instance containing sampling configuration
        """
        self.config = config
        self.sample_rate = config.value("sample_rate")
        self.sample_endpoints = config.value("sample_endpoints")
        self.sample_jobs = config.value("sample_jobs")
        self.ignore_endpoints = set(
            config.value("ignore_endpoints") + config.value("ignore")
        )
        self.ignore_jobs = set(config.value("ignore_jobs"))
        self.endpoint_sample_rate = config.value("endpoint_sample_rate")
        self.job_sample_rate = config.value("job_sample_rate")

    def _any_sampling(self):
        """
        Check if any sampling is enabled.

        Returns:
            Boolean indicating if any sampling is enabled
        """
        return (
            self.sample_rate < 100
            or self.sample_endpoints
            or self.sample_jobs
            or self.ignore_endpoints
            or self.ignore_jobs
            or self.endpoint_sample_rate is not None
            or self.job_sample_rate is not None
        )

    def _find_matching_rate(
        self, name: str, patterns: Dict[str, float]
    ) -> Optional[str]:
        """
        Finds the matching sample rate for a given operation name.

        Args:
            name: The operation name to match
            patterns: Dictionary of pattern to sample rate mappings

        Returns:
            The sample rate for the matching pattern or None if no match found
        """

        for pattern, rate in patterns.items():
            if name.startswith(pattern):
                return rate
        return None

    def _get_operation_type_and_name(
        self, operation: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Determines if an operation is an endpoint or job and extracts its name.

        Args:
            operation: The full operation string (e.g. "Controller/users/show")

        Returns:
            Tuple of (type, name) where type is either 'endpoint' or 'job',
            and name is the operation name without the prefix
        """
        if operation.startswith(self.CONTROLLER_PREFIX):
            return "endpoint", operation[len(self.CONTROLLER_PREFIX) :]
        elif operation.startswith(self.JOB_PREFIX):
            return "job", operation[len(self.JOB_PREFIX) :]
        else:
            return None, None

    def get_effective_sample_rate(self, operation: str, is_ignored: bool) -> int:
        """
        Determines the effective sample rate for a given operation.

        Prioritization:
        1. Sampling rate for specific endpoint or job
        2. Specified ignore pattern or flag for operation
        3. Global endpoint or job sample rate
        4. Global sample rate

        Args:
            operation: The operation string (e.g. "Controller/users/show")
            is_ignored: boolean for if the specific transaction is ignored

        Returns:
            Integer between 0 and 100 representing sample rate
        """
        op_type, name = self._get_operation_type_and_name(operation)
        patterns = self.sample_endpoints if op_type == "endpoint" else self.sample_jobs
        ignores = self.ignore_endpoints if op_type == "endpoint" else self.ignore_jobs
        default_operation_rate = (
            self.endpoint_sample_rate if op_type == "endpoint" else self.job_sample_rate
        )

        if not op_type or not name:
            return self.sample_rate
        matching_rate = self._find_matching_rate(name, patterns)
        if matching_rate is not None:
            return matching_rate
        for prefix in ignores:
            if name.startswith(prefix) or is_ignored:
                return 0
        if default_operation_rate is not None:
            return default_operation_rate

        # Fall back to global sample rate
        return self.sample_rate

    def should_sample(self, operation: str, is_ignored: bool) -> bool:
        """
        Determines if an operation should be sampled.
        If no sampling is enabled, always return True.

        Args:
            operation: The operation string (e.g. "Controller/users/show"
                   or "Job/mailer")

        Returns:
            Boolean indicating whether to sample this operation
        """
        if not self._any_sampling():
            return True
        return random.randint(1, 100) <= self.get_effective_sample_rate(
            operation, is_ignored
        )
