"""合成缺陷注入注册接口；只用于验证工具的反例测试。"""
from .services import (
    ConflictOverwrite, CrossInstancePseudonym, DuplicateNotDeduped,
    ProposalInFormalView, ReceiverFieldsWritable, RevocationIneffective,
    ServiceConfirmsGrade, UnapprovedMethodAllowed,
)

REGISTRY = {}


def register(name, implementation):
    if name in REGISTRY:
        raise ValueError("duplicate defect registration")
    REGISTRY[name] = implementation


register("dup-not-deduped", DuplicateNotDeduped)
register("conflict-overwrite", ConflictOverwrite)
register("service-confirms-grade", ServiceConfirmsGrade)
register("revocation-ineffective", RevocationIneffective)
register("unapproved-method-allowed", UnapprovedMethodAllowed)
register("receiver-fields-writable", ReceiverFieldsWritable)
register("proposal-in-formal-view", ProposalInFormalView)
register("cross-instance-pseudonym", CrossInstancePseudonym)
