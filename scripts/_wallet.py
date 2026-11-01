"""
_wallet
=======

One seam between this package's on-disk result caches and `wallet-helper`_,
the suite's memoization layer. It answers a single question — *has this
expensive call already been made, and is somebody making it right now?* — and
it answers the second half, which is the part the hand-rolled caches here
could not.

The defect this file exists for
-------------------------------
Every cached tool in this repository was written the same way, and the shape
was always this::

    key = _cache_key(...)          # a SHA-256 of what determines the result
    hit = _cache_get(key)          # read
    if hit is not None:
        return hit
    result = <minutes of model work>
    _cache_set(key, result)        # write

Read against the four properties a result cache can have, that shape holds
two of them and misses two. **Content addressing** holds: the key is a digest
of the bytes actually sent, so the same audio reached by a different path
hits and two different files never collide. **Survival across a restart**
holds: the entry is a file, so a second process reads what the first wrote.

**Cross-process single-flight does not hold, and its absence was measured
rather than assumed**: three processes started together on a cold cache, all
asking for the same entry, produced *three* real runs — 2.6 ms apart in
``sprezzature-audio``, 0.2 ms apart in ``sprezzature-publish`` — because the
gap between ``_cache_get`` returning ``None`` and ``_cache_set`` writing is
wide open and nothing stands in it. Three whisper loads for one file, or
three model answers to one prompt, and then two of the three results thrown
away. With the SQLite-backed ledger below, the same three processes produce
**one** run and two waiters.

For a local LLM that is not only wasted time. The same prompt asked twice
does not come back the same, so the two results thrown away were *different
answers to the same question*, and which one survives in the cache depends on
which process happened to write last.

**TTL and eviction** do not hold either, and that one is left alone on
purpose: the real caches on the author's machine hold four entries and 16 kB
after two weeks of use, so an unbounded store is a problem that has not
happened. What the substitution does add for free is a way to bound it from
outside when it ever does — ``wallet-helper evict --sqlite <path>`` — which a
directory of bare ``.txt`` and ``.json`` files did not offer.

The key is *not* substituted, and that is deliberate
----------------------------------------------------
:func:`wallet_helper.ledger.make_key` would happily build the key from the
raw arguments, and it is good at it. But it content-addresses any ``str``
that *happens to name an existing file*, which means a ``--goal`` string or a
model alias that collides with a filename in the working directory would
silently key on that file's bytes instead of its own text. The callers here
already have a digest they trust, computed from exactly the inputs that
affect their output and nothing else. So that digest is what travels, handed
over as **bytes** — a leaf ``make_key`` hashes as content and never
path-tests — and the identity of a cache entry is determined by the same
inputs as before this file existed.

Its own ledger file, never the shared one
-----------------------------------------
``wallet-helper``'s default store is shared across every package that uses
it, and ``max_entries`` evicts inside whatever database it is handed. A cap
set on the shared ledger would throw away other packages' entries. So the
ledger here lives at ``<the caller's cache dir>/ledger.db`` and is this
package's alone.

The creation race, reproduced — and then fixed upstream
------------------------------------------------------
:class:`~wallet_helper.sqlite_ledger.SqliteLedger` used to collide with itself
at construction: six processes released from a barrier onto the same missing
database file raised ``sqlite3.OperationalError: database is locked`` in
**two of six rounds**, from inside its own ``PRAGMA journal_mode=WAL`` — the
statement that makes concurrent use possible is itself not concurrency-safe on
a file nobody has created yet. SQLite answers a journal-mode change with
``SQLITE_BUSY`` *without consulting the busy handler*, so the connection's
timeout never covered it.

``wallet-helper`` **1.3.2** reads the mode before writing it, and this
package's floor now names 1.3.2, so that cause is out of reach here.

What the retry is for now
-------------------------
It stays, and the reason is narrower than the one that prompted it — which is
worth writing down, because a defence whose stated cause has been removed is a
defence the next reader deletes or, worse, keeps for the wrong reason.

The live branch is ``sqlite3.DatabaseError``: **a file that is not a
database**, which is a disk and not a release. A ledger truncated by a crash,
or a path that collided with something else, degrades immediately to the JSON
:class:`~wallet_helper.ledger.Ledger` instead of taking the whole command down
— and each repository holding this file has its own test for exactly that.
Trading a cache for a crash was the defect the pair this replaced had.

``OperationalError`` keeps its retry for genuine contention beyond the busy
timeout, which is far rarer and which no floor can rule out. The numbers are
unchanged: raising the floor changed what this code is *for*, not what it does.

.. _wallet-helper: https://github.com/warith-harchaoui/wallet-helper

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sqlite3
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: How many times :func:`_ledger` re-opens the SQLite store before giving up
#: on it. Six attempts with the backoff below span roughly 1.3 s in the worst
#: case, which was far longer than the creation race measured above lasted, and
#: far shorter than the work being guarded. Unchanged when the floor moved past
#: that race: a number nobody re-measured is a number to leave alone.
OPEN_ATTEMPTS: int = 6

#: First backoff step, in seconds; doubled each attempt and jittered, so two
#: processes that collided do not retry in lockstep and collide again.
OPEN_BACKOFF: float = 0.02

#: Open ledgers, keyed by the resolved cache directory. Opening a
#: :class:`~wallet_helper.sqlite_ledger.SqliteLedger` runs a ``PRAGMA`` and
#: three ``CREATE TABLE IF NOT EXISTS`` statements, so a tool that memoizes
#: several calls in one run should pay for that once. Keyed by path rather
#: than held as a single global because a test moves the cache directory per
#: case and has to get a ledger pointing at its own.
_WALLETS: dict[str, Any] = {}

#: Set once when ``wallet_helper`` turns out not to be installed, so a run
#: that memoizes repeatedly says so once instead of once per call.
_WARNED_MISSING: bool = False


def _payload(digest: str) -> dict[str, bytes]:
    """
    Wrap a caller's digest so it can only ever be keyed as content.

    Parameters
    ----------
    digest : str
        The hex digest the caller already computed, from exactly the inputs
        that affect its result.

    Returns
    -------
    dict
        A payload whose one leaf is ``bytes``.
        :func:`wallet_helper.ledger.make_key` hashes ``bytes`` as raw content
        and explicitly never treats them as a filesystem path, which is what
        keeps a digest that happens to match a filename from being replaced
        by that file's contents.

    Notes
    -----
    A non-hexadecimal digest is encoded as UTF-8 rather than rejected: this
    helper's contract is "whatever string identifies the call", and a caller
    that moves to a different digest alphabet should not get a crash before
    its work even starts.
    """
    try:
        raw = bytes.fromhex(digest)
    except ValueError:
        raw = digest.encode("utf-8")
    return {"digest": raw}


def _ledger(cache_dir: Path) -> Any:
    """
    Open this package's own result store under ``cache_dir``.

    Parameters
    ----------
    cache_dir : pathlib.Path
        Directory the calling tool already uses for its cache. The ledger is
        ``cache_dir / "ledger.db"``; the directory is created if missing.

    Returns
    -------
    wallet_helper.ledger.LedgerLike
        A :class:`~wallet_helper.sqlite_ledger.SqliteLedger` when it can be
        opened — the backend that gives cross-process single-flight, because
        it is the one with a claim table. Otherwise a JSON
        :class:`~wallet_helper.ledger.Ledger` over the same directory, which
        still memoizes and still survives a restart, and whose single-flight
        reaches only as far as the current process.

    Raises
    ------
    ImportError
        When ``wallet-helper`` is not installed. Callers reaching this through
        :func:`memoized` never see it.
    """
    from wallet_helper.ledger import Ledger
    from wallet_helper.sqlite_ledger import SqliteLedger

    cache_dir.mkdir(parents=True, exist_ok=True)
    db = cache_dir / "ledger.db"
    reason = f"stayed locked after {OPEN_ATTEMPTS} attempts"
    for attempt in range(OPEN_ATTEMPTS):
        try:
            return SqliteLedger(db)
        except sqlite3.OperationalError:
            # Genuine contention: another process holds the write lock past the
            # busy timeout. The WAL-pragma race that first prompted this is
            # fixed in wallet-helper 1.3.2, which the floor now names — see the
            # module docstring. Jittered, so the retry does not recreate the
            # collision it is recovering from.
            # (`OperationalError` first: it is a subclass of the clause below.)
            time.sleep(OPEN_BACKOFF * (2**attempt) * (0.5 + random.random()))
        except sqlite3.DatabaseError as exc:
            # A file that is not a database. The pair this replaced read a
            # corrupt entry as a miss and recomputed, and losing that would be
            # trading a cache for a crash — so corruption degrades instead,
            # immediately, because no number of retries repairs a bad file.
            reason = f"is not a usable database ({exc})"
            break
    sys.stderr.write(
        f"wallet: {db} {reason}; "
        "falling back to the JSON ledger (no cross-process single-flight).\n"
    )
    return Ledger(cache_dir)


def wallet_for(cache_dir: Path) -> Any:
    """
    The memoizing wallet for ``cache_dir``, opened once per directory.

    Parameters
    ----------
    cache_dir : pathlib.Path
        Directory the calling tool already uses for its cache.

    Returns
    -------
    wallet_helper.Wallet
        A wallet over this package's own ledger (see :func:`_ledger`).

    Raises
    ------
    ImportError
        When ``wallet-helper`` is not installed.
    """
    from wallet_helper import Wallet

    resolved = str(Path(cache_dir).resolve())
    wallet = _WALLETS.get(resolved)
    if wallet is None:
        wallet = Wallet(_ledger(Path(cache_dir)))
        _WALLETS[resolved] = wallet
    return wallet


def memoized(
    namespace: str,
    digest: str,
    compute: Callable[[], Any],
    *,
    cache_dir: Path,
    enabled: bool = True,
    ttl: float | None = None,
) -> Any:
    """
    Return a stored result for ``digest``, or run ``compute`` exactly once.

    The heavy call belongs **inside** ``compute``. A single-flight that does
    not enclose the work it is deduplicating has not deduplicated anything:
    the waiting is what makes the second caller cheap, and there is nothing to
    wait on if the leader has already returned.

    Parameters
    ----------
    namespace : str
        Scope for the entry, so two tools' digests cannot collide. Use the
        tool's own name, for example ``"captions"``.
    digest : str
        Hex digest of everything that affects the result, computed by the
        caller. Passed through unchanged (see :func:`_payload`).
    compute : callable
        Zero-argument callable doing the expensive work. Run at most once per
        digest, even when several processes ask at the same moment. A raising
        ``compute`` stores nothing and releases the claim, so the next caller
        retries rather than inheriting a failure.
    cache_dir : pathlib.Path
        Directory the calling tool already uses for its cache.
    enabled : bool, optional
        ``False`` bypasses the cache entirely — read *and* write — which is
        what the tools' ``--no-cache`` flag and ``SPREZZATURE_NO_CACHE`` mean.
        Defaults to ``True``.
    ttl : float, optional
        Seconds the entry stays fresh. ``None`` (default) means it never
        expires, which is what the hand-rolled caches did.

    Returns
    -------
    Any
        The stored result, or what ``compute`` returned. It makes a JSON round
        trip through the ledger, so it has to be JSON-serialisable: the
        callers here store a string or a list of dicts of numbers and strings.

    Notes
    -----
    When ``wallet-helper`` is missing the work still happens — once, with no
    cache and one message on stderr. That is a degradation and not a failure,
    because the package it belongs to declares the dependency in the extras
    whose tools reach this function; an install that has the tool but not the
    helper is a hand-assembled one.
    """
    global _WARNED_MISSING
    if not enabled:
        return compute()
    try:
        wallet = wallet_for(cache_dir)
    except ImportError as exc:
        if not _WARNED_MISSING:
            _WARNED_MISSING = True
            sys.stderr.write(
                f"wallet: {exc}; running uncached. "
                "Install wallet-helper to reuse this result and to stop "
                "parallel runs from doing it more than once.\n"
            )
        return compute()
    result, _hit = wallet.call(namespace, _payload(digest), compute, ttl=ttl)
    return result
