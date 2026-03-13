from __future__ import annotations


def _is_word_boundary(text: str, i: int) -> bool:
    if i == 0:
        return True
    prev = text[i - 1]
    curr = text[i]
    return prev in " _/-." or (prev.islower() and curr.isupper())


def fuzzy_match(query: str, text: str) -> tuple[int, list[int]]:
    if not query:
        return 1, []
    lower_query = query.lower()
    lower_text = text.lower()
    positions: list[int] = []
    score = 0
    qi = 0
    prev_match_idx = -2
    for ti in range(len(lower_text)):
        if qi < len(lower_query) and lower_text[ti] == lower_query[qi]:
            positions.append(ti)
            score += 1
            if _is_word_boundary(lower_text, ti):
                score += 5
            if ti == prev_match_idx + 1:
                score += 3
            if ti == qi:
                score += 2
            prev_match_idx = ti
            qi += 1
    if qi < len(lower_query):
        return 0, []
    if len(positions) == len(lower_text):
        score += 10
    return score, positions


def fuzzy_score(query: str, text: str) -> int:
    score, _ = fuzzy_match(query, text)
    return score
