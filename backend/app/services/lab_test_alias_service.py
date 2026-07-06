"""Services for reviewing and applying lab test aliases."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import AuditAction, AuditLog, LabTestAlias, LabTestType
from app.services.base import BaseService


def normalize_alias_key(value: str) -> str:
    """Normalize raw lab wording for alias grouping and matching."""
    text = str(value or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class AliasMatch:
    alias_id: int
    lab_test_type: LabTestType


@dataclass(frozen=True)
class FuzzyMatch:
    lab_test_type: LabTestType
    score: float


class LabTestAliasService(BaseService[LabTestAlias]):
    """Review workflow and matching helpers for lab test aliases."""

    BROAD_REJECT_KEYS = {"mold", "total count", "heavy metals"}
    # Words that describe a grouping rather than a specific analyte. A phrase
    # made up entirely of these (plus category words) is category-like and must
    # not fuzzy-map to a specific test/panel.
    GENERIC_TOKENS = {
        "panel",
        "total",
        "count",
        "test",
        "tests",
        "analysis",
        "screen",
        "profile",
    }

    def __init__(self) -> None:
        super().__init__(LabTestAlias)

    def _category_tokens(self, active_lab_types: list[LabTestType]) -> set[str]:
        """Tokens drawn from the catalog's test_category labels, with naive
        singular/plural variants so `heavy metal`/`metals` are all covered."""
        tokens: set[str] = set()
        for lab_type in active_lab_types:
            category = getattr(lab_type, "test_category", None)
            if not category:
                continue
            for token in normalize_alias_key(category).split():
                tokens.add(token)
                tokens.add(token[:-1] if token.endswith("s") else token + "s")
        return tokens

    def _is_category_like(self, key: str, active_lab_types: list[LabTestType]) -> bool:
        """True when every token of `key` is a category/grouping word (i.e. the
        phrase names a category, not a specific analyte) — e.g. `Heavy Metals`,
        `Heavy Metal`, `Metals Panel`, `Total Count`."""
        tokens = [token for token in key.split() if token]
        if not tokens:
            return True
        vocabulary = self._category_tokens(active_lab_types) | self.GENERIC_TOKENS
        return all(token in vocabulary for token in tokens)

    def list_aliases(
        self,
        db: Session,
        page: int,
        page_size: int,
        status: Optional[str] = None,
        search: Optional[str] = None,
        lab_name: Optional[str] = None,
    ) -> tuple[list[LabTestAlias], int]:
        query = db.query(LabTestAlias).options(joinedload(LabTestAlias.lab_test_type))
        if status:
            query = query.filter(LabTestAlias.status == status)
        if lab_name is not None:
            query = query.filter(LabTestAlias.lab_name == (lab_name or None))
        if search:
            term = f"%{search.strip()}%"
            query = query.join(LabTestAlias.lab_test_type).filter(
                or_(
                    LabTestAlias.raw_phrase.ilike(term),
                    LabTestAlias.normalized_key.ilike(term),
                    LabTestAlias.last_filename.ilike(term),
                    LabTestType.test_name.ilike(term),
                )
            )
        total = query.count()
        items = (
            query.order_by(LabTestAlias.updated_at.desc(), LabTestAlias.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def update_alias(
        self, db: Session, alias: LabTestAlias, values: dict[str, Any], user_id: int
    ) -> LabTestAlias:
        old = alias.to_dict()
        if "raw_phrase" in values and values["raw_phrase"] is not None:
            alias.raw_phrase = values["raw_phrase"].strip()
            alias.normalized_key = normalize_alias_key(alias.raw_phrase)
        if "lab_name" in values:
            lab_name = values["lab_name"]
            alias.lab_name = lab_name.strip() if lab_name and lab_name.strip() else None
        if "lab_test_type_id" in values and values["lab_test_type_id"] is not None:
            target = (
                db.query(LabTestType)
                .filter(
                    LabTestType.id == values["lab_test_type_id"],
                    LabTestType.is_active == True,
                )
                .first()
            )
            if not target:
                raise ValueError("Target lab test type not found or inactive")
            alias.lab_test_type_id = target.id
        db.flush()
        self._audit_alias(
            db,
            AuditAction.UPDATE,
            alias.id,
            old,
            alias.to_dict(),
            user_id,
            "Lab test alias edited",
        )
        db.commit()
        db.refresh(alias)
        return alias

    def approve_alias(
        self, db: Session, alias: LabTestAlias, user_id: int
    ) -> LabTestAlias:
        if not alias.lab_test_type or not alias.lab_test_type.is_active:
            raise ValueError("Target lab test type is inactive")
        old = alias.to_dict()
        now = datetime.utcnow()
        competitors = (
            db.query(LabTestAlias)
            .filter(
                LabTestAlias.id != alias.id,
                LabTestAlias.normalized_key == alias.normalized_key,
                (
                    LabTestAlias.lab_name.is_(None)
                    if alias.lab_name is None
                    else LabTestAlias.lab_name == alias.lab_name
                ),
                LabTestAlias.status.in_(["pending", "approved"]),
            )
            .all()
        )
        for competitor in competitors:
            competitor_old = competitor.to_dict()
            competitor.status = "disabled"
            competitor.disabled_by_id = user_id
            competitor.disabled_at = now
            competitor.disable_reason = "Superseded by approved alias"
            self._audit_alias(
                db,
                AuditAction.UPDATE,
                competitor.id,
                competitor_old,
                competitor.to_dict(),
                user_id,
                "Lab test alias disabled by competing approval",
            )
        alias.status = "approved"
        alias.approved_by_id = user_id
        alias.approved_at = now
        alias.disabled_by_id = None
        alias.disabled_at = None
        alias.disable_reason = None
        db.flush()
        self._audit_alias(
            db,
            AuditAction.UPDATE,
            alias.id,
            old,
            alias.to_dict(),
            user_id,
            "Lab test alias approved",
        )
        db.commit()
        db.refresh(alias)
        return alias

    def disable_alias(
        self,
        db: Session,
        alias: LabTestAlias,
        user_id: int,
        reason: Optional[str] = None,
    ) -> LabTestAlias:
        old = alias.to_dict()
        alias.status = "disabled"
        alias.disabled_by_id = user_id
        alias.disabled_at = datetime.utcnow()
        alias.disable_reason = reason
        db.flush()
        self._audit_alias(
            db,
            AuditAction.UPDATE,
            alias.id,
            old,
            alias.to_dict(),
            user_id,
            "Lab test alias disabled",
        )
        db.commit()
        db.refresh(alias)
        return alias

    def resolve_approved_alias(
        self, db: Session, raw_name: str, lab_name: Optional[str]
    ) -> Optional[AliasMatch]:
        key = normalize_alias_key(raw_name)
        if not key:
            return None
        scopes = [lab_name.strip() if lab_name and lab_name.strip() else None, None]
        seen = set()
        for scope in scopes:
            if scope in seen:
                continue
            seen.add(scope)
            alias = (
                db.query(LabTestAlias)
                .join(LabTestAlias.lab_test_type)
                .filter(
                    LabTestAlias.normalized_key == key,
                    LabTestAlias.status == "approved",
                    LabTestType.is_active == True,
                    (
                        LabTestAlias.lab_name.is_(None)
                        if scope is None
                        else LabTestAlias.lab_name == scope
                    ),
                )
                .order_by(LabTestAlias.updated_at.desc())
                .first()
            )
            if alias:
                return AliasMatch(alias_id=alias.id, lab_test_type=alias.lab_test_type)
        return None

    def find_fuzzy_lab_test_type(
        self, raw_name: str, active_lab_types: list[LabTestType]
    ) -> Optional[FuzzyMatch]:
        key = normalize_alias_key(raw_name)
        if not key or key in self.BROAD_REJECT_KEYS:
            return None
        # Reject category-like phrases (any spelling/plurality) — they must not
        # auto-map to a specific test or panel.
        if self._is_category_like(key, active_lab_types):
            return None
        raw_tokens = set(key.split())
        single_token = len(raw_tokens) <= 1
        if single_token and len(key) < 5:
            return None

        scored: list[tuple[float, LabTestType]] = []
        for lab_type in active_lab_types:
            target_key = normalize_alias_key(lab_type.test_name)
            target_tokens = set(target_key.split())
            token_overlap = len(raw_tokens & target_tokens) / max(
                len(raw_tokens), len(target_tokens), 1
            )
            sequence = SequenceMatcher(None, key, target_key).ratio()
            token_similarity = 0.0
            if raw_tokens and target_tokens:
                token_similarity = sum(
                    max(
                        SequenceMatcher(None, raw, target).ratio()
                        for target in target_tokens
                    )
                    for raw in raw_tokens
                ) / len(raw_tokens)
            score = (
                (sequence * 0.55) + (token_overlap * 0.25) + (token_similarity * 0.20)
            )
            if raw_tokens and raw_tokens.issubset(target_tokens):
                score += 0.08
            scored.append((min(score, 1.0), lab_type))

        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            return None
        best_score, best = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        if best_score < 0.65:
            return None
        # A single bare token that is an exact component of a multi-word test
        # names only part of a combined test, so don't auto-map it (e.g. `Yeast`
        # must not become `Yeast & Mold`). A single-token typo of a single-word
        # test (e.g. `Glutn` -> `Gluten`) is still allowed.
        if single_token:
            best_tokens = set(normalize_alias_key(best.test_name).split())
            if len(best_tokens) > 1 and next(iter(raw_tokens)) in best_tokens:
                return None
        if second_score and best_score - second_score < 0.08:
            return None
        return FuzzyMatch(lab_test_type=best, score=best_score)

    def record_alias_suggestion(
        self,
        db: Session,
        raw_phrase: str,
        lab_name: Optional[str],
        lab_test_type_id: int,
        source: str,
        import_context: dict[str, Any],
        user_id: int,
    ) -> LabTestAlias:
        key = normalize_alias_key(raw_phrase)
        if not key:
            raise ValueError("Alias phrase is required")
        scope = lab_name.strip() if lab_name and lab_name.strip() else None
        now = datetime.utcnow()
        alias = (
            db.query(LabTestAlias)
            .filter(
                LabTestAlias.normalized_key == key,
                LabTestAlias.lab_test_type_id == lab_test_type_id,
                LabTestAlias.status == "pending",
                (
                    LabTestAlias.lab_name.is_(None)
                    if scope is None
                    else LabTestAlias.lab_name == scope
                ),
            )
            .first()
        )
        if alias:
            alias.suggestion_count += 1
            alias.raw_phrase = raw_phrase
        else:
            alias = LabTestAlias(
                raw_phrase=raw_phrase,
                normalized_key=key,
                lab_name=scope,
                lab_test_type_id=lab_test_type_id,
                status="pending",
                source=source,
                suggestion_count=1,
                first_seen_at=now,
            )
            db.add(alias)
        alias.last_seen_at = now
        alias.last_result_import_id = import_context.get("result_import_id")
        alias.last_lot_id = import_context.get("lot_id")
        alias.last_filename = import_context.get("filename")
        alias.last_suggested_by_id = user_id
        db.flush()
        return alias

    def _audit_alias(
        self,
        db: Session,
        action: AuditAction,
        record_id: int,
        old_values: Optional[dict[str, Any]],
        new_values: Optional[dict[str, Any]],
        user_id: int,
        reason: str,
    ) -> None:
        AuditLog.log_change(
            session=db,
            table_name="lab_test_aliases",
            record_id=record_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            user=user_id,
            reason=reason,
        )
