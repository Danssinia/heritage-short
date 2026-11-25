"""Fast offline tests: schema rules, cache behaviour, timeline and subtitles. Run: make test"""
import copy
import json
import os

import pytest

os.environ["HERITAGE_MOCK"] = "1"

from pipeline import subtitles  # noqa: E402
from pipeline.common import story  # noqa: E402
from pipeline.common.cache import Manifest, stable_hash  # noqa: E402
from pipeline.validate import semantic_errors, validate  # noqa: E402
from pipeline.common.config import ROOT  # noqa: E402


@pytest.fixture()
def sb():
    return json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))


def write(tmp_path, data):
    p = tmp_path / "sb.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_storyboard_is_valid():
    validate()


@pytest.mark.parametrize("mutate, message", [
    (lambda s: s["characters"][0].pop("consent_ref"), "consent_ref"),
    (lambda s: s["end_card"].update(text="The end"), "end_card"),
    (lambda s: s["shots"][2].update(location="market"), "unknown location"),
    (lambda s: [x.update(duration_s=12) for x in s["shots"]], "planned runtime"),
    (lambda s: s["shots"][0]["motion"].pop("seed"), "seed"),
    (lambda s: s["shots"][7]["narration"]["lines"][1].update(speaker="uncle"), "has no voice"),
    (lambda s: s.update(exports=[s["exports"][0]]), "exports"),
])
def test_broken_storyboards_are_rejected(tmp_path, sb, mutate, message):
    bad = copy.deepcopy(sb)
    mutate(bad)
    with pytest.raises(SystemExit) as e:
        validate(write(tmp_path, bad))
    assert message in str(e.value)


def test_hash_is_stable_and_order_independent():
    assert stable_hash({"a": 1, "b": [1, 2]}) == stable_hash({"b": [1, 2], "a": 1})
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


def test_manifest_detects_change(tmp_path):
    f = ROOT / "outputs_mock" / "_test_artifact.txt"
    f.parent.mkdir(exist_ok=True)
    f.write_text("x")
    m = Manifest(tmp_path / "manifest.json")
    m.put("k", "h1", [f])
    assert m.fresh("k", "h1")
    assert not m.fresh("k", "h2")
    f.unlink()
    assert not m.fresh("k", "h1")


def test_timeline_extends_shot_to_fit_speech(sb):
    timings = {"s03": {"total": 9.0, "lines": [{"start": 0.0, "end": 9.0}]}}
    t = story.timeline(sb, timings)
    s03 = next(s for s in t["shots"] if s["id"] == "s03")
    offset = sb["shots"][2]["narration"]["offset_s"]
    assert s03["duration"] == pytest.approx(offset + 9.0 + 0.6)
    assert s03["extended"]
    assert t["cues"][-1]["end"] == t["end_card"]["end"]


def test_only_changed_shot_changes_hash(sb):
    a = [story.keyframe_prompt(sb, s) for s in sb["shots"]]
    sb2 = copy.deepcopy(sb)
    sb2["shots"][4]["keyframe"]["prompt"] += " with a towel"
    b = [story.keyframe_prompt(sb2, s) for s in sb2["shots"]]
    assert [x != y for x, y in zip(a, b)] == [i == 4 for i in range(len(a))]


def test_subtitles_respect_line_limits(sb):
    t = story.timeline(sb, {s["id"]: {"total": 4.0, "lines": [{"start": 0, "end": 4.0}] * len(s["narration"]["lines"])}
                            for s in sb["shots"]})
    for a, b, lines in subtitles.cues(sb, t):
        assert b > a
        assert len(lines) <= sb["subtitles"]["max_lines"]
        assert all(len(line) <= sb["subtitles"]["max_chars_per_line"] for line in lines)


def test_wan_frame_count_is_4k_plus_1():
    for s in (2.0, 3.4, 5.0):
        assert (story.num_frames(s) - 1) % 4 == 0


def test_no_semantic_errors_in_sample(sb):
    assert semantic_errors(sb) == []
