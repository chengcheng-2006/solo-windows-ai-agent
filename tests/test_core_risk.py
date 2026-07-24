"""Tests for risk classifier — R0/R1/R2/R3 classification."""
import pytest

from solo.core.enums import RiskLevel
from solo.core.risk import RiskClassifier


@pytest.fixture
def classifier():
    return RiskClassifier()


def test_r3_high_risk(classifier):
    r = classifier.classify("Delete all files in the important project directory")
    assert r.level == RiskLevel.R3
    assert len(r.reasons) > 0


def test_r3_delete_permanently(classifier):
    r = classifier.classify("delete permanently all logs")
    assert r.level == RiskLevel.R3


def test_r3_irreversible(classifier):
    r = classifier.classify("This is an irreversible operation")
    assert r.level == RiskLevel.R3


def test_r2_write(classifier):
    r = classifier.classify("write a new config file to the settings directory")
    assert r.level == RiskLevel.R2


def test_r2_modify(classifier):
    r = classifier.classify("modify the system configuration")
    assert r.level == RiskLevel.R2


def test_r2_delete_file(classifier):
    r = classifier.classify("delete the temporary log file")
    assert r.level == RiskLevel.R2


def test_r2_execute(classifier):
    r = classifier.classify("execute this shell command")
    assert r.level == RiskLevel.R2


def test_r1_read(classifier):
    r = classifier.classify("read the contents of a text file")
    assert r.level == RiskLevel.R1


def test_r1_search(classifier):
    r = classifier.classify("search for documents on the desktop")
    assert r.level == RiskLevel.R1


def test_r1_check(classifier):
    r = classifier.classify("check the system status")
    assert r.level == RiskLevel.R1


def test_r0_default(classifier):
    r = classifier.classify("Count words in a test text file")
    assert r.level == RiskLevel.R0


def test_r0_greeting(classifier):
    r = classifier.classify("Hello, how are you?")
    assert r.level == RiskLevel.R0


def test_r0_math(classifier):
    r = classifier.classify("calculate 2 + 2")
    assert r.level == RiskLevel.R0


def test_case_insensitive(classifier):
    r_upper = classifier.classify("DELETE IMPORTANT FILE")
    assert r_upper.level == RiskLevel.R3
    r_lower = classifier.classify("delete important file")
    assert r_lower.level == RiskLevel.R3


def test_reasons_not_empty_for_risk_levels(classifier):
    for obj in ["delete all files", "write a file", "read a file", "hello"]:
        r = classifier.classify(obj)
        assert len(r.reasons) > 0, f"No reasons for {obj!r} (level={r.level})"
