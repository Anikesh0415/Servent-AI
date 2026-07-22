import json
from src.macro_orchestrator import macro_orchestrator
from src.planner import planner_instance

prompts = [
    """Begin the 'Legacy Database Migration' protocol. Open the local directory C:\\Legacy_Records\\ containing 10,000 nested folders, each representing a client.
For every single folder, sequentially execute the following loop:
Open the folder, locate the PDF named client_data.pdf, and open it.
Use Semantic Copy (Ctrl+A) to grab all raw text and send it to the Hermes LLM Data Cleaner to extract the 'Account ID' and 'Current Balance'.
Open the target CRM web portal in Chrome.
Use OCR (PyTesseract) to locate the 'Global Search' bar, click it, and paste the 'Account ID'.
Wait for the client profile to load. Use VISTA Moondream to visually verify that the profile picture and 'Active' status badge have rendered on the screen.
If Moondream returns a Condition Failed (e.g., 'Not Found' or 'Inactive'), log 'FAILED' in a master audit.csv file and immediately move to the next client folder.
If Moondream returns Condition Met, use normal UI actions to scroll down, click the 'Update Balance' text box, and type the cleaned 'Current Balance'.
Click 'Save'.
Use Moondream to verify the green 'Saved Successfully' banner appears.
Close the CRM tab, close the PDF, and proceed to the next folder.
Continue this exact loop without stopping until all 10,000 folders have been processed."""
]

def run_tests():
    print("# Full Divided-Brain Pipeline Test Results\n", flush=True)
    for i, prompt in enumerate(prompts):
        print(f"## Test {i+1}: 80+ Action Prompt Processing", flush=True)
        try:
            print("### Phase 1: Macro Orchestrator (Architect Brain)", flush=True)
            macro_plan = macro_orchestrator.analyze_instruction(prompt)
            print(json.dumps(macro_plan, indent=2), flush=True)
            
            if macro_plan.get("is_loop"):
                print("\n### Phase 2: ARIA Planner (Worker Brain)", flush=True)
                
                setup = macro_plan.get("setup_instructions")
                if setup:
                    print("\n#### Generating Setup Plan:", flush=True)
                    setup_json = planner_instance.generate_action_plan(setup, "Context: Desktop")
                    print(json.dumps(setup_json, indent=2), flush=True)
                    
                loop = macro_plan.get("loop_instructions")
                if loop:
                    print("\n#### Generating Loop Iteration Plan (Runs N times):", flush=True)
                    loop_json = planner_instance.generate_action_plan(loop, "Context: Target App")
                    print(json.dumps(loop_json, indent=2), flush=True)
                    
                teardown = macro_plan.get("teardown_instructions")
                if teardown:
                    print("\n#### Generating Teardown Plan:", flush=True)
                    teardown_json = planner_instance.generate_action_plan(teardown, "Context: Desktop")
                    print(json.dumps(teardown_json, indent=2), flush=True)

        except Exception as e:
            print(f"### Error:\n{e}", flush=True)
        print("\n---\n", flush=True)

if __name__ == "__main__":
    run_tests()
