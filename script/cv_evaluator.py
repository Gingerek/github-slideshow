#!/usr/bin/env python3
"""Simple CV evaluation tool based on a job offer.

The script compares the keywords present in a job offer against the
content of a CV/resume and returns a similarity score together with
matched and missing requirements. It is intentionally lightweight and
only depends on the Python standard library so it can be used without
additional setup.
"""

from __future__ import annotations

import argparse
import pathlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set

# The stop words list is deliberately a mix of English and Polish words because
# job offers and CVs often combine both languages. This helps the tool focus on
# actual requirements such as technologies or responsibilities instead of
# generic verbs.
STOP_WORDS: Set[str] = {
    "a",
    "aby",
    "and",
    "as",
    "at",
    "be",
    "being",
    "by",
    "czy",
    "dla",
    "do",
    "from",
    "i",
    "in",
    "is",
    "it",
    "jego",
    "jej",
    "jest",
    "na",
    "o",
    "of",
    "or",
    "our",
    "przez",
    "s",
    "się",
    "the",
    "to",
    "u",
    "was",
    "we",
    "with",
    "w",
    "you",
    "że",
}

TOKEN_RE = re.compile(r"[a-ząćęłńóśźż0-9\+#\-]+", re.IGNORECASE)


def tokenize(text: str) -> List[str]:
    """Return a list of lower-cased tokens contained in *text*."""

    return [token.lower() for token in TOKEN_RE.findall(text)]


def extract_keywords(tokens: Sequence[str], *, top_n: int) -> List[str]:
    """Extract the *top_n* most frequent keywords from *tokens*.

    The function filters out stop words and very short words to focus on
    meaningful requirements. The resulting list is sorted from most frequent to
    least frequent.
    """

    filtered = [t for t in tokens if len(t) > 2 and t not in STOP_WORDS]
    counter = Counter(filtered)
    return [token for token, _ in counter.most_common(top_n)]


@dataclass
class EvaluationResult:
    score: float
    offer_keywords: List[str]
    matched_keywords: List[str]
    missing_keywords: List[str]
    offer_path: pathlib.Path
    cv_path: pathlib.Path

    def as_report(self) -> str:
        lines = [
            f"Oferta: {self.offer_path}",
            f"CV: {self.cv_path}",
            f"Wynik dopasowania: {self.score:.1f}/100",
            "",
            f"Dopasowane słowa kluczowe ({len(self.matched_keywords)}/"
            f"{len(self.offer_keywords)}):",
            ", ".join(self.matched_keywords) or "(brak)",
            "",
            f"Brakujące słowa kluczowe ({len(self.missing_keywords)}):",
            ", ".join(self.missing_keywords) or "(brak)",
        ]
        return "\n".join(lines)


def evaluate_cv(
    offer_text: str,
    cv_text: str,
    *,
    top_n: int,
    extra_keywords: Iterable[str] | None = None,
) -> EvaluationResult:
    offer_tokens = tokenize(offer_text)
    cv_tokens = tokenize(cv_text)

    offer_keywords = extract_keywords(offer_tokens, top_n=top_n)
    if extra_keywords:
        offer_keywords = list(dict.fromkeys(list(extra_keywords) + offer_keywords))

    cv_counter = Counter(cv_tokens)
    cv_token_set = set(cv_counter)

    matched = [kw for kw in offer_keywords if kw in cv_token_set]
    missing = [kw for kw in offer_keywords if kw not in cv_token_set]

    if not offer_keywords:
        score = 0.0
    else:
        coverage = len(matched) / len(offer_keywords)
        density = (
            sum(cv_counter[kw] for kw in matched) / max(sum(cv_counter.values()), 1)
        )
        score = (coverage * 0.7 + density * 0.3) * 100

    return EvaluationResult(
        score=score,
        offer_keywords=offer_keywords,
        matched_keywords=matched,
        missing_keywords=missing,
        offer_path=pathlib.Path("offer"),  # placeholders replaced in main()
        cv_path=pathlib.Path("cv"),
    )


def load_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Retry with latin-1 which is often used for CVs exported from legacy tools.
        return path.read_text(encoding="latin-1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analizuje zgodność CV z ofertą pracy na podstawie słów kluczowych."
            " Im wyższy wynik, tym więcej wymagań z oferty znajduje się w CV."
        )
    )
    parser.add_argument(
        "offer",
        type=pathlib.Path,
        help="Ścieżka do pliku tekstowego z ofertą pracy.",
    )
    parser.add_argument(
        "cv",
        type=pathlib.Path,
        help="Ścieżka do pliku tekstowego z CV.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=40,
        help="Liczba najważniejszych słów kluczowych z oferty, które będą oceniane.",
    )
    parser.add_argument(
        "--extra-keyword",
        action="append",
        default=[],
        help=(
            "Dodatkowe słowo kluczowe, które zawsze powinno być oceniane. "
            "Argument można powtórzyć wielokrotnie."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Zwróć wynik w formacie JSON (przydatne do automatyzacji).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    offer_text = load_text(args.offer)
    cv_text = load_text(args.cv)

    result = evaluate_cv(
        offer_text,
        cv_text,
        top_n=max(args.top_n, 1),
        extra_keywords=args.extra_keyword,
    )
    result.offer_path = args.offer
    result.cv_path = args.cv

    if args.json:
        import json

        payload = {
            "offer": str(result.offer_path),
            "cv": str(result.cv_path),
            "score": round(result.score, 2),
            "offer_keywords": result.offer_keywords,
            "matched_keywords": result.matched_keywords,
            "missing_keywords": result.missing_keywords,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(result.as_report())


if __name__ == "__main__":
    main()
