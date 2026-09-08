"""Gate for P1-S2 — policy pack format and loader.

Packs are the citation backbone: an appeal argues from the payer's own published policy, so
a pack that cannot be attributed to a retrievable source and a named section is unusable.
These tests assert the schema refuses such packs at load time rather than letting them
surface as an uncitable appeal three phases later.
"""

import textwrap

import pytest
from pydantic import ValidationError

from attest.policies.loader import find_pack, list_packs, load_pack

pytestmark = pytest.mark.p1_s2

VALID = """
pack_id: test-pack
payer: TestPayer
plan: Commercial
service: rTMS for major depressive disorder
cpt_codes: ["90867", "90868"]
source_url: https://example.org/policy.pdf
source_title: Transcranial Magnetic Stimulation Policy
retrieved_date: 2026-09-08
pa_required: true
appeal_window_days: 180
appeal_window_source: Member handbook, appeals section.
criteria:
  - id: c-01
    text: Patient is 18 years of age or older.
    category: eligibility
    source_section: IV.A.1
  - id: c-02
    text: Patient has a confirmed diagnosis of severe major depressive disorder.
    category: diagnosis
    source_section: IV.A.2
"""


def write(tmp_path, body: str, name: str = "pack.yaml"):
    p = tmp_path / name
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_valid_pack_loads(tmp_path):
    pack = load_pack(write(tmp_path, VALID))
    assert pack.pack_id == "test-pack"
    assert pack.criterion_ids == ["c-01", "c-02"]
    assert pack.criterion("c-02").source_section == "IV.A.2"


def test_pack_requires_source_url(tmp_path):
    body = "\n".join(l for l in VALID.splitlines() if not l.startswith("source_url:"))
    with pytest.raises(ValidationError):
        load_pack(write(tmp_path, body))


def test_pack_rejects_duplicate_criterion_ids(tmp_path):
    with pytest.raises(ValidationError, match="duplicate criterion ids"):
        load_pack(write(tmp_path, VALID.replace("id: c-02", "id: c-01")))


def test_criterion_requires_source_section(tmp_path):
    body = "\n".join(l for l in VALID.splitlines() if "source_section: IV.A.2" not in l)
    with pytest.raises(ValidationError):
        load_pack(write(tmp_path, body))


def test_pack_rejects_non_https_source(tmp_path):
    with pytest.raises(ValidationError):
        load_pack(write(tmp_path, VALID.replace("https://", "http://")))


def test_pack_requires_at_least_one_criterion(tmp_path):
    body = VALID[: VALID.index("criteria:")] + "criteria: []\n"
    with pytest.raises(ValidationError):
        load_pack(write(tmp_path, body))


def test_pack_rejects_unknown_fields(tmp_path):
    """Guards against a stale or hand-edited pack silently carrying a field nothing reads."""
    with pytest.raises(ValidationError):
        load_pack(write(tmp_path, VALID + "\nconfidence: 0.9\n"))


def test_appeal_window_must_be_positive(tmp_path):
    with pytest.raises(ValidationError):
        load_pack(write(tmp_path, VALID.replace("appeal_window_days: 180", "appeal_window_days: 0")))


def test_list_packs_reads_a_directory(tmp_path):
    write(tmp_path, VALID, "a.yaml")
    write(tmp_path, VALID.replace("pack_id: test-pack", "pack_id: other-pack"), "b.yaml")
    assert [p.pack_id for p in list_packs(tmp_path)] == ["other-pack", "test-pack"]


def test_find_pack_returns_none_when_unmapped():
    """None is the honest answer for an unmapped CPT. P2-S2 turns it into UNKNOWN."""
    assert find_pack(cpt="00000", payer="NoSuchPayer") is None


def test_shipped_packs_all_load():
    """Whatever is in packs/ must be valid. Empty until P1-S3."""
    for pack in list_packs():
        assert pack.criteria
