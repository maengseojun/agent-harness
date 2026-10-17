"""Process boundary: chosen in-process scenarios re-run with hooks and CLIs spawned as real processes.

The in-process runner calls `maeng_hooks.main()` / runs bin scripts as __main__ inside the test process. That cannot
see what only a real process shows: the interpreter start, `sys.path` set-up of the entry scripts, real stdin/stdout
bytes, exit codes and environment inheritance. Every hook event and every CLI keeps its representative deny and
allow paths here; the rest of each class stays in-process. (Run the whole suite this way with HARNESS_TEST_PROCESS=1.)
"""
from . import test_cli, test_g1, test_merge, test_r2, test_r5, test_stop_hooks


def proc(base, *names):
    """Subclass of `base` that spawns real processes and runs only `names` (all tests when none are given)."""
    attrs = {"PROCESS": True, "__module__": __name__, "__qualname__": base.__name__ + "Proc"}
    if names:
        missing = [n for n in names if not hasattr(base, n)]
        assert not missing, f"{base.__name__} has no {missing}"
        attrs.update({n: None for n in dir(base) if n.startswith("test") and n not in names})
    return type(base.__name__ + "Proc", (base,), attrs)


# hook events: Stop, UserPromptSubmit, PostToolUse, SessionStart; unreadable stdin and its exit code
# (DispatcherFailureModes and R1_1 patch handlers in-process, so they have no process form)
StopProc = proc(test_stop_hooks.StopTests, "test_block_once_then_system_message_and_state_kept",
                "test_verified_and_recorded_stops_cleanly")
HookInputProc = proc(test_r2.R2_D_HookInputFailsClosed)
# PreToolUse: default-branch push / merge denied, feature push allowed
SlimGateProc = proc(test_g1.SlimGate, "test_only_default_branch_pushes_and_merges_are_denied",
                    "test_feature_pushes_gh_env_and_eta_paths_are_allowed")
# CLIs
VerifyExecProc = proc(test_r5.R5_4_ExecAndDeclarations, "test_exec_records_runner_evidence_and_satisfies",
                      "test_failing_run_records_failure_and_exit_code", "test_tree_change_during_exec_records_no_evidence")
VerifyCliProc = proc(test_cli.VerifyCli)
ReviewRunProc = proc(test_cli.ReviewRun, "test_pass_verdict_is_stored_as_receipt_with_exact_flags",
                     "test_fail_verdict_stores_no_receipt")
EtaIsolateProc = proc(test_cli.EtaIsolate, "test_apply_merges_keys_installs_and_is_idempotent")
ShipThroughHookProc = proc(test_merge.ExactLeaseThroughHook, "test_exact_form_needs_matching_receipt",
                           "test_post_hooks_consume_reject_or_leave_pending")
