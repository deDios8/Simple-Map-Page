"""
Main server application that listens to Firebase database changes and updates the ECS world accordingly.
"""

import esper
import ecs_proc_events
import ecs_proc_border_db
from session_db_state import DEFAULT_DATABASE_URL, SessionState
import sys

def main() -> None:
    print("Firebase Feature Listener")
    if len(sys.argv) > 1:
        session_name = sys.argv[1]
        print(f"Session Name: {session_name}")
    else:
        session_name = input("Session name: ")
    session_state = SessionState(DEFAULT_DATABASE_URL, session_name)
    esper.add_processor(ecs_proc_border_db.ApplyClientRequests(session_state), priority=100)
    esper.add_processor(ecs_proc_border_db.CheckZoneEntryExit(session_state), priority=95)
    esper.add_processor(ecs_proc_events.CriteriaProcessor(session_state), priority=90)
    esper.add_processor(ecs_proc_events.EventProcessor(session_state), priority=80)
    esper.add_processor(ecs_proc_border_db.RemoveZoneEntryExit(), priority=10)
    esper.add_processor(ecs_proc_border_db.SyncZonesToDatabase(session_state), priority=0)
    session_state.run_db_and_ecs_processor()


if __name__ == "__main__":
    main()

