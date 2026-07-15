"""
Test script for verifying placeholder alias mapping in the orchestrator.
Tests:
1. {{step_1.result.full_name}} -> NAME
2. {{step_1.result.phone_number}} -> PHONE
3. {{step_1.result.position}} -> POSITION
4. {{step_3.result.message}} -> BODY (Email body/message alias)
5. Embedded substring placeholder: "Welcome {{step_2.result.full_name}} to our team!"
"""
import sys
import os

# Insert backend dir to path for imports
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _backend_dir)

from orchestrator.execution_module import _resolve_placeholder

def run_test():
    print("=" * 60)
    print("  Testing Placeholder Alias Mapping in Orchestrator  ")
    print("=" * 60)

    # Mock parameters
    arguments = {}
    depends_on = [1]
    state = None  # State is not used in the placeholder resolution flow for simple/nested matches

    # Test Case 1: Simple match under DATA list (e.g. search_employees output)
    print("\n--- Test Case 1: Resolving 'full_name' to 'NAME' in DATA list ---")
    results_by_step = {
        1: {
            "success": True,
            "columns": ["ID", "NAME"],
            "data": [{"ID": 13, "NAME": "Rafael Richie"}]
        }
    }
    arguments = {"recipient_name": "{{step_1.result.full_name}}"}
    
    unresolved = _resolve_placeholder("recipient_name", "{{step_1.result.full_name}}", arguments, results_by_step, depends_on, state)
    print(f"Unresolved status: {unresolved}")
    print(f"Arguments: {arguments}")
    assert not unresolved, "Test Case 1 Failed: Should be resolved"
    assert arguments["recipient_name"] == "Rafael Richie", f"Test Case 1 Failed: expected 'Rafael Richie', got '{arguments.get('recipient_name')}'"
    print("[PASS] Test Case 1 successful!")

    # Test Case 2: Resolving 'phone_number' to 'PHONE' in DATA list
    print("\n--- Test Case 2: Resolving 'phone_number' to 'PHONE' in DATA list ---")
    results_by_step = {
        1: {
            "success": True,
            "data": [{"PHONE": "+62-812-8430-0979"}]
        }
    }
    arguments = {"recipient_phone": "{{step_1.result.phone_number}}"}
    
    unresolved = _resolve_placeholder("recipient_phone", "{{step_1.result.phone_number}}", arguments, results_by_step, depends_on, state)
    print(f"Unresolved status: {unresolved}")
    print(f"Arguments: {arguments}")
    assert not unresolved, "Test Case 2 Failed: Should be resolved"
    assert arguments["recipient_phone"] == "+62-812-8430-0979", f"Test Case 2 Failed: expected '+62-812-8430-0979', got '{arguments.get('recipient_phone')}'"
    print("[PASS] Test Case 2 successful!")

    # Test Case 3: Resolving 'position' in a flat dictionary result (e.g. get_employee_by_id output)
    print("\n--- Test Case 3: Resolving 'position' in flat dictionary ---")
    results_by_step = {
        1: {
            "success": True,
            "ID": 13,
            "NAME": "Rafael Richie",
            "POSITION": "Fullstack Developer"
        }
    }
    arguments = {"position": "{{step_1.result.position}}"}
    
    unresolved = _resolve_placeholder("position", "{{step_1.result.position}}", arguments, results_by_step, depends_on, state)
    print(f"Unresolved status: {unresolved}")
    print(f"Arguments: {arguments}")
    assert not unresolved, "Test Case 3 Failed: Should be resolved"
    assert arguments["position"] == "Fullstack Developer", f"Test Case 3 Failed: expected 'Fullstack Developer', got '{arguments.get('position')}'"
    print("[PASS] Test Case 3 successful!")

    # Test Case 4: Deep search fallback with aliases
    print("\n--- Test Case 4: Deep search fallback for 'email_address' ---")
    results_by_step = {
        1: {
            "success": True,
            "some_metadata": {
                "user_info": {
                    "email": "rafaelrichie03@gmail.com"
                }
            }
        }
    }
    arguments = {"email": "{{step_1.result.email_address}}"}
    
    unresolved = _resolve_placeholder("email", "{{step_1.result.email_address}}", arguments, results_by_step, depends_on, state)
    print(f"Unresolved status: {unresolved}")
    print(f"Arguments: {arguments}")
    assert not unresolved, "Test Case 4 Failed: Should be resolved via deep search fallback"
    assert arguments["email"] == "rafaelrichie03@gmail.com", f"Test Case 4 Failed: expected 'rafaelrichie03@gmail.com', got '{arguments.get('email')}'"
    print("[PASS] Test Case 4 successful!")

    # Test Case 5: Resolving 'message' from 'body' output of generate_email_content (Crucial Fix!)
    print("\n--- Test Case 5: Resolving 'message' from 'body' of generate_email_content ---")
    results_by_step = {
        3: {
            "success": True,
            "subject": "Konfirmasi Permohonan Surat Keterangan Kerja - Rafael Richie",
            "body": "Yth. Bapak Rafael Richie,\n\nSurat Keterangan Kerja Anda sedang diproses...",
            "recipient_name": "Rafael Richie"
        }
    }
    arguments = {"message": "{{step_3.result.message}}"}
    
    unresolved = _resolve_placeholder("message", "{{step_3.result.message}}", arguments, results_by_step, [3], state)
    print(f"Unresolved status: {unresolved}")
    print(f"Arguments: {arguments}")
    assert not unresolved, "Test Case 5 Failed: Should be resolved via MESSAGE->BODY alias mapping"
    assert arguments["message"].startswith("Yth. Bapak Rafael Richie"), f"Test Case 5 Failed: got '{arguments.get('message')}'"
    print("[PASS] Test Case 5 successful!")

    # Test Case 6: Substring/Embedded Placeholders (Crucial Fix!)
    print("\n--- Test Case 6: Substring/Embedded Placeholders Resolution ---")
    results_by_step = {
        2: {
            "ID": 13,
            "NAME": "Rafael Richie",
            "POSITION": "Fullstack Developer"
        }
    }
    arguments = {
        "context": "Surat keterangan kerja yang menyatakan bahwa {{step_2.result.full_name}} adalah karyawan tetap di PT. Prima Integrasi Network. Posisinya adalah {{step_2.result.position}}."
    }
    
    unresolved = _resolve_placeholder("context", arguments["context"], arguments, results_by_step, [2], state)
    print(f"Unresolved status: {unresolved}")
    print(f"Arguments: {arguments}")
    assert not unresolved, "Test Case 6 Failed: Substring placeholders should be resolved successfully"
    expected_context = "Surat keterangan kerja yang menyatakan bahwa Rafael Richie adalah karyawan tetap di PT. Prima Integrasi Network. Posisinya adalah Fullstack Developer."
    assert arguments["context"] == expected_context, f"Test Case 6 Failed:\nExpected: {expected_context}\nGot: {arguments.get('context')}"
    print("[PASS] Test Case 6 successful!")

    print("\n" + "=" * 60)
    print("  All Placeholder Alias & Substring Resolution Tests PASSED!  ")
    print("=" * 60)

if __name__ == "__main__":
    run_test()
