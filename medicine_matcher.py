import json
from rapidfuzz import process, fuzz, utils


def load_drug_names(filepath):
    """Load the drug names database from JSON."""
    with open(filepath, "r") as f:
        return json.load(f)


def load_inventory(filepath):
    """Load the pharmacy inventory from JSON."""
    with open(filepath, "r") as f:
        return json.load(f)


def match_medicines(candidates, drug_names, inventory, score_threshold=65, limit=3):
    """
    For each candidate string, find the best fuzzy match in drug_names.

    Returns a list of dicts with: raw_text, matched_name, confidence,
    in_stock, stock_count, alternatives.
    """
    results = []
    seen = set()

    for candidate in candidates:
        matches = process.extract(
            query=candidate,
            choices=drug_names,
            scorer=fuzz.WRatio,
            limit=limit,
            processor=utils.default_process,
            score_cutoff=score_threshold,
        )

        if not matches:
            results.append({
                "raw_text": candidate,
                "matched_name": None,
                "confidence": 0,
                "in_stock": False,
                "stock_count": 0,
                "alternatives": [],
            })
            continue

        best_name = matches[0][0]
        best_score = matches[0][1]

        # Deduplicate
        if best_name.lower() in seen:
            continue
        seen.add(best_name.lower())

        # Check inventory
        inv_key = best_name.lower()
        inv_entry = inventory.get(inv_key, {})
        in_stock = inv_entry.get("quantity", 0) > 0
        stock_count = inv_entry.get("quantity", 0)

        alternatives = [
            {"name": m[0], "score": round(m[1], 1)}
            for m in matches[1:]
        ]

        results.append({
            "raw_text": candidate,
            "matched_name": best_name,
            "confidence": round(best_score, 1),
            "in_stock": in_stock,
            "stock_count": stock_count,
            "alternatives": alternatives,
        })

    return results
