"""Dependency-free local intelligence kernel for YIB/WORLD.

This is a deterministic, offline-first reasoning scaffold, not an LLM. It provides
intent routing, bounded planning, evidence labels, local memory hooks, and
self-checks without API keys or network calls. A trained local model can be
attached later behind the same interface.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import re
from typing import Any, Callable


TRUTH_LABELS = {"VERIFIED", "OBSERVED", "REPORTED", "INFERRED", "BLOCKED", "UNKNOWN"}
HIGH_RISK_TERMS = (
    "delete", "deploy", "publish", "payment", "transfer", "نشر", "احذف",
    "حذف", "ادفع", "تحويل", "شراء", "إرسال للجميع",
)


@dataclass
class KernelResult:
    text: str
    intent: str
    truth: str
    mode: str = "LOCAL_RULE_KERNEL"
    actions: list[dict[str, Any]] | None = None
    needs_approval: bool = False
    timestamp: str = ""

    def __post_init__(self) -> None:
        if self.truth not in TRUTH_LABELS:
            raise ValueError("invalid truth label")
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.actions is None:
            self.actions = []

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalIntelligenceKernel:
    """Offline kernel: honest deterministic behavior, bounded actions, testable."""

    def __init__(self, memory_read: Callable[[], list[dict[str, Any]]] | None = None):
        self.memory_read = memory_read or (lambda: [])

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def route(self, text: str) -> str:
        q = self._normalize(text)
        if not q:
            return "empty"
        if re.search(r"\b(status|truth|health|الحقيقة|الحالة|اختبر|تحقق)\b", q):
            return "status"
        if re.search(r"\b(resume|continue|اكمل|أكمل|استمر)\b", q):
            return "resume"
        if re.search(r"\b(memory|remember|ذاكرة|تذكر|استرجع)\b", q):
            return "memory"
        if re.search(r"\b(plan|steps|خطة|خطوات|كيف)\b", q):
            return "plan"
        return "general"

    def handle(self, text: str) -> KernelResult:
        q = text.strip()
        if not q:
            return KernelResult("أرسل طلبًا غير فارغ.", "empty", "OBSERVED")
        intent = self.route(q)
        risk = any(term in q.lower() for term in HIGH_RISK_TERMS)
        if intent == "status":
            return KernelResult(
                "الحالة المحلية: نواة القواعد تعمل دون شبكة أو مفتاح API. "
                "هذا اختبار للنواة وليس إثباتًا لنموذج لغوي كبير. "
                "الذاكرة: " + str(len(self.memory_read())) + " سجلًا متاحًا.",
                intent, "OBSERVED",
            )
        if intent == "resume":
            return KernelResult(
                "تم تحديد مسار الاستئناف المحلي. أستطيع متابعة مهام النواة "
                "المسجلة؛ لا أزعم تنفيذ أي إجراء خارجي غير موثق.",
                intent, "OBSERVED",
            )
        if intent == "memory":
            records = self.memory_read()[-10:]
            return KernelResult(
                json.dumps(records, ensure_ascii=False) if records else
                "لا توجد سجلات ذاكرة متاحة عبر موصل الذاكرة المحلي.",
                intent, "OBSERVED",
            )
        if intent == "plan":
            steps = [
                {"step": 1, "action": "فهم الطلب وتحديد النتيجة المطلوبة", "state": "READY"},
                {"step": 2, "action": "فحص الأدلة والقدرات المحلية المتاحة", "state": "READY"},
                {"step": 3, "action": "تنفيذ إجراء محلي محدود إن كان مدعومًا", "state": "GATED"},
                {"step": 4, "action": "اختبار النتيجة وحفظ دليل قابل للاسترجاع", "state": "REQUIRED"},
            ]
            return KernelResult(json.dumps(steps, ensure_ascii=False), intent, "INFERRED", steps, risk)
        return KernelResult(
            "استقبلت النواة المحلية الطلب، لكن هذه النسخة لا تحتوي نموذجًا لغويًا "
            "مدرّبًا ولا ينبغي تقديم قواعد ثابتة على أنها فهم عام. "
            "يمكنني تنفيذ المسارات المحلية المحددة واختبارها؛ "
            "الرد التوليدي المفتوح غير متاح في هذه النواة وحدها.",
            intent, "OBSERVED", needs_approval=risk,
        )


def self_test() -> dict[str, Any]:
    """Offline regression tests; safe to run without credentials or network."""
    kernel = LocalIntelligenceKernel(memory_read=lambda: [{"id": "test-1"}])
    cases = [
        ("الحالة", "status"),
        ("أكمل", "resume"),
        ("الذاكرة", "memory"),
        ("خطة وخطوات", "plan"),
        ("", "empty"),
    ]
    results = []
    for prompt, expected in cases:
        actual = kernel.handle(prompt)
        results.append({
            "case": expected,
            "pass": actual.intent == expected and actual.truth in TRUTH_LABELS,
            "actual": actual.intent,
        })
    return {
        "mode": "LOCAL_RULE_KERNEL",
        "network_used": False,
        "api_key_required": False,
        "passed": all(item["pass"] for item in results),
        "tests": results,
        "truth": "OBSERVED",
    }


if __name__ == "__main__":
    print(json.dumps(self_test(), ensure_ascii=False, indent=2))
