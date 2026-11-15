import re
from collections import Counter


class CategoryMap:
    """Static mapping of source category names to our region and subject."""

    def __init__(self, cfg: dict, edition: str) -> None:
        rules = ((cfg.get("editions") or {}).get(edition) or {}).get("rules") or {}
        self.rules = {
            facet: [(value, re.compile(p)) for value, patterns in (values or {}).items() for p in patterns]
            for facet, values in rules.items()
        }
        self.domains: dict[str, dict] = cfg.get("domains") or {}

    def facets(self, domain: str, names: list[str]) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {facet: set() for facet in ("region", "subject")}
        overrides = self.domains.get(domain) or {}
        for name in names:
            if name in overrides:
                for facet, value in (overrides[name] or {}).items():
                    out[facet].add(value)
                continue
            low = name.strip().lower()
            for facet, rules in self.rules.items():
                match = next((value for value, pattern in rules if pattern.search(low)), None)
                if match:
                    out[facet].add(match)
        return out


def vote(
    members: list[tuple[int, float]], facets: dict[int, dict[str, set[str]]], facet: str
) -> tuple[str | None, int]:
    counts = Counter(v for aid, _ in members for v in facets[aid][facet])
    if not counts:
        return None, 0
    best = max(counts.values())
    tied = {v for v, n in counts.items() if n == best}
    # Ties go to the member closest to the centroid.
    for aid, _ in sorted(members, key=lambda m: -m[1]):
        hit = tied & facets[aid][facet]
        if hit:
            return min(hit), best
    return None, 0
