"""Stage B Task 5: model-processing consent and share-scope gate.

Pure stdlib. The function ``check_authorization`` returns a list of error
messages; an empty list means the consent/scope gate passed. Private-only runs
default to ``private_only`` without a separate derivative-use declaration.
Shareable runs still require an explicit shareable derivative-use scope.
``assert_authorized_or_block``
turns failures into a typed exception that the CLI layer can convert to a
``run-manifest.step_log`` entry with ``error_type='authorization_missing'``.
"""

from __future__ import annotations

from typing import Any


class AuthorizationBlocked(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
        self.error_type = "authorization_missing"


_VALID_MODEL_PROCESSING = {"local_only", "hosted_with_consent", "hosted_only"}
_VALID_DERIVATIVE_USE = {
    "private_only",
    "shareable_with_attribution",
    "shareable_anonymous",
}
_VALID_EVIDENCE_BASIS = {"user_declaration", "license_file", "publisher_grant"}
_SHAREABLE_PURPOSES = {"shareable_anonymous", "shareable_with_attribution"}


def _field_error(field_path: str, message: str) -> str:
    return f"{field_path}: {message}"


def check_authorization(
    authorization: dict[str, Any],
    *,
    requested_model_id: str,
    requested_purpose: str,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(authorization, dict):
        return [_field_error("authorization", "must be a JSON object")]

    scope = authorization.get("scope")
    if not isinstance(scope, dict):
        errors.append(_field_error("authorization.scope", "must be a JSON object"))
        return errors

    mp = scope.get("model_processing")
    du = scope.get("derivative_use")

    if mp is None:
        errors.append(_field_error("authorization.scope.model_processing", "is required"))
    elif mp not in _VALID_MODEL_PROCESSING:
        errors.append(_field_error(
            "authorization.scope.model_processing",
            f"must be one of {sorted(_VALID_MODEL_PROCESSING)}",
        ))

    if du is not None and du not in _VALID_DERIVATIVE_USE:
        errors.append(_field_error(
            "authorization.scope.derivative_use",
            f"must be one of {sorted(_VALID_DERIVATIVE_USE)}",
        ))

    eb = authorization.get("evidence_basis")
    if eb is not None and eb not in _VALID_EVIDENCE_BASIS:
        errors.append(_field_error(
            "authorization.evidence_basis",
            f"must be one of {sorted(_VALID_EVIDENCE_BASIS)}",
        ))

    if not errors:
        # Semantic checks.
        if requested_model_id == "local":
            if mp not in {"local_only", "hosted_with_consent"}:
                errors.append(_field_error(
                    "authorization.scope.model_processing",
                    f"local model requires local_only or hosted_with_consent, got {mp!r}",
                ))
        else:
            if mp not in {"hosted_with_consent", "hosted_only"}:
                errors.append(_field_error(
                    "authorization.scope.model_processing",
                    f"hosted model {requested_model_id!r} requires hosted_with_consent or hosted_only, got {mp!r}",
                ))

        if requested_purpose in _SHAREABLE_PURPOSES:
            if du not in _SHAREABLE_PURPOSES:
                errors.append(_field_error(
                    "authorization.scope.derivative_use",
                    f"shareable purpose requires explicit shareable_* derivative_use, got {du!r}",
                ))

    return errors


def assert_authorized_or_block(
    authorization: dict[str, Any],
    *,
    requested_model_id: str,
    requested_purpose: str,
) -> None:
    errors = check_authorization(
        authorization,
        requested_model_id=requested_model_id,
        requested_purpose=requested_purpose,
    )
    if errors:
        raise AuthorizationBlocked(errors)


__all__ = [
    "AuthorizationBlocked",
    "check_authorization",
    "assert_authorized_or_block",
]
