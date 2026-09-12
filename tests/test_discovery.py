from __future__ import annotations

from pm import reference as ref
from pm.discovery import discover_directly_follows, dominant_edges, discovery_matches_documented_procedure


def test_directly_follows_miner_recovers_the_documented_procedure_exactly(con):
    edges = discover_directly_follows(con, min_support=5)
    discovered = dominant_edges(edges, dominance_threshold=0.9)
    documented = set(ref.ALLOWED_TRANSITIONS)

    exact, missing, extra = discovery_matches_documented_procedure(discovered, documented)
    assert exact, f"missing={missing} extra={extra}"
    assert len(discovered) == 7  # 8-activity linear chain has 7 edges


def test_miner_sees_seeded_noise_but_min_support_keeps_it_out_of_the_discovered_model(con):
    """The 24 seeded deviations introduce a handful of non-documented edges
    (an unauthorized activity, a duplicated activity, a reordered pair).
    First confirms the miner really does see this noise, at min_support=1
    (the raw edge table contains non-documented edges). Separately confirms
    that at a realistic min_support (5, the same threshold the "exact
    recovery" test above uses), none of that noise survives into the
    discovered model: min_support is the actual defense here, not the 0.9
    dominance fraction alone, since a from_activity that only ever appears
    once (an unauthorized activity's own single occurrence) is trivially
    "100% dominant" for itself regardless of the fraction threshold."""
    noisy_edges = discover_directly_follows(con, min_support=1)
    non_documented = noisy_edges[
        ~noisy_edges.apply(lambda r: (r["from_activity"], r["to_activity"]) in ref.ALLOWED_TRANSITIONS, axis=1)
    ]
    assert len(non_documented) > 0, "expected the seeded deviations to leave some non-documented edge trace"

    # min_support=5 alone does not remove every noise edge (some seeded
    # deviation types repeat often enough to clear a raw count of 5); it is
    # min_support combined with the 0.9 dominance fraction, checked together
    # by dominant_edges(), that keeps the discovered model clean, since any
    # surviving noise edge is still a small minority of its from_activity's
    # total outgoing mass.
    filtered_edges = discover_directly_follows(con, min_support=5)
    filtered_non_documented = filtered_edges[
        ~filtered_edges.apply(lambda r: (r["from_activity"], r["to_activity"]) in ref.ALLOWED_TRANSITIONS, axis=1)
    ]
    if len(filtered_non_documented) > 0:
        assert (filtered_non_documented["fraction_of_from_activity"] < 0.9).all()

    discovered = dominant_edges(filtered_edges, dominance_threshold=0.9)
    assert discovered == set(ref.ALLOWED_TRANSITIONS)
