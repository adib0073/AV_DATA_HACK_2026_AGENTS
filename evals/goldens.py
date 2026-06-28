"""Golden dataset for the trip-planner agent.

An *agent* golden is more than (input, expected_output): it carries the task,
the tools we expect to be exercised, and metadata (difficulty, capability). Here
we keep it lightweight - input + expected tools + metadata - which is enough for
the trace-based Layer-1 metrics (TaskCompletion, StepEfficiency) and as a
reference for Layer-2 component metrics.

One case (Tokyo) is the seeded-regression trigger: with INJECT_REGRESSION=true
the flight agent picks the wrong tool *only* for that destination, so exactly
one golden fails.

Custom datasets: if ``GOLDENS_FILE`` (env) or ``evals/_active_goldens.json``
exists, it is loaded instead of the built-in set. That file is a JSON list of
``{"input": str, "destination"?: str, "difficulty"?: str, "expected_tools"?: [str]}``
- this is what the Eval Studio "upload golden data" feature writes.
"""

from __future__ import annotations

import json
import os
import pathlib

from deepeval.dataset import Golden

try:
    from deepeval.test_case import ToolCall  # type: ignore
except Exception:  # pragma: no cover
    ToolCall = None  # type: ignore


_PLAN_TOOLS = ["search_flights", "search_hotels", "search_activities"]
_BOOK_TOOLS = ["search_flights", "search_hotels", "book_flight", "book_hotel"]

# (input, expected_tools, difficulty, destination)
RAW = [
    ("Plan a 5-day relaxing trip to Bali for 2 from Mumbai in October, budget $2500 total.", _PLAN_TOOLS, "easy", "Bali"),
    ("I want an explorer trip to Rome for 4 days, 1 traveler, flying from London, budget 1200 GBP.", _PLAN_TOOLS, "easy", "Rome"),
    ("Plan a leisure week in Paris for a couple from New York, mid budget.", _PLAN_TOOLS, "easy", "Paris"),
    ("Family trip to Singapore, 6 days, 2 adults 2 kids, from Delhi, flights budget $1800.", _PLAN_TOOLS, "medium", "Singapore"),
    ("Adventure trip to Queenstown for 5 days from Sydney, solo, budget AUD 2000.", _PLAN_TOOLS, "medium", "Queenstown"),
    ("Relaxing 4-night Maldives getaway for 2 from Bengaluru, hotel budget $200/night.", _PLAN_TOOLS, "medium", "Maldives"),
    ("Business trip to Frankfurt, 3 days, 1 traveler from Mumbai, need central hotel.", _PLAN_TOOLS, "easy", "Frankfurt"),
    ("Explorer trip to Istanbul, 5 days, 2 travelers from Dubai, total budget $1500.", _PLAN_TOOLS, "easy", "Istanbul"),
    ("Plan a 7-day leisure trip to Barcelona for 3 from Berlin.", _PLAN_TOOLS, "easy", "Barcelona"),
    ("Relaxing beach trip to Goa, 4 days, 2 people from Pune, budget 40000 INR.", _PLAN_TOOLS, "easy", "Goa"),
    ("Adventure trip to Reykjavik for 6 days from Boston, 2 travelers, mid-high budget.", _PLAN_TOOLS, "medium", "Reykjavik"),
    ("Family trip to Orlando for 5 days from Chicago, 2 adults 2 kids.", _PLAN_TOOLS, "medium", "Orlando"),
    ("Explorer trip to Cairo, 4 days, solo from Athens, budget $900 total.", _PLAN_TOOLS, "medium", "Cairo"),
    ("Leisure trip to Lisbon for 5 days, couple from Madrid.", _PLAN_TOOLS, "easy", "Lisbon"),
    # --- the seeded regression trigger ---
    ("Plan an explorer trip to Tokyo for 5 days, 2 travelers from Mumbai, budget $3000 total.", _PLAN_TOOLS, "trigger", "Tokyo"),
    # --- booking trips (end-to-end incl. reservation) ---
    ("Book a relaxing 3-night trip to Phuket for 2 from Chennai, budget $1500, go ahead and reserve.", _BOOK_TOOLS, "medium", "Phuket"),
    ("Plan and book a 4-day leisure trip to Dubai for 2 from Mumbai, budget $2200. Book it.", _BOOK_TOOLS, "medium", "Dubai"),
    ("Book my business trip to Zurich, 2 days, 1 traveler from London, central hotel, confirm now.", _BOOK_TOOLS, "medium", "Zurich"),
    # --- harder / ambiguous ---
    ("Weekend getaway somewhere relaxing near the beach from Mumbai for 2, budget $800.", _PLAN_TOOLS, "hard", "unspecified"),
    ("Surprise me with a 5-day explorer trip in Europe for 1 from Delhi, budget $2000.", _PLAN_TOOLS, "hard", "unspecified"),
]


def data_dir() -> pathlib.Path:
    """Directory for runtime-persisted files (mounted as a Docker volume so eval
    history / uploaded goldens survive container recreation)."""
    d = pathlib.Path(os.getenv("EVAL_DATA_DIR") or pathlib.Path(__file__).resolve().parents[1] / ".data")
    d.mkdir(parents=True, exist_ok=True)
    return d


def active_goldens_path() -> pathlib.Path:
    """Where an uploaded/custom dataset lives (env override wins)."""
    env = os.getenv("GOLDENS_FILE")
    if env:
        return pathlib.Path(env)
    return data_dir() / "_active_goldens.json"


def _raw_dicts() -> list[dict]:
    return [
        {"input": text, "expected_tools": list(tools), "difficulty": diff, "destination": dest}
        for text, tools, diff, dest in RAW
    ]


def _coerce_item(item: dict) -> dict:
    """Normalize one uploaded golden into our canonical dict shape."""
    text = (item.get("input") or item.get("query") or item.get("text") or "").strip()
    tools = item.get("expected_tools") or item.get("tools") or _PLAN_TOOLS
    if isinstance(tools, str):
        tools = [t.strip() for t in tools.split(",") if t.strip()]
    return {
        "input": text,
        "expected_tools": list(tools),
        "difficulty": item.get("difficulty", "custom"),
        "destination": item.get("destination", "") or "",
    }


def get_golden_dicts() -> list[dict]:
    """Plain-dict view of the active dataset (no deepeval types needed)."""
    path = active_goldens_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data.get("goldens", data) if isinstance(data, dict) else data
            cleaned = [_coerce_item(it) for it in items if isinstance(it, dict)]
            cleaned = [c for c in cleaned if c["input"]]
            if cleaned:
                return cleaned
        except Exception:
            pass
    return _raw_dicts()


def is_custom() -> bool:
    return active_goldens_path().exists()


def save_custom(items: list[dict]) -> int:
    """Persist an uploaded dataset; returns the number of goldens stored."""
    cleaned = [_coerce_item(it) for it in items if isinstance(it, dict)]
    cleaned = [c for c in cleaned if c["input"]]
    path = active_goldens_path()
    path.write_text(json.dumps({"goldens": cleaned}, indent=2), encoding="utf-8")
    return len(cleaned)


def reset_custom() -> None:
    path = active_goldens_path()
    if path.exists():
        path.unlink()


def _tools(names) -> list | None:
    if ToolCall is None:
        return None
    return [ToolCall(name=n) for n in names]


def get_goldens() -> list[Golden]:
    """deepeval Golden objects built from the active dataset."""
    goldens: list[Golden] = []
    for item in get_golden_dicts():
        kwargs: dict = {
            "input": item["input"],
            "additional_metadata": {
                "difficulty": item.get("difficulty", "custom"),
                "destination": item.get("destination", ""),
            },
        }
        et = _tools(item.get("expected_tools") or [])
        if et is not None:
            kwargs["expected_tools"] = et
        try:
            goldens.append(Golden(**kwargs))
        except TypeError:
            goldens.append(Golden(input=item["input"]))
    return goldens


if __name__ == "__main__":
    gs = get_golden_dicts()
    print(f"{len(gs)} goldens ({'custom' if is_custom() else 'built-in'})")
    for g in gs:
        print(" -", g["destination"], "|", g["input"][:60])
