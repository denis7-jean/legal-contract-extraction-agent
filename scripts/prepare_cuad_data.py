"""
ETL script: pulls the CUAD legal contracts dataset from HuggingFace Hub
(theatticusproject/cuad-qa) and converts the first 20 contracts into a structured
evaluation dataset written to data/eval_dataset.json.

Input:  HuggingFace dataset "theatticusproject/cuad-qa", train split.
        Each row is a (contract, question) pair with fields id, title, context,
        question, and answers; rows are grouped by contract title before mapping
        so that all nine answers for a contract are aggregated first.
        Requires datasets==2.14.6. See pyproject.toml for pin rationale.
Output: data/eval_dataset.json — a JSON file following the EvalDataset Pydantic schema.

Nine CUAD questions mapped:
    1. "Parties"
    2. "Effective Date"
    3. "Expiration Date"
    4. "Governing Law"
    5. "Document Name"
    6. "Renewal Term"
    7. "Cap On Liability"
    8. "Termination For Convenience"
    9. "Most Favored Nation"
"""
# ETL version: 1.4.0 — update this when mapping logic changes.
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal, TypedDict, cast

from datasets import Dataset, DownloadMode, VerificationMode, load_dataset
from pydantic import BaseModel, ConfigDict, Field, ValidationError


# ---------------------------------------------------------------------------
# TypedDict helpers for raw CUAD dataset structures
# ---------------------------------------------------------------------------


class _AnswerEntry(TypedDict, total=False):
    """Raw Q&A entry for a single CUAD question (SQuAD-style)."""

    text: list[str]
    answer_start: list[int]


# ---------------------------------------------------------------------------
# Pydantic output models
# ---------------------------------------------------------------------------


class Party(BaseModel):
    """A named party in a legal contract with an inferred role."""

    model_config = ConfigDict(strict=True, frozen=True)

    name: str
    role: Literal[
        "buyer",
        "seller",
        "licensor",
        "licensee",
        "employer",
        "employee",
        "lender",
        "borrower",
        "lessor",
        "lessee",
        "unknown",
    ]


class ExtractedLegalEntities(BaseModel):
    """Structured legal entities extracted from a single contract."""

    model_config = ConfigDict(strict=True, frozen=True)

    document_name: str
    parties: list[Party] = Field(min_length=1)
    effective_date: str | None
    expiration_date: str | None
    governing_law: str | None
    agreement_type: str
    renewal_term: str | None
    limitation_of_liability: str | None
    termination_for_convenience: bool
    most_favored_nation: bool


class CUADEvalRecord(BaseModel):
    """A single evaluation record derived from one CUAD contract."""

    model_config = ConfigDict(strict=True, frozen=True)

    cuad_id: str
    raw_contract_text: str
    ground_truth: ExtractedLegalEntities
    cuad_question_answers: dict[str, str]
    source_dataset: str = "theatticusproject/cuad-qa"


class EvalDataset(BaseModel):
    """Top-level container for all CUAD evaluation records."""

    model_config = ConfigDict(strict=True, frozen=True)

    schema_version: str = "1.0.0"
    total_records: int
    records: list[CUADEvalRecord]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_QUESTION_KEYS: list[str] = [
    "Parties",
    "Effective Date",
    "Expiration Date",
    "Governing Law",
    "Document Name",
    "Renewal Term",
    "Cap On Liability",
    "Termination For Convenience",
    "Most Favored Nation",
]

_MAX_CONTRACTS: int = 20


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def _load_cuad_train() -> Dataset:
    """Load the CUAD train split, retrying with NO_CHECKS if FORCE_REDOWNLOAD fails.

    FORCE_REDOWNLOAD is the primary strategy and corrects corrupt/incomplete caches.
    NO_CHECKS is used only as a last resort and may expose incomplete data.

    Returns:
        The CUAD train Dataset (one row per contract-question pair).
    """
    try:
        result: Dataset = load_dataset(  # type: ignore[assignment]
            "theatticusproject/cuad-qa",
            split="train",
            download_mode=DownloadMode.FORCE_REDOWNLOAD,
        )
        return result
    except Exception as exc:
        print(
            f"[WARN] FORCE_REDOWNLOAD failed ({type(exc).__name__}): {exc}\n"
            "[WARN] Retrying with verification_mode=NO_CHECKS — data may be incomplete.",
            file=sys.stderr,
        )
    try:
        fallback: Dataset = load_dataset(  # type: ignore[assignment]
            "theatticusproject/cuad-qa",
            split="train",
            verification_mode=VerificationMode.NO_CHECKS,
        )
        return fallback
    except Exception as exc2:
        print(
            f"[ERROR] Both load attempts failed: {type(exc2).__name__}: {exc2}",
            file=sys.stderr,
        )
        sys.exit(1)


def _print_dataset_diagnostics(ds_train: Dataset) -> None:
    """Print a schema summary of the raw dataset to aid debugging.

    Args:
        ds_train: The loaded CUAD train Dataset.
    """
    print(f"  rows    : {len(ds_train)}")
    print(f"  columns : {ds_train.column_names}")
    if len(ds_train) > 0:
        first: dict[str, object] = dict(ds_train[0])  # type: ignore[arg-type]
        print(f"  title   : {first.get('title', 'N/A')!r}")
        print(f"  question: {first.get('question', 'N/A')!r}")
        answers_repr = repr(first.get("answers"))[:120]
        print(f"  answers : {answers_repr}")


# ---------------------------------------------------------------------------
# Question label extraction and row grouping
# ---------------------------------------------------------------------------


def _extract_question_label(question: str) -> str:
    """Map a raw CUAD question string to one of the nine target label keys.

    Handles three formats in priority order:
    1. Short label verbatim (e.g. "Parties").
    2. CUAD long format: '... related to "LABEL" that should be reviewed ...'.
    3. Generic fallback: first double-quoted substring that matches a known label.

    Args:
        question: A raw question string from the CUAD dataset row.

    Returns:
        The matched label from _QUESTION_KEYS, or the original question string.
    """
    if question in _QUESTION_KEYS:
        return question
    match = re.search(r'related to "([^"]+)"', question)
    if match and match.group(1) in _QUESTION_KEYS:
        return match.group(1)
    match = re.search(r'"([^"]+)"', question)
    if match and match.group(1) in _QUESTION_KEYS:
        return match.group(1)
    return question


def _group_by_contract(
    ds_train: Dataset, max_contracts: int
) -> dict[str, dict[str, object]]:
    """Group dataset rows by contract title, collecting per-question answers.

    Scans every row; accumulates answers only for the first max_contracts unique
    titles encountered. Rows for later contracts are skipped efficiently.

    Args:
        ds_train:      CUAD train Dataset — one row per (contract, question) pair.
        max_contracts: Maximum number of unique contracts to retain.

    Returns:
        Dict mapping contract title → merged dict containing:
          "_context" (str), "_title" (str), and one key per matched question label
          whose value is the raw _AnswerEntry for that question.
    """
    grouped: dict[str, dict[str, object]] = {}
    for row in ds_train:
        row_dict: dict[str, object] = dict(row)  # type: ignore[arg-type]
        title: str = str(row_dict.get("title", ""))
        if title not in grouped:
            if len(grouped) >= max_contracts:
                continue
            grouped[title] = {
                "_context": str(row_dict.get("context", "")),
                "_title": title,
            }
        label = _extract_question_label(str(row_dict.get("question", "")))
        if label in _QUESTION_KEYS:
            grouped[title][label] = row_dict.get(
                "answers", {"text": [], "answer_start": []}
            )
    return grouped


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _get_answer(answers: dict[str, _AnswerEntry], key: str) -> str | None:
    """Extract the first non-empty answer text for a CUAD question label.

    Args:
        answers: Answers dict keyed by question label (built from grouped rows).
        key:     The exact question label to look up.

    Returns:
        The first non-empty answer string, or None if absent or empty.
    """
    entry = answers.get(key)
    if entry is None:
        return None
    texts: list[str] = entry.get("text", [])
    if not texts:
        return None
    first = texts[0]
    return first if first else None


def _parse_parties(parties_answer: str | None) -> list[Party]:
    """Parse a raw parties string into a list of Party objects.

    Splits on comma, ' and ', and newline; strips whitespace; filters tokens
    shorter than 3 chars. Assigns role='unknown' (inference is out of scope).
    Falls back to Party(name='Unknown', role='unknown') if nothing parses.

    Args:
        parties_answer: Raw answer string from the "Parties" question, or None.

    Returns:
        A non-empty list of Party objects.
    """
    if not parties_answer:
        return [Party(name="Unknown", role="unknown")]
    normalised = parties_answer.replace(" and ", ",").replace("\n", ",")
    tokens = [t.strip() for t in normalised.split(",")]
    names = [t for t in tokens if len(t) >= 3]
    if not names:
        return [Party(name="Unknown", role="unknown")]
    return [Party(name=name, role="unknown") for name in names]


# ---------------------------------------------------------------------------
# Core mapping function
# ---------------------------------------------------------------------------


def map_cuad_example_to_record(example: dict[str, object], index: int) -> CUADEvalRecord:
    """Convert a grouped contract dict into a validated CUADEvalRecord.

    Args:
        example: Dict with keys "context" (str), "title" (str), and
                 "answers" (dict[str, _AnswerEntry] keyed by question label).
        index:   Zero-based contract position; used to form cuad_id.

    Returns:
        A fully validated CUADEvalRecord.
    """
    answers = cast(dict[str, _AnswerEntry], example["answers"])

    raw_contract_text: str = str(example["context"])[:8000]
    title_raw = example["title"]
    document_name: str = str(title_raw) if title_raw else f"Unknown Contract {index}"

    agreement_answer = _get_answer(answers, "Document Name")
    agreement_type: str = agreement_answer if agreement_answer else document_name

    parties = _parse_parties(_get_answer(answers, "Parties"))
    effective_date = _get_answer(answers, "Effective Date")
    expiration_date = _get_answer(answers, "Expiration Date")
    governing_law = _get_answer(answers, "Governing Law")
    renewal_term = _get_answer(answers, "Renewal Term")

    liability_raw = _get_answer(answers, "Cap On Liability")
    limitation_of_liability: str | None = liability_raw[:500] if liability_raw else None

    tfc_entry = answers.get("Termination For Convenience")
    tfc_texts: list[str] = tfc_entry.get("text", []) if tfc_entry else []
    termination_for_convenience: bool = bool(tfc_texts) and bool(tfc_texts[0])

    mfn_entry = answers.get("Most Favored Nation")
    mfn_texts: list[str] = mfn_entry.get("text", []) if mfn_entry else []
    most_favored_nation: bool = bool(mfn_texts) and bool(mfn_texts[0])

    cuad_question_answers: dict[str, str] = {
        key: (_get_answer(answers, key) or "") for key in _QUESTION_KEYS
    }

    ground_truth = ExtractedLegalEntities(
        document_name=document_name,
        parties=parties,
        effective_date=effective_date,
        expiration_date=expiration_date,
        governing_law=governing_law,
        agreement_type=agreement_type,
        renewal_term=renewal_term,
        limitation_of_liability=limitation_of_liability,
        termination_for_convenience=termination_for_convenience,
        most_favored_nation=most_favored_nation,
    )

    return CUADEvalRecord(
        cuad_id=f"contract_{index:04d}",
        raw_contract_text=raw_contract_text,
        ground_truth=ground_truth,
        cuad_question_answers=cuad_question_answers,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Load CUAD, group rows by contract, map the first 20, and write data/eval_dataset.json."""
    print("Loading CUAD dataset from HuggingFace Hub...")
    ds_train = _load_cuad_train()

    print("Dataset loaded — diagnostics:")
    _print_dataset_diagnostics(ds_train)

    print(f"Grouping rows by contract (scanning {len(ds_train)} rows)...")
    contracts = _group_by_contract(ds_train, _MAX_CONTRACTS)
    print(f"Processing {len(contracts)} contracts...")

    records: list[CUADEvalRecord] = []
    for i, (_, contract_data) in enumerate(contracts.items()):
        example: dict[str, object] = {
            "context": contract_data["_context"],
            "title": contract_data["_title"],
            "answers": {k: v for k, v in contract_data.items() if not k.startswith("_")},
        }
        try:
            record = map_cuad_example_to_record(example, i)
            records.append(record)
        except ValidationError as e:
            print(f"[WARN] Skipping contract_{i:04d}: {type(e).__name__}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] Skipping contract_{i:04d}: {type(e).__name__}: {e}", file=sys.stderr)

    eval_dataset = EvalDataset(
        schema_version="1.0.0",
        total_records=len(records),
        records=records,
    )

    try:
        EvalDataset.model_validate(eval_dataset.model_dump())
    except ValidationError as e:
        print(f"[ERROR] Final EvalDataset validation failed:\n{e}", file=sys.stderr)
        sys.exit(1)

    output_path = Path("data/eval_dataset.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(eval_dataset.model_dump_json(indent=2), encoding="utf-8")

    gl_count = sum(1 for r in records if r.ground_truth.governing_law)
    ed_count = sum(1 for r in records if r.ground_truth.effective_date)
    mfn_count = sum(1 for r in records if r.ground_truth.most_favored_nation)

    print(f"Done. Saved {len(records)} records to data/eval_dataset.json")
    print(f"Schema version: {eval_dataset.schema_version}")
    print(f"Records with governing_law: {gl_count}")
    print(f"Records with effective_date: {ed_count}")
    print(f"Records with MFN clause: {mfn_count}")


if __name__ == "__main__":
    main()
