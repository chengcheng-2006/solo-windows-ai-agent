from __future__ import annotations

from dataclasses import dataclass

from .enums import RiskLevel


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    reasons: tuple[str, ...]


class RiskClassifier:
    R3_TERMS = {
        "delete important",
        "format disk",
        "firewall",
        "security policy",
        "driver install",
        "send message",
        "publish",
        "payment",
        "pay ",
        "submit application",
        "upload sensitive",
        "identity card",
        "password",
        "unknown executable",
        "owner permission",
        "\u5220\u9664\u91cd\u8981",
        "\u683c\u5f0f\u5316",
        "\u9632\u706b\u5899",
        "\u5b89\u5168\u7b56\u7565",
        "\u53d1\u9001\u6d88\u606f",
        "\u53d1\u5e03",
        "\u4ed8\u6b3e",
        "\u652f\u4ed8",
        "\u6b63\u5f0f\u7533\u8bf7",
        "\u4e0a\u4f20\u654f\u611f",
        "\u8eab\u4efd\u8bc1",
        "\u5bc6\u7801",
        "\u6240\u6709\u8005\u6743\u9650",
    }
    R2_TERMS = {
        "install",
        "uninstall",
        "modify config",
        "write file",
        "move file",
        "delete file",
        "submit form",
        "login",
        "\u5b89\u88c5",
        "\u5378\u8f7d",
        "\u4fee\u6539\u914d\u7f6e",
        "\u5199\u5165\u6587\u4ef6",
        "\u79fb\u52a8\u6587\u4ef6",
        "\u5220\u9664\u6587\u4ef6",
        "\u63d0\u4ea4\u8868\u5355",
        "\u767b\u5f55",
    }
    R1_TERMS = {
        "create test file",
        "edit sandbox",
        "download test",
        "start test process",
        "\u521b\u5efa\u6d4b\u8bd5\u6587\u4ef6",
        "\u4fee\u6539\u6c99\u7bb1",
        "\u4e0b\u8f7d\u6d4b\u8bd5",
    }

    def classify(self, objective: str, task_type: str, requested: RiskLevel | None = None) -> RiskAssessment:
        text = f"{task_type} {objective}".lower()
        if any(term in text for term in self.R3_TERMS):
            assessed = RiskAssessment(RiskLevel.R3, ("high_risk_or_irreversible_action",))
        elif any(term in text for term in self.R2_TERMS):
            assessed = RiskAssessment(RiskLevel.R2, ("modifying_or_external_action",))
        elif any(term in text for term in self.R1_TERMS):
            assessed = RiskAssessment(RiskLevel.R1, ("low_risk_reversible_action",))
        else:
            assessed = RiskAssessment(RiskLevel.R0, ("read_only_or_no_side_effect",))
        if requested and _rank(requested) > _rank(assessed.level):
            return RiskAssessment(requested, (*assessed.reasons, "requester_elevated_risk"))
        return assessed


def _rank(level: RiskLevel) -> int:
    return int(level.value[-1])

