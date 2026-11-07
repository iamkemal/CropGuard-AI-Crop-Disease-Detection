"""Transparent symptom-based inference over the stored IF-THEN rules."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable, Literal


Outcome = Literal["matched", "no_match", "insufficient_evidence"]
ConfidenceLevel = Literal["none", "low", "moderate", "high"]


@dataclass(frozen=True)
class SymptomEvidence:
    """Identify one selected or required symptom and its display label."""
    slug: str
    label: str


# Flat records keep rule evidence explicit rather than hiding related fields.
@dataclass(frozen=True)
class RuleEvidence:  # pylint: disable=too-many-instance-attributes
    """Describe a rule, its matched evidence, and its qualification thresholds."""
    disease_id: int
    disease_slug: str
    disease_name: str
    code: str
    name: str
    description: str
    matched_symptoms: tuple[SymptomEvidence, ...]
    missing_required_symptoms: tuple[SymptomEvidence, ...]
    minimum_matches: int
    minimum_score: float
    match_score: float
    qualified: bool


@dataclass(frozen=True)
class DiseaseCandidate:
    """Collect the qualified rule evidence supporting a ranked disease candidate."""
    disease_id: int
    slug: str
    name: str
    match_score: float
    confidence_level: Literal["low", "moderate", "high"]
    matched_symptoms: tuple[SymptomEvidence, ...]
    matched_rules: tuple[RuleEvidence, ...]


# Flat records keep rule evidence explicit rather than hiding related fields.
@dataclass(frozen=True)
class InferenceResult:  # pylint: disable=too-many-instance-attributes
    """Return the diagnosis outcome, ranked candidates, and supporting explanation."""
    outcome: Outcome
    crop_slug: str
    crop_name: str
    selected_symptoms: tuple[SymptomEvidence, ...]
    candidates: tuple[DiseaseCandidate, ...]
    rule_evidence: tuple[RuleEvidence, ...]
    confidence_level: ConfidenceLevel
    explanation: str


@dataclass(frozen=True)
class _Condition:
    symptom: SymptomEvidence
    condition_type: str
    weight: float


# Flat records keep rule evidence explicit rather than hiding related fields.
@dataclass
class _RuleBuilder:  # pylint: disable=too-many-instance-attributes
    rule_id: int
    code: str
    name: str
    description: str
    minimum_matches: int
    minimum_score: float
    priority: int
    disease_id: int
    disease_slug: str
    disease_name: str
    conditions: list[_Condition]


# Flat records keep rule evidence explicit rather than hiding related fields.
@dataclass(frozen=True)
class _Rule:  # pylint: disable=too-many-instance-attributes
    code: str
    name: str
    description: str
    minimum_matches: int
    minimum_score: float
    priority: int
    disease_id: int
    disease_slug: str
    disease_name: str
    conditions: tuple[_Condition, ...]


def _confidence_for(score: float, matched_symptom_count: int) -> Literal[
    "low", "moderate", "high"
]:
    if score >= 0.8 and matched_symptom_count >= 3:
        return "high"
    if score >= 0.5 and matched_symptom_count >= 2:
        return "moderate"
    return "low"


def _load_rules(connection: sqlite3.Connection, crop_id: int) -> tuple[_Rule, ...]:
    rows = connection.execute(
        """
        SELECT r.id, r.code, r.name, r.description, r.minimum_matches,
               r.minimum_score, r.priority, d.id, d.slug, d.name,
               s.slug, s.label, rc.condition_type, rc.weight
        FROM rules AS r
        JOIN diseases AS d ON d.id = r.disease_id
        JOIN rule_conditions AS rc ON rc.rule_id = r.id
        JOIN symptoms AS s ON s.id = rc.symptom_id
        WHERE d.crop_id = ? AND d.is_active = 1 AND r.is_active = 1
              AND s.is_active = 1
        ORDER BY r.priority, r.code, rc.id
        """,
        (crop_id,),
    ).fetchall()

    builders: dict[int, _RuleBuilder] = {}
    for row in rows:
        rule_id = int(row[0])
        builder = builders.get(rule_id)
        if builder is None:
            builder = _RuleBuilder(
                rule_id=rule_id,
                code=str(row[1]),
                name=str(row[2]),
                description=str(row[3]),
                minimum_matches=int(row[4]),
                minimum_score=float(row[5]),
                priority=int(row[6]),
                disease_id=int(row[7]),
                disease_slug=str(row[8]),
                disease_name=str(row[9]),
                conditions=[],
            )
            builders[rule_id] = builder
        builder.conditions.append(
            _Condition(
                symptom=SymptomEvidence(str(row[10]), str(row[11])),
                condition_type=str(row[12]),
                weight=float(row[13]),
            )
        )

    return tuple(
        _Rule(
            code=builder.code,
            name=builder.name,
            description=builder.description,
            minimum_matches=builder.minimum_matches,
            minimum_score=builder.minimum_score,
            priority=builder.priority,
            disease_id=builder.disease_id,
            disease_slug=builder.disease_slug,
            disease_name=builder.disease_name,
            conditions=tuple(builder.conditions),
        )
        for builder in builders.values()
    )


def _evaluate_rule(rule: _Rule, selected_slugs: set[str]) -> RuleEvidence:
    matched_conditions = tuple(
        condition
        for condition in rule.conditions
        if condition.symptom.slug in selected_slugs
    )
    matched_symptoms = tuple(
        condition.symptom for condition in matched_conditions
    )
    missing_required = tuple(
        condition.symptom
        for condition in rule.conditions
        if condition.condition_type == "required"
        and condition.symptom.slug not in selected_slugs
    )
    total_weight = sum(condition.weight for condition in rule.conditions)
    matched_weight = sum(condition.weight for condition in matched_conditions)
    score = round(matched_weight / total_weight, 4) if total_weight else 0.0
    qualified = (
        not missing_required
        and len(matched_conditions) >= rule.minimum_matches
        and score >= rule.minimum_score
    )
    return RuleEvidence(
        disease_id=rule.disease_id,
        disease_slug=rule.disease_slug,
        disease_name=rule.disease_name,
        code=rule.code,
        name=rule.name,
        description=rule.description,
        matched_symptoms=matched_symptoms,
        missing_required_symptoms=missing_required,
        minimum_matches=rule.minimum_matches,
        minimum_score=rule.minimum_score,
        match_score=score,
        qualified=qualified,
    )


def _build_candidates(
    qualified_evidence: tuple[RuleEvidence, ...],
    rule_priority: dict[str, int],
) -> tuple[DiseaseCandidate, ...]:
    evidence_by_disease: dict[int, list[RuleEvidence]] = {}
    for evidence in qualified_evidence:
        evidence_by_disease.setdefault(evidence.disease_id, []).append(evidence)

    candidates: list[DiseaseCandidate] = []
    for disease_evidence in evidence_by_disease.values():
        first = disease_evidence[0]
        matched_by_slug: dict[str, SymptomEvidence] = {}
        for evidence in disease_evidence:
            for symptom in evidence.matched_symptoms:
                matched_by_slug[symptom.slug] = symptom
        matched_symptoms = tuple(matched_by_slug.values())
        score = max(evidence.match_score for evidence in disease_evidence)
        candidates.append(
            DiseaseCandidate(
                disease_id=first.disease_id,
                slug=first.disease_slug,
                name=first.disease_name,
                match_score=score,
                confidence_level=_confidence_for(score, len(matched_symptoms)),
                matched_symptoms=matched_symptoms,
                matched_rules=tuple(disease_evidence),
            )
        )

    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -candidate.match_score,
                -len(candidate.matched_symptoms),
                min(rule_priority[rule.code] for rule in candidate.matched_rules),
                candidate.name.casefold(),
            ),
        )
    )


def _load_selected_symptoms(
    connection: sqlite3.Connection,
    crop_id: int,
    crop_slug: str,
    selected_slugs: tuple[str, ...],
) -> tuple[SymptomEvidence, ...]:
    """Validate selected slugs against the active symptoms of the chosen crop."""
    symptom_rows = connection.execute(
        """
        SELECT slug, label
        FROM symptoms
        WHERE crop_id = ? AND is_active = 1
        ORDER BY label COLLATE NOCASE
        """,
        (crop_id,),
    ).fetchall()
    symptoms_by_slug = {
        str(row[0]): SymptomEvidence(str(row[0]), str(row[1]))
        for row in symptom_rows
    }
    unknown_slugs = sorted(set(selected_slugs) - symptoms_by_slug.keys())
    if unknown_slugs:
        raise ValueError(
            f"Symptoms are unknown or do not belong to {crop_slug}: "
            + ", ".join(unknown_slugs)
        )

    return tuple(
        symptoms_by_slug[slug] for slug in selected_slugs
    )


def _matched_explanation(candidates: tuple[DiseaseCandidate, ...]) -> str:
    """Explain leading candidates without treating rule scores as probabilities."""
    top_score = candidates[0].match_score
    if len(candidates) > 1 and top_score - candidates[1].match_score <= 0.1:
        names = ", ".join(candidate.name for candidate in candidates)
        explanation = (
            "Several diseases have similarly strong matching rule evidence: "
            f"{names}. These are possible causes, not confirmed diagnoses; "
            "seek local agricultural advice if the problem persists."
        )
    elif len(candidates) > 1:
        explanation = (
            f"{candidates[0].name} has the strongest matching rule evidence, "
            "but other diseases also matched. Treat the results as possibilities, "
            "not as a confirmed diagnosis."
        )
    else:
        explanation = (
            f"The stored rule evidence most strongly supports {candidates[0].name} "
            f"(weighted rule-match score {top_score:.0%}). This is a possible "
            "diagnosis, not confirmation."
        )
    return explanation


def _unmatched_explanation(
    selected_slugs: tuple[str, ...],
    activated_evidence: tuple[RuleEvidence, ...],
) -> str:
    """Explain missing evidence or the absence of any matching stored rule."""
    if not selected_slugs:
        explanation = (
            "No symptoms were selected, so there is not enough evidence to evaluate "
            "the disease rules."
        )
    elif activated_evidence:
        closest = activated_evidence[0]
        missing_labels = ", ".join(
            symptom.label for symptom in closest.missing_required_symptoms
        )
        details = (
            f" The closest rule was {closest.name} "
            f"({closest.match_score:.0%} weighted match)."
        )
        if missing_labels:
            details += f" It still requires: {missing_labels}."
        if len(closest.matched_symptoms) < closest.minimum_matches:
            details += (
                f" It needs at least {closest.minimum_matches} matched symptoms."
            )
        explanation = (
            "Some selected symptoms overlap with stored rules, but no rule met all "
            "required conditions and evidence thresholds."
            + details
        )
    else:
        explanation = (
            "No stored IF-THEN rule matched the selected symptoms. The symptoms may "
            "have another cause or need assessment by a local agricultural adviser."
        )
    return explanation


def infer_disease(
    connection: sqlite3.Connection,
    crop_slug: str,
    observed_symptom_slugs: Iterable[str],
) -> InferenceResult:
    """Evaluate active rules for one crop; uploaded images are not accepted or read."""
    if not isinstance(crop_slug, str) or not crop_slug.strip():
        raise ValueError("A crop slug is required.")

    supplied_symptoms = tuple(observed_symptom_slugs)
    if any(not isinstance(slug, str) or not slug.strip() for slug in supplied_symptoms):
        raise ValueError("Every selected symptom must have a non-empty slug.")
    selected_slugs = tuple(dict.fromkeys(supplied_symptoms))

    crop = connection.execute(
        "SELECT id, slug, name FROM crops WHERE slug = ? AND is_active = 1",
        (crop_slug,),
    ).fetchone()
    if crop is None:
        raise LookupError(f"Unknown or inactive crop: {crop_slug}")

    selected_symptoms = _load_selected_symptoms(
        connection, int(crop[0]), crop_slug, selected_slugs
    )
    rules = _load_rules(connection, int(crop[0]))
    evaluated = tuple(
        _evaluate_rule(rule, set(selected_slugs)) for rule in rules
    )
    rule_priority = {rule.code: rule.priority for rule in rules}
    activated_evidence = tuple(
        sorted(
            (evidence for evidence in evaluated if evidence.matched_symptoms),
            key=lambda evidence: (
                -evidence.match_score,
                len(evidence.missing_required_symptoms),
                max(
                    0,
                    evidence.minimum_matches - len(evidence.matched_symptoms),
                ),
                rule_priority[evidence.code],
                evidence.code,
            ),
        )
    )
    qualified_evidence = tuple(
        evidence for evidence in activated_evidence if evidence.qualified
    )
    candidates = _build_candidates(qualified_evidence, rule_priority)
    crop_name = str(crop[2])

    if candidates:
        return InferenceResult(
            outcome="matched",
            crop_slug=str(crop[1]),
            crop_name=crop_name,
            selected_symptoms=selected_symptoms,
            candidates=candidates,
            rule_evidence=activated_evidence,
            confidence_level=candidates[0].confidence_level,
            explanation=_matched_explanation(candidates),
        )

    return InferenceResult(
        outcome="insufficient_evidence" if activated_evidence or not selected_slugs else "no_match",
        crop_slug=str(crop[1]),
        crop_name=crop_name,
        selected_symptoms=selected_symptoms,
        candidates=(),
        rule_evidence=activated_evidence,
        confidence_level="none",
        explanation=_unmatched_explanation(selected_slugs, activated_evidence),
    )
