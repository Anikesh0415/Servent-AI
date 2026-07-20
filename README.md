# Servent-AI: Action Intelligence Framework (AIF)

Servent-AI is a 100% local, privacy-first Windows OS automation agent. It enables users to control their operating systems entirely hands-free using natural voice commands and real-time hand gestures. By utilizing local reasoning models (Hermes 2 Pro) and vision models (Moondream), Servent-AI autonomously plans and executes complex, multi-step actions on your computer, verifying the visual state of the screen at every step.

This framework is built with **accessibility** at its heart, providing physically challenged or motor-impaired individuals a way to fully operate their computers, write code, and build digital careers independently.

---

## Key Features

* **🎤 Hands-Free Voice Control:** Uses local OpenAI Whisper models to transcribe voice commands (e.g. *"open Gemini, write a letter, and send it to my friend on WhatsApp"*).
* **🖐️ Real-Time Gesture Tracking:** Tracks hand coordinates and finger curls using MediaPipe to control mouse cursor movement, clicks, and page scrolling.
* **🧠 Aria Planning Brain:** Uses **Hermes 2 Pro 8B** (via LM Studio) to convert abstract voice instructions into structured, step-by-step JSON plan arrays.
* **🏗️ Hierarchical Macro-Orchestrator:** Intercepts massive 80+ action macro loops and acts as a Software Architect, dynamically orchestrating the LLM through setup, loop, and teardown logic without blowing the context window.
* **👁️ VISTA Visual Verification:** Automatically captures screenshots and queries a local **Moondream** vision model to verify whether a page loaded or a loading animation has finished before proceeding.
* **📚 Skill Library (RAG):** Dynamically injects context-specific examples into the prompt to prevent hallucination without breaking context limits.
* **🪄 Semantic Copy & OCR Clicking:** Uses PyTesseract for native OCR-based clicking and leveraging Hermes to semantically extract and clean messy clipboard data in real-time.
* **⚡ Native Accessibility & DOM Snapshotting:** Uses UIAutomation to instantaneously click desktop buttons and rips real-time DOM snapshots for perfect-context error recovery replanning.
* **📱 Hybrid Remote Architecture:** Use your Android/iOS phone as a remote control. The Python backend broadcasts to your local Wi-Fi, allowing you to trigger complex Windows desktop automations from your couch using the mobile web app.
* **🧠 Persistent Context Memory & Chat History:** Local persistent chat history drawer with dedicated settings to provide the AI with long-term user context across all sessions.
* **🚦 Smart Intent Router:** Intelligently separates conversational chats, headless background API tasks, and physical GUI takeover actions to prevent workflow interruptions.
* **🎓 Dynamic Student Focus Mode:** Transforms the UI into a dedicated study hub with interactive flashcards and notebook features.
* **🛡️ Security Guardrails:** Intercepts vague intentions and actively blacklists destructive terminal commands before they can be executed.
* **🔒 100% Local & Private:** No APIs, no cloud dependencies, no paywalls, and completely offline. Your data never leaves your machine.

---

## Architecture Flow

```mermaid
graph TD
    User(("🗣️ User Request")) --> UI["💻 Ecosystem Control Center"]
    
    subgraph Execution Routing
        UI --> Router{"🚦 Smart Intent Router"}
        Router -->|Conversational| ChatResponse["💬 Instant Chat Reply"]
        Router -->|Background| HeadlessWorker["👻 Headless API Engine"]
        Router -->|GUI Takeover| Macro["🏗️ Macro Orchestrator\n(Logic & Loops)"]
        Router -->|Student Focus| StudentEngine["🎓 AI Tutor Engine"]
    end
    
    subgraph Headless Execution
        HeadlessWorker --> FetchAPI["🌐 Background API Call\n(YouTube Transcript API)"]
        FetchAPI --> LLMSummarize["🧠 Background LLM Summarize\n(Hermes 8B)"]
        LLMSummarize --> UI
    end
    
    subgraph Tutor Execution
        StudentEngine --> QuizGen["📝 Generate Interactive Quiz"]
        StudentEngine --> FlashcardGen["📇 Generate Smart Flashcards"]
    end
    
    subgraph GUI Takeover
        Macro -->|Dynamic Sub-Tasks| Planner{"🧠 ARIA Planner\n(Hermes 8B)"}
        SkillDB[("📚 Skill Library\n(RAG / skills.json)")] -.->|Injects Examples| Planner
        
        Planner -->|JSON Action Plan| AgentLoop(("⚙️ Central Agent Loop"))
        
        AgentLoop -->|Execute| ExecMgr["⚡ Execution Manager\n(PyAutoGUI / PyTesseract)"]
        AgentLoop -->|Verify| VistaWait["👁️ VISTA Moondream\n(smart_wait_for_completion)"]
        
        VistaWait -.->|Wait Condition Met ✓| AgentLoop
        
        ExecMgr --> TargetApp["🖥️ Target App\n(WhatsApp, Web, etc.)"]
        ExecMgr --> OCRClick["👀 OCR click_text"]
        OCRClick --> TargetApp
        ExecMgr --> SemanticCopy["🪄 Semantic Copy"]
        SemanticCopy --> HermesFilter{"🧹 Hermes LLM\nData Cleaner"}
        HermesFilter --> TargetApp
    end
```

---

## Prerequisites & Installation

### 1. Set Up Local Models
* **LM Studio:** Download and run [LM Studio](https://lmstudio.ai/). Load **`Hermes-2-Pro-Llama-3-8B-GGUF`** (or a similar function-calling model) and start the local API server on port `1234`.
* **Ollama:** Install [Ollama](https://ollama.com/) and run the following in your terminal to pull the visual model:
  ```bash
  ollama pull moondream
  ```

### 2. Install Tesseract OCR
For the visual `click_text` capabilities to work, you must install Tesseract:
* **Windows:** Download and install the [Tesseract-OCR executable](https://github.com/UB-Mannheim/tesseract/wiki). Ensure the installation path is added to your Windows Environment Variables.

### 3. Install Project Dependencies
1. Clone the repository:
   ```bash
   git clone https://github.com/Anikesh0415/Servent-AI.git
   cd Servent-AI
   ```
2. Activate your virtual environment and install dependencies:
   ```bash
   .\venv\Scripts\activate
   pip install -r requirements.txt
   pip install pytesseract pyperclip
   ```

---

## Usage

### Option 1: Desktop Master Interface
1. Start your local model servers (LM Studio on port `1234` and Ollama on port `11434`).
2. Run the bootstrapper script:
   ```bash
   Start_Ecosystem.bat
   ```
3. Open the locally served dashboard at `ui/index.html`.
4. Speak a command (e.g., *"open Gemini, ask for a letter, and copy it..."*) or use hand gestures to control the cursor!

### Option 2: Mobile Remote Control
1. Ensure your PC and phone are on the same Wi-Fi network.
2. Find your PC's IP Address (`ipconfig`).
3. Run the Python backend (`python server.py`) which broadcasts on `0.0.0.0`.
4. Host the `ui` folder on your PC (e.g., `python -m http.server 8000`).
5. On your phone, visit `http://<YOUR_PC_IP>:8000/android.html` and connect to the brain to control your PC remotely!

---

## Contributing & License
Distributed under the MIT License. Feel free to open issues and pull requests to help make computing accessible for everyone!
