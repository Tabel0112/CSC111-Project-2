"""Country-name matching and autocorrect helpers."""

from __future__ import annotations


def dp(a: str, b: str) -> int:
    """Return the Levenshtein edit distance between strings a and b."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    if len(a) < len(b):
        a, b = b, a

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i]
        for j, char_b in enumerate(b, start=1):
            insertion = current_row[j - 1] + 1
            deletion = previous_row[j] + 1
            substitution = previous_row[j - 1]
            if char_a != char_b:
                substitution += 1
            current_row.append(min(insertion, deletion, substitution))
        previous_row = current_row

    return previous_row[-1]


def suggest_closest_command(user_input: str, candidates: list[str]) -> str | None:
    """Return the closest candidate, using edit distance plus prefix/substring boosts."""
    normalized_input = user_input.lower().strip()
    if normalized_input == "" or not candidates:
        return None

    best_command = None
    best_score = -1.0

    for candidate in candidates:
        normalized_candidate = candidate.lower().strip()
        distance = dp(normalized_input, normalized_candidate)
        max_len = max(len(normalized_input), len(normalized_candidate))
        score = 1.0
        if max_len != 0:
            score -= distance / max_len

        if normalized_candidate.startswith(normalized_input):
            score += 0.45
        elif normalized_input in normalized_candidate:
            score += 0.20

        if score > best_score:
            best_score = score
            best_command = candidate

    return best_command


def _normalize_country_lookup_key(value: str) -> str:
    """Return a simplified lookup key for country names and codes."""
    return "".join(character for character in value.lower() if character.isalnum())


def _build_country_name_lookup(countries: dict[str, object]) -> dict[str, str]:
    """Return a lookup from country names/codes to ISO-3 codes."""
    lookup = {}
    for code, country in countries.items():
        lookup[_normalize_country_lookup_key(code)] = code
        country_name = getattr(country, "name", code)
        lookup[_normalize_country_lookup_key(str(country_name))] = code
    return lookup


def resolve_country_input(
    user_input: str,
    countries: dict[str, object],
) -> tuple[str | None, str | None]:
    """Resolve a typed country name or code into an ISO-3 code and optional suggestion."""
    normalized_input = _normalize_country_lookup_key(user_input)
    if normalized_input == "":
        return None, None

    lookup = _build_country_name_lookup(countries)
    if normalized_input in lookup:
        return lookup[normalized_input], None

    candidate_names = sorted({str(getattr(country, "name", code)) for code, country in countries.items()})
    suggestion = suggest_closest_command(user_input, candidate_names)
    if suggestion is None:
        return None, None

    normalized_suggestion = _normalize_country_lookup_key(suggestion)
    max_len = max(len(normalized_input), len(normalized_suggestion))
    distance = dp(normalized_input, normalized_suggestion)
    if max_len == 0 or distance > max(2, max_len // 3):
        return None, None

    suggested_code = lookup.get(_normalize_country_lookup_key(suggestion))
    return suggested_code, suggestion
