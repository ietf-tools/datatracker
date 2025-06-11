# Copyright The IETF Trust 2025, All Rights Reserved
from django.core.exceptions import ValidationError
from zxcvbn import zxcvbn


class StrongPasswordValidator:
    message = "This password does not meet complexity requirements and is easily guessable."
    code = "weak"
    min_zxcvbn_score = 3

    def __init__(self, message=None, code=None, min_zxcvbn_score=None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        if min_zxcvbn_score is not None:
            self.min_zxcvbn_score = min_zxcvbn_score

    def validate(self, password, user=None):
        """Validate that a password is strong enough"""
        strength_report = zxcvbn(password[:72], max_length=72)
        if strength_report["score"] < self.min_zxcvbn_score:
            raise ValidationError(message=self.message, code=self.code)
