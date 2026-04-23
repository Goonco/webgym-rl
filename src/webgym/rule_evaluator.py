from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RuleCheck:
    passed: bool
    message: str


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    checks: tuple[RuleCheck, ...]

    @property
    def reward(self) -> float:
        return 1.0 if self.passed else 0.0

    def summary(self) -> str:
        if not self.checks:
            return "no evaluation rules"
        return "; ".join(check.message for check in self.checks)


def collect_selectors(evaluation: Any) -> list[str]:
    selectors: list[str] = []
    for rule in _rules(evaluation):
        selector = rule.get("selector")
        if isinstance(selector, str) and selector and selector not in selectors:
            selectors.append(selector)
    return selectors


def uses_page_html(evaluation: Any) -> bool:
    for rule in _rules(evaluation):
        if "selector" not in rule and ("html" in rule or "html_regex" in rule):
            return True
    return False


def evaluate_page_rules(evaluation: Any, snapshot: Mapping[str, Any]) -> EvaluationResult:
    rules = _rules(evaluation)
    if not rules:
        return EvaluationResult(False, (RuleCheck(False, "no evaluation rules configured"),))

    mode = "all"
    if isinstance(evaluation, Mapping):
        mode = str(evaluation.get("mode", evaluation.get("operator", "all"))).lower()
    if mode not in {"all", "any"}:
        raise ValueError(f"Unsupported evaluation mode: {mode}")

    checks = tuple(_evaluate_rule(rule, snapshot, index) for index, rule in enumerate(rules, 1))
    passed = (
        all(check.passed for check in checks)
        if mode == "all"
        else any(check.passed for check in checks)
    )
    return EvaluationResult(passed, checks)


def _rules(evaluation: Any) -> list[Mapping[str, Any]]:
    if evaluation is None:
        return []
    if isinstance(evaluation, list):
        return [rule for rule in evaluation if isinstance(rule, Mapping)]
    if not isinstance(evaluation, Mapping):
        return []

    rules = evaluation.get("rules")
    if isinstance(rules, list):
        return [rule for rule in rules if isinstance(rule, Mapping)]

    # Allow a single rule dict for small hand-written task files.
    if any(key in evaluation for key in _RULE_KEYS):
        return [evaluation]
    return []


_RULE_KEYS = {
    "selector",
    "text",
    "text_regex",
    "html",
    "html_regex",
    "url",
    "url_regex",
    "title",
    "title_regex",
    "attribute",
    "attr",
}


def _evaluate_rule(rule: Mapping[str, Any], snapshot: Mapping[str, Any], index: int) -> RuleCheck:
    selector = rule.get("selector")
    if isinstance(selector, str) and selector:
        return _evaluate_selector_rule(rule, snapshot, selector, index)
    return _evaluate_page_rule(rule, snapshot, index)


def _evaluate_selector_rule(
    rule: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    selector: str,
    index: int,
) -> RuleCheck:
    selector_errors = snapshot.get("selector_errors", {})
    if isinstance(selector_errors, Mapping) and selector in selector_errors:
        return RuleCheck(False, f"rule {index}: invalid selector {selector!r}")

    elements_by_selector = snapshot.get("elements", {})
    elements = []
    if isinstance(elements_by_selector, Mapping):
        raw_elements = elements_by_selector.get(selector, [])
        if isinstance(raw_elements, list):
            elements = [element for element in raw_elements if isinstance(element, Mapping)]

    visible_filter = rule.get("visible")
    if visible_filter is not None:
        expected_visible = bool(visible_filter)
        elements = [
            element for element in elements if bool(element.get("visible")) == expected_visible
        ]

    if not elements:
        return RuleCheck(False, f"rule {index}: no matching elements for selector {selector!r}")

    if not _has_content_condition(rule):
        return RuleCheck(True, f"rule {index}: selector {selector!r} exists")

    for element in elements:
        if _element_satisfies(rule, element):
            return RuleCheck(True, f"rule {index}: selector {selector!r} matched")

    return RuleCheck(False, f"rule {index}: selector {selector!r} did not satisfy content rule")


def _evaluate_page_rule(
    rule: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    index: int,
) -> RuleCheck:
    if "url" in rule:
        passed = _matches(snapshot.get("url", ""), rule["url"], rule, normalize_space=False)
        return RuleCheck(passed, _message(index, "url", passed))
    if "url_regex" in rule:
        passed = _matches(snapshot.get("url", ""), rule["url_regex"], rule, match="regex")
        return RuleCheck(passed, _message(index, "url_regex", passed))
    if "title" in rule:
        passed = _matches(snapshot.get("title", ""), rule["title"], rule)
        return RuleCheck(passed, _message(index, "title", passed))
    if "title_regex" in rule:
        passed = _matches(snapshot.get("title", ""), rule["title_regex"], rule, match="regex")
        return RuleCheck(passed, _message(index, "title_regex", passed))
    if "html" in rule:
        passed = _matches(snapshot.get("html", ""), rule["html"], rule, normalize_space=False)
        return RuleCheck(passed, _message(index, "html", passed))
    if "html_regex" in rule:
        passed = _matches(
            snapshot.get("html", ""),
            rule["html_regex"],
            rule,
            match="regex",
            normalize_space=False,
        )
        return RuleCheck(passed, _message(index, "html_regex", passed))
    if "text_regex" in rule:
        passed = _matches(snapshot.get("text", ""), rule["text_regex"], rule, match="regex")
        return RuleCheck(passed, _message(index, "text_regex", passed))
    if "text" in rule:
        passed = _matches(snapshot.get("text", ""), rule["text"], rule)
        return RuleCheck(passed, _message(index, "text", passed))

    return RuleCheck(False, f"rule {index}: unsupported rule shape")


def _element_satisfies(rule: Mapping[str, Any], element: Mapping[str, Any]) -> bool:
    conditions: list[bool] = []

    if "text" in rule:
        conditions.append(_matches(element.get("text", ""), rule["text"], rule))
    if "text_regex" in rule:
        conditions.append(
            _matches(element.get("text", ""), rule["text_regex"], rule, match="regex")
        )
    if "html" in rule:
        conditions.append(
            _matches(element.get("html", ""), rule["html"], rule, normalize_space=False)
        )
    if "html_regex" in rule:
        conditions.append(
            _matches(
                element.get("html", ""),
                rule["html_regex"],
                rule,
                match="regex",
                normalize_space=False,
            )
        )

    attribute_name = rule.get("attribute", rule.get("attr"))
    if isinstance(attribute_name, str) and attribute_name:
        attributes = element.get("attributes", {})
        actual = ""
        if isinstance(attributes, Mapping):
            actual = str(attributes.get(attribute_name, ""))
        if not actual and attribute_name in element:
            actual = str(element.get(attribute_name, ""))
        expected = rule.get("value", rule.get("attr_value", ""))
        conditions.append(_matches(actual, expected, rule))

    return bool(conditions) and all(conditions)


def _has_content_condition(rule: Mapping[str, Any]) -> bool:
    return any(
        key in rule
        for key in (
            "text",
            "text_regex",
            "html",
            "html_regex",
            "attribute",
            "attr",
        )
    )


def _matches(
    actual: Any,
    expected: Any,
    rule: Mapping[str, Any],
    *,
    match: str | None = None,
    normalize_space: bool | None = None,
) -> bool:
    if isinstance(expected, list):
        return any(
            _matches(actual, option, rule, match=match, normalize_space=normalize_space)
            for option in expected
        )

    actual_text = "" if actual is None else str(actual)
    expected_text = "" if expected is None else str(expected)

    match_mode = str(match or rule.get("match", "contains")).lower()
    if match_mode not in {"contains", "exact", "regex"}:
        raise ValueError(f"Unsupported match mode: {match_mode}")

    if normalize_space is None:
        normalize_space = bool(rule.get("normalize_space", True))
    if normalize_space:
        actual_text = _normalize_space(actual_text)
        expected_text = _normalize_space(expected_text)

    case_sensitive = bool(rule.get("case_sensitive", False))
    if match_mode == "regex":
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(expected_text, actual_text, flags=flags) is not None

    if not case_sensitive:
        actual_text = actual_text.casefold()
        expected_text = expected_text.casefold()

    if match_mode == "exact":
        return actual_text == expected_text
    return expected_text in actual_text


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _message(index: int, target: str, passed: bool) -> str:
    status = "matched" if passed else "did not match"
    return f"rule {index}: {target} {status}"
