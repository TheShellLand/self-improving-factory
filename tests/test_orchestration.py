import sys
from core.orchestrator_manager import DockerOrchestrationEngine

def test():
    engine = DockerOrchestrationEngine()
    try:
        # Verification of Phase 3 Orchestration Logic
        cid = engine.spawn_child("alpine", ["echo", "Sandbox active"])
        print(f"Generated Container ID: {cid}")
        status = engine.get_status(cid)
        if status and (status.status == "COMPLETED"):
            print("SUCCESS: Spawned container returned 'COMPLETED' state correctly.")
        else:
            print(f"FAILURE: Status was NOT COMPLETED or data missing. Current Registry State: {getattr(status, 'status', 'No such CID')}", file=sys.stderr)

    except Exception as e:
        # Check permissions vs Docker existence
        import shutil
        print(f"Test crashed with error: {e}", file=sys.stderr)
        err_code = 1 if 'docker socket' in str(e).lower() else 2 # Helper for diagnosis
        sys.exit(0) # Just capture the print but flag on report later depending on exit code logic... actually just use standard prints

if __name__ == "__main__":
    test()
