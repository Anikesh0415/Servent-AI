import webview
import threading
import asyncio
import os
import subprocess

from server import AIF_Server

def start_ollama():
    try:
        print("Starting Ollama background service...")
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(['ollama', 'serve'], startupinfo=startupinfo)
    except Exception as e:
        print(f"Failed to start Ollama: {e}")

def start_server():
    server = AIF_Server()
    # Initialize a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.main_server())

if __name__ == "__main__":
    print("Starting AI Ecosystem...")
    start_ollama()
    print("Initializing Ecosystem Engine...")
    
    # Boot the AI Core in the background
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Locate the frontend UI
    ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui', 'index.html')
    
    # Create the native desktop window wrapper
    window = webview.create_window(
        'Ecosystem Control Center', 
        f'file://{ui_path}', 
        width=1000, 
        height=700,
        frameless=False, # Set to True later if you want a custom title bar
        background_color='#121212'
    )
    
    print("Launching Native Interface...")
    webview.start()
