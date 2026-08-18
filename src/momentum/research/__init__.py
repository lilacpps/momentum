"""Research/statistics modules separate from the M0 execution engine."""

__all__ = ["run_m1a_track_b", "run_m2_track_b"]


def __getattr__(name: str):
    if name == "run_m1a_track_b":
        from .m1a import run_m1a_track_b

        return run_m1a_track_b
    if name == "run_m2_track_b":
        from .m2 import run_m2_track_b

        return run_m2_track_b
    raise AttributeError(name)
