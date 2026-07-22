import os
import subprocess
import time
import sys

def boot():
    print("Booting NOVA AI Core...")
    
    # Ensure working directory is correct
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print("1. Starting Ollama Server...")
    subprocess.Popen(
        "cmd /c ollama serve",
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    time.sleep(5)

    print("2. Starting Python Backend...")
    python_exe = os.path.join(project_dir, "venv", "Scripts", "python.exe")
    
    if not os.path.exists(python_exe):
        print(f"CRITICAL ERROR: Could not find Python environment at {python_exe}")
        print("Please ensure your venv is set up correctly.")
        os.system("pause")
        sys.exit(1)
        
    subprocess.Popen(
        f'cmd /k "{python_exe}" server.py',
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    time.sleep(3)

    print("3. Launching Web Dashboard...")
    os.system("start ui\\index.html")
    
    print("Startup complete!")

if __name__ == "__main__":
    boot()
