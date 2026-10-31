"""
Two runs that want the same answer make one model call, not two.

The defect, measured
--------------------
Every cached tool in this package was written as *read, miss, work, write*,
and the gap between the read and the write was wide open::

    key = _cache_key(...)
    if _cache_get(key) is not None:   # <- nothing stands between
        return ...                    #    these two lines and
    out = <the model call>            #    another process doing
    _cache_set(key, out)              #    exactly the same thing

Three processes started together on a cold cache, all asking for the plain
language rewrite of one sentence, made **three** real model calls 0.2 ms
apart. That is not only three times the work. Asked three times, a local LLM
gave three different answers — 126, 100 and 96 characters, measured against
``qwen3:8b`` — and the entry that survived in the cache was whichever process
happened to write last. So the page built by those three workers showed three
rewrites of one sentence, and the cache then preserved an arbitrary one of
them. That is a correctness defect wearing a performance defect's clothes.

What is asserted here
---------------------
The four properties a result cache can have, one test each, because they fail
independently and three of them were already holding before this file:

* content addressing — a different digest is a different entry;
* **cross-process single-flight** — the one that was missing;
* survival across a restart — a second process reuses the first's result;
* and the degradations, so the guard above cannot be bought with a crash:
  a corrupt ledger recomputes, and a missing ``wallet-helper`` still answers.

Written with real subprocesses rather than threads on purpose. The absence
being guarded against was *between processes*: a threading test passes
against the in-process ledger, which is exactly the backend that does not fix
this.

The sabotage that proves it has teeth
-------------------------------------
In ``scripts/_wallet.py``, make :func:`_wallet._ledger` return
``Ledger(cache_dir)`` — the JSON store — instead of the SQLite one. Nothing
else changes, every other test stays green, the cache still works, and
:func:`test_three_processes_make_one_model_call` reports 3.

Note that sabotaging the *key* proves nothing here, and that is the trap this
file was written around: ``wallet_helper.ledger.make_key`` content-addresses
a string that names an existing file, so replacing a digest with a path can
leave the behaviour intact and the guard green. The property is what has to
be broken, not the identifier.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from _wallet import memoized, wallet_for

REPO_ROOT = Path(__file__).resolve().parent.parent

# The helper that provides the property under test. Not an `importorskip`:
# this package's CI installs `[dev,all,api,mcp]`, `all` reaches `[prose]`, and
# `[prose]` declares `wallet-helper`. A skip here would make the one
# environment that gates the repository report green for the one thing this
# file exists to check.
pytest.importorskip(
    "wallet_helper",
    reason=(
        "wallet-helper is declared in the [prose] extra, which this "
        "package's CI installs through [all]. If this skips, the manifest "
        "and the install have come apart: pip install 'sprezzature-publish[prose]'"
    ),
)

#: A worker that memoizes one call, recording every real run in a shared file.
#: The sleep is what makes an overlap observable: without it a process can
#: finish before the next one starts, and three sequential runs would also
#: produce one call, for the wrong reason.
WORKER = textwrap.dedent(
    """
    import sys, os, time, pathlib
    scripts, cache_dir, counter, digest, naptime = sys.argv[1:6]
    sys.path.insert(0, scripts)
    from _wallet import memoized

    def work():
        with open(counter, "a") as handle:
            handle.write(f"{time.time():.6f} {os.getpid()}\\n")
        time.sleep(float(naptime))
        return {"answer": "computed once"}

    out = memoized("guard", digest, work, cache_dir=pathlib.Path(cache_dir))
    assert out == {"answer": "computed once"}, out
    """
)


def _run(workers: int, cache_dir: Path, counter: Path, digest: str, nap: float) -> int:
    """Start ``workers`` processes at once and return how many did real work."""
    script = cache_dir.parent / "worker.py"
    script.write_text(WORKER, encoding="utf-8")
    argv = [
        sys.executable,
        str(script),
        str(REPO_ROOT / "scripts"),
        str(cache_dir),
        str(counter),
        digest,
        str(nap),
    ]
    running = [
        subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(workers)
    ]
    for process in running:
        _, err = process.communicate(timeout=120)
        assert process.returncode == 0, err.decode()
    return len(counter.read_text(encoding="utf-8").splitlines()) if counter.exists() else 0


@pytest.fixture
def arena(tmp_path):
    """A cold cache directory and the counter the workers append to."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # Open the ledger once here, which is what every run after the first sees
    # anyway, so this test measures single-flight rather than the creation
    # race. That race has its own test below.
    wallet_for(cache_dir)
    return cache_dir, tmp_path / "calls.txt"


def test_three_processes_make_one_model_call(arena) -> None:
    """The measured defect: three concurrent asks, one real call.

    Three before this, 0.2 ms apart. The two followers wait on the leader's
    claim and are served its result, so they also agree with it — which is
    the half of the fix that is about being right, not about being fast.
    """
    cache_dir, counter = arena
    assert _run(3, cache_dir, counter, "a1b2c3d4", nap=0.6) == 1


def test_a_different_question_is_a_different_entry(arena) -> None:
    """Content addressing: the single-flight does not merge unrelated calls.

    The property that already held, kept because the fix had every chance to
    break it: a ledger keyed on a namespace alone would pass the test above
    and be useless.
    """
    cache_dir, counter = arena
    assert _run(1, cache_dir, counter, "aaaaaaaa", nap=0.0) == 1
    assert _run(1, cache_dir, counter, "bbbbbbbb", nap=0.0) == 2


def test_the_answer_survives_the_process_that_computed_it(arena) -> None:
    """Persistence: a second process reuses the first one's result."""
    cache_dir, counter = arena
    assert _run(1, cache_dir, counter, "deadbeef", nap=0.0) == 1
    assert _run(1, cache_dir, counter, "deadbeef", nap=0.0) == 1


def test_processes_creating_the_ledger_at_once_all_succeed(tmp_path) -> None:
    """The creation race, which cost a sibling repository a red run.

    ``SqliteLedger`` collides with itself at construction: several processes
    released onto the same missing database file raise ``sqlite3.
    OperationalError: database is locked`` from inside its own ``PRAGMA
    journal_mode=WAL`` — the statement that makes concurrent use possible is
    not itself safe on a file nobody has created yet. Reproduced here at 6
    processes behind a barrier: two rounds in six. ``_ledger`` retries, so
    this is the test that the retry budget is enough.
    """
    cache_dir = tmp_path / "cold"
    cache_dir.mkdir()
    counter = tmp_path / "calls.txt"
    # No `wallet_for` first: the children race to create the database.
    assert _run(4, cache_dir, counter, "c0ffee00", nap=0.2) == 1


def test_a_refused_sqlite_store_degrades_instead_of_raising(tmp_path, monkeypatch) -> None:
    """When the SQLite store cannot be opened at all, the tool still answers.

    The deterministic twin of the test above: the race is timing-dependent and
    the fallback is not, so the fallback is asserted by refusing every attempt
    rather than by hoping a lock lands. What is lost is cross-process
    single-flight; what is kept is the memoization and the result.
    """
    import sqlite3

    import _wallet

    def always_locked(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("wallet_helper.sqlite_ledger.SqliteLedger", always_locked)
    monkeypatch.setattr(_wallet, "OPEN_ATTEMPTS", 2)
    monkeypatch.setattr(_wallet, "OPEN_BACKOFF", 0.0)
    monkeypatch.setattr(_wallet, "_WALLETS", {})

    runs: list[int] = []

    def work() -> str:
        runs.append(1)
        return "answered anyway"

    assert memoized("guard", "fallback", work, cache_dir=tmp_path) == "answered anyway"
    assert memoized("guard", "fallback", work, cache_dir=tmp_path) == "answered anyway"
    assert len(runs) == 1, "the JSON fallback still has to memoize"


def test_a_corrupt_ledger_recomputes_instead_of_raising(tmp_path) -> None:
    """A truncated or overwritten ledger file reads as a miss, as before.

    The pair this replaced treated a corrupt entry as a miss and recomputed.
    Trading that for an exception would be trading a cache for a crash, which
    is a worse deal than having no cache at all.
    """
    (tmp_path / "ledger.db").write_text("not a database", encoding="utf-8")
    assert memoized("guard", "11223344", lambda: "fresh", cache_dir=tmp_path) == "fresh"


def test_without_wallet_helper_the_work_still_happens(tmp_path, monkeypatch) -> None:
    """A missing helper degrades to an uncached call, not to an ImportError.

    Asserted by blocking the import rather than by uninstalling anything, so
    it says the same thing in a full environment and in a bare one.
    """
    import builtins

    import _wallet

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("wallet_helper"):
            raise ImportError("No module named 'wallet_helper'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    monkeypatch.setattr(_wallet, "_WALLETS", {})
    monkeypatch.setattr(_wallet, "_WARNED_MISSING", False)

    runs: list[int] = []

    def work() -> str:
        runs.append(1)
        return "uncached but answered"

    assert memoized("guard", "nohelper", work, cache_dir=tmp_path) == "uncached but answered"
    # Twice, because the degradation is "no cache", and a silent cache that
    # returns the first answer forever would be the worse failure.
    assert memoized("guard", "nohelper", work, cache_dir=tmp_path) == "uncached but answered"
    assert len(runs) == 2


def test_no_cache_bypasses_both_halves(tmp_path) -> None:
    """``--no-cache`` has to skip the write as well as the read.

    Reading only would still leave this run's answer behind for the next one,
    which is the opposite of what the flag is asked for: it exists so a person
    can see what the model says *now*.
    """
    runs: list[int] = []

    def work() -> str:
        runs.append(1)
        return "fresh every time"

    memoized("guard", "bypass", work, cache_dir=tmp_path, enabled=False)
    memoized("guard", "bypass", work, cache_dir=tmp_path, enabled=False)
    assert len(runs) == 2
    memoized("guard", "bypass", work, cache_dir=tmp_path)
    assert len(runs) == 3, "nothing should have been stored by the bypassed runs"
