const wsStatus = document.getElementById('ws-status');
const sysState = document.getElementById('sys-state');
const statusDot = document.getElementById('status-dot');
const actionText = document.getElementById('action-text');

// Chat UI Elements
const chatLog = document.getElementById('chat-log');
const textInput = document.getElementById('text-command-input');
const sendBtn = document.getElementById('send-btn');
const ttsToggle = document.getElementById('tts-toggle');
const timeWidget = document.getElementById('time-widget');
const voiceSelect = document.getElementById('voice-select');

let ws;
let reconnectInterval = 2000;
let ttsEnabled = true;
let lastVoiceText = "";
let lastReplyText = '';
let voices = [];

// Time Update
function updateTime() {
    const now = new Date();
    let hours = now.getHours();
    let minutes = now.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12; 
    minutes = minutes < 10 ? '0' + minutes : minutes;
    timeWidget.textContent = `${hours}:${minutes} ${ampm}`;
}
setInterval(updateTime, 1000);
updateTime();

// Pomodoro Logic
let pomodoroInterval;
let pomodoroTime = 25 * 60;
let isPomodoroActive = false;
const pomodoroWidget = document.getElementById('pomodoro-widget');
const pomodoroText = document.getElementById('pomodoro-text');

if (pomodoroWidget) {
    pomodoroWidget.addEventListener('click', () => {
        if (isPomodoroActive) {
            // Stop Pomodoro
            clearInterval(pomodoroInterval);
            isPomodoroActive = false;
            pomodoroTime = 25 * 60;
            pomodoroText.textContent = "25:00";
            pomodoroWidget.style.background = "";
            appendMessage('SYSTEM', 'Focus Mode Disabled. Distractions unblocked.');
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ command: "UNBLOCK_SITES" }));
            }
        } else {
            // Start Pomodoro
            isPomodoroActive = true;
            pomodoroWidget.style.background = "rgba(231, 76, 60, 0.4)";
            appendMessage('SYSTEM', 'Focus Mode Enabled for 25 minutes. Distractions blocked.');
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ command: "BLOCK_SITES" }));
            }
            
            pomodoroInterval = setInterval(() => {
                pomodoroTime--;
                let m = Math.floor(pomodoroTime / 60).toString().padStart(2, '0');
                let s = (pomodoroTime % 60).toString().padStart(2, '0');
                pomodoroText.textContent = `${m}:${s}`;
                
                if (pomodoroTime <= 0) {
                    clearInterval(pomodoroInterval);
                    isPomodoroActive = false;
                    pomodoroTime = 25 * 60;
                    pomodoroText.textContent = "25:00";
                    pomodoroWidget.style.background = "";
                    appendMessage('SYSTEM', 'Focus Mode Complete! Take a 5 minute break.');
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({ command: "UNBLOCK_SITES" }));
                    }
                }
            }, 1000);
        }
    });
}

// TTS Toggle Logic
ttsToggle.addEventListener('click', () => {
    ttsEnabled = !ttsEnabled;
    if(ttsEnabled) {
        ttsToggle.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
    } else {
        ttsToggle.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
        if (window.speechSynthesis) window.speechSynthesis.cancel();
    }
});

// Load Voices
function loadVoices() {
    voices = window.speechSynthesis.getVoices();
    const voiceOptionsContainer = document.getElementById('voice-options-container');
    const voiceSelectedText = document.getElementById('voice-selected-text');
    if (!voiceOptionsContainer) return;
    
    voiceOptionsContainer.innerHTML = '';
    
    if (voices.length > 0 && voiceSelectedText.textContent === 'Loading voices...') {
        voiceSelectedText.textContent = voices[0].name;
    }
    
    voices.forEach((voice, i) => {
        const option = document.createElement('div');
        option.className = 'custom-dropdown-option';
        option.dataset.value = voice.name;
        // Prioritize female or beautiful natural voices if possible in the label
        let label = voice.name;
        if (voice.default) label += ' (Default)';
        option.textContent = label;
        
        option.addEventListener('click', () => {
            voiceSelectedText.textContent = option.textContent;
            voiceSelectedText.dataset.value = voice.name;
        });
        
        voiceOptionsContainer.appendChild(option);
    });
}

// Some browsers need this event, some load immediately
if (speechSynthesis.onvoiceschanged !== undefined) {
    speechSynthesis.onvoiceschanged = loadVoices;
}
loadVoices();

function speakText(text) {
    if (!ttsEnabled || !window.speechSynthesis) return;
    window.speechSynthesis.cancel(); 
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US'; // Force English language
    
    // Set selected voice or fallback to English
    const voiceSelectedText = document.getElementById('voice-selected-text');
    const selectedVoiceName = voiceSelectedText ? (voiceSelectedText.dataset.value || voiceSelectedText.textContent) : null;
    let chosenVoice = null;
    if (selectedVoiceName && voices.length > 0) {
        chosenVoice = voices.find(v => v.name === selectedVoiceName);
    }
    if (!chosenVoice && voices.length > 0) {
        chosenVoice = voices.find(v => v.lang && v.lang.startsWith('en'));
    }
    if (chosenVoice) {
        utterance.voice = chosenVoice;
    }
    
    utterance.pitch = 1.0;
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
}

let currentTraceContainer = null;

function appendMessage(sender, text) {
    if (!text || typeof text !== 'string' || text.trim() === '') return;
    text = text.trim();

    // Prevent duplicate user messages from rendering back-to-back
    if (sender === 'USER') {
        const lastMsg = chatLog.lastElementChild;
        if (lastMsg && lastMsg.classList.contains('user-msg')) {
            if (lastMsg.textContent.trim() === text) {
                return; // Skip duplicate message!
            }
        }
    } else if (sender === 'SYSTEM' && !text.startsWith('[TRACE]')) {
        const lastMsg = chatLog.lastElementChild;
        if (lastMsg && lastMsg.classList.contains('system-msg')) {
            if (lastMsg.textContent.trim() === text) {
                return; // Skip duplicate system message!
            }
        }
    }

    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message');
    
    if (sender === 'USER') {
        msgDiv.classList.add('user-msg');
        // Reset trace container when user speaks
        if (currentTraceContainer) {
            currentTraceContainer.removeAttribute('open');
            currentTraceContainer = null;
        }
    } else {
        msgDiv.classList.add('system-msg');
        
        if (text.startsWith("[TRACE]")) {
            text = text.replace("[TRACE]", "").trim();
            
            if (!currentTraceContainer) {
                currentTraceContainer = document.createElement('details');
                currentTraceContainer.classList.add('trace-container');
                currentTraceContainer.setAttribute('open', '');
                
                const summary = document.createElement('summary');
                summary.textContent = "Task Execution Trace";
                currentTraceContainer.appendChild(summary);
                
                msgDiv.appendChild(currentTraceContainer);
                chatLog.appendChild(msgDiv);
            }
            
            // Deduplicate trace lines inside currentTraceContainer
            const existingLines = Array.from(currentTraceContainer.querySelectorAll('.trace-line'));
            if (existingLines.some(l => l.textContent.trim() === text)) {
                return; // Skip duplicate trace line!
            }

            const traceLine = document.createElement('div');
            traceLine.classList.add('trace-line');
            traceLine.textContent = text;
            currentTraceContainer.appendChild(traceLine);
            chatLog.scrollTop = chatLog.scrollHeight; 
            
            // Auto close if it's the final trace
            if (text === "Plan execution completed successfully." || text.includes("Macro Orchestration Completed")) {
                currentTraceContainer.removeAttribute('open');
                currentTraceContainer = null;
            }
            return; // We appended into the trace container, so skip standard bubble creation
        } else if (text.startsWith("[ANSWER]")) {
            if (currentTraceContainer) {
                currentTraceContainer.removeAttribute('open');
                currentTraceContainer = null;
            }
            text = text.replace("[ANSWER]", "").trim();
            const bubble = document.createElement('div');
            bubble.classList.add('msg-bubble', 'answer-bubble');
            bubble.textContent = text;
            msgDiv.appendChild(bubble);
        } else {
            // Standard system message (no tags)
            if (currentTraceContainer) {
                currentTraceContainer.removeAttribute('open');
                currentTraceContainer = null;
            }
            const bubble = document.createElement('div');
            bubble.classList.add('msg-bubble');
            bubble.textContent = text;
            msgDiv.appendChild(bubble);
        }
    }
    
    if (sender === 'USER') {
        const bubble = document.createElement('div');
        bubble.classList.add('msg-bubble');
        bubble.textContent = text;
        msgDiv.appendChild(bubble);
    }
    
    if (msgDiv.children.length > 0) {
        chatLog.appendChild(msgDiv);
    }
    chatLog.scrollTop = chatLog.scrollHeight; 
}

function connectWebSocket() {
    ws = new WebSocket('ws://localhost:8765');

    ws.onopen = () => {
        wsStatus.textContent = 'CONNECTED';
        wsStatus.style.color = '#34c759';
        statusDot.classList.add('active');
        updateState('ONLINE');
        
        // Request history on connect
        ws.send(JSON.stringify({ command: "GET_HISTORY" }));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "FOLDER_SELECTED") {
            const folderInput = document.getElementById('dev-folder-input');
            if (folderInput) {
                folderInput.value = data.path;
            }
            return;
        }
        
        if (data.type === "INJECT_UI") {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message system-msg`;
            msgDiv.innerHTML = `<div class="msg-bubble" style="padding:0; background:transparent; border:none; box-shadow:none;">${data.html}</div>`;
            document.getElementById('chat-log').appendChild(msgDiv);
            document.getElementById('chat-log').scrollTop = document.getElementById('chat-log').scrollHeight;
            
            // Re-initialize mermaid in case the injected HTML contains a mindmap
            if (window.mermaid) {
                setTimeout(() => { mermaid.init(undefined, document.querySelectorAll('.mermaid')); }, 100);
            }
            return;
        }

        if (data.type === "CHAT_HISTORY") {
            chatLog.innerHTML = ""; // Clear existing log
            updateHistoryDrawer(data.history);
            
            if (!data.history || data.history.length === 0) {
                const hour = new Date().getHours();
                let greeting = "Good evening";
                if (hour < 12) greeting = "Good morning";
                else if (hour < 17) greeting = "Good afternoon";
                
                appendMessage('SYSTEM', `${greeting}, Developer! System is online and ready.`);
            } else {
                let lastUserMsg = "";
                data.history.forEach(msg => {
                    appendMessage(msg.sender, msg.text);
                    if (msg.sender === "USER") {
                        lastUserMsg = msg.text;
                    }
                });
                if (lastUserMsg) {
                    lastVoiceText = lastUserMsg;
                }
            }
            return;
        }
        
        if (data.state) {
            updateState(data.state);
        }
        
        const isProcessing = data.state === 'PROCESSING_INTENT' || data.state === 'EXECUTING';
        textInput.disabled = isProcessing;
        sendBtn.disabled = isProcessing;
        if (isProcessing) {
            textInput.placeholder = 'Processing...';
        } else {
            textInput.placeholder = 'Type an automation command...';
        }
        
        // Fix for chat log duplication bug: only append if text changed
        if (data.voice_text && data.voice_text !== lastVoiceText) {
            appendMessage('USER', data.voice_text);
            lastVoiceText = data.voice_text;
        }
        
        if (data.reply_text && data.reply_text !== lastReplyText) {
            lastReplyText = data.reply_text;
            appendMessage('SYSTEM', data.reply_text);
            speakText(data.reply_text);
        }
        
        if (data.action_text) {
            actionText.textContent = data.action_text;
        }
    };

    ws.onclose = () => {
        wsStatus.textContent = 'DISCONNECTED';
        wsStatus.style.color = '#ff3b30';
        statusDot.classList.remove('active');
        sysState.textContent = 'OFFLINE';
        const stateWrapper = sysState ? sysState.closest('.sys-state-wrapper') : null;
        if (stateWrapper) {
            stateWrapper.classList.remove('online');
            stateWrapper.classList.add('offline');
        }
        setTimeout(connectWebSocket, reconnectInterval);
    };
}

function updateState(stateName) {
    sysState.textContent = stateName;
    const stateWrapper = sysState ? sysState.closest('.sys-state-wrapper') : null;
    if (stateWrapper) {
        if (stateName === 'OFFLINE' || stateName === 'DISCONNECTED') {
            stateWrapper.classList.remove('online');
            stateWrapper.classList.add('offline');
        } else {
            stateWrapper.classList.remove('offline');
            stateWrapper.classList.add('online');
        }
    }
    const confirmWrapper = document.getElementById('confirmation-wrapper');
    const inputWrapper = document.getElementById('input-wrapper');
    
    // Train Animation Logic
    const progressContainer = document.getElementById('macro-progress');
    const progressTrain = document.getElementById('progress-train');
    const progressText = document.getElementById('macro-progress-text');
    
    if (progressContainer && progressTrain && progressText) {
        // Reset stations
        for(let i=1; i<=4; i++) {
            const st = document.getElementById(`station-${i}`);
            if(st) { st.classList.remove('active', 'passed'); }
        }

        if (stateName === 'ONLINE' || stateName === 'STANDBY') {
            progressText.textContent = "Engine Standby - Ready for Task";
            progressTrain.style.left = "12%";
            if (document.getElementById('station-1')) {
                document.getElementById('station-1').classList.add('active');
            }
        } else {
            if (stateName.includes('PLAN')) {
                progressText.textContent = "Analyzing requirements & planning...";
                progressTrain.style.left = "12%";
                if (document.getElementById('station-1')) document.getElementById('station-1').classList.add('active');
            } else if (stateName === 'EXECUTING' || stateName.includes('RUN')) {
                progressText.textContent = "Executing automation steps...";
                progressTrain.style.left = "38%";
                if (document.getElementById('station-1')) document.getElementById('station-1').classList.add('passed');
                if (document.getElementById('station-2')) document.getElementById('station-2').classList.add('active');
            } else if (stateName === 'AWAITING_CONFIRMATION' || stateName.includes('VERIFY')) {
                progressText.textContent = "Waiting for verification/approval...";
                progressTrain.style.left = "63%";
                if (document.getElementById('station-1')) document.getElementById('station-1').classList.add('passed');
                if (document.getElementById('station-2')) document.getElementById('station-2').classList.add('passed');
                if (document.getElementById('station-3')) document.getElementById('station-3').classList.add('active');
            } else if (stateName === 'COMPLETE' || stateName === 'FINISHED') {
                progressText.textContent = "Task Complete!";
                progressTrain.style.left = "88%";
                if (document.getElementById('station-1')) document.getElementById('station-1').classList.add('passed');
                if (document.getElementById('station-2')) document.getElementById('station-2').classList.add('passed');
                if (document.getElementById('station-3')) document.getElementById('station-3').classList.add('passed');
                if (document.getElementById('station-4')) document.getElementById('station-4').classList.add('active');
            } else {
                progressText.textContent = `System state: ${stateName}...`;
            }
        }
    }

    if (confirmWrapper && inputWrapper) {
        if (stateName === 'AWAITING_CONFIRMATION') {
            const autoConfirm = document.getElementById('auto-confirm-toggle');
            if (autoConfirm && autoConfirm.checked) {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ command: "CONFIRM_PLAN" }));
                }
                return;
            }
            confirmWrapper.style.display = 'flex';
            inputWrapper.style.display = 'none';
        } else {
            confirmWrapper.style.display = 'none';
            inputWrapper.style.display = 'flex';
        }
    }
}

// Confirmation Button Logic
const confirmBtn = document.getElementById('confirm-btn');
const rejectBtn = document.getElementById('reject-btn');
const replanBtn = document.getElementById('replan-btn');

if (confirmBtn && rejectBtn) {
    confirmBtn.addEventListener('click', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: "CONFIRM_PLAN" }));
        }
    });
    
    rejectBtn.addEventListener('click', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: "REJECT_PLAN" }));
        }
    });
}
if (replanBtn) {
    replanBtn.addEventListener('click', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            appendMessage('SYSTEM', 'Requesting new plan...');
            // In a real system, you might prompt for feedback here. For now we just mock a reject and re-prompt.
            ws.send(JSON.stringify({ command: "REJECT_PLAN" }));
        }
    });
}

// Image Upload Logic
let currentAttachedImage = null;

const uploadBtn = document.getElementById('upload-image-btn');
const imageInput = document.getElementById('image-upload-input');
const imagePreviewContainer = document.getElementById('image-preview-container');
const imagePreview = document.getElementById('image-preview');
const removeImageBtn = document.getElementById('remove-image-btn');
const selectFolderBtn = document.getElementById('select-folder-btn');

if (selectFolderBtn) {
    selectFolderBtn.addEventListener('click', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: "SELECT_FOLDER" }));
        }
    });
}

if (uploadBtn && imageInput) {
    uploadBtn.addEventListener('click', () => imageInput.click());
    
    imageInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
                currentAttachedImage = event.target.result;
                imagePreview.src = currentAttachedImage;
                imagePreviewContainer.style.display = 'flex';
                
                // Send immediately to server
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        command: "IMAGE_UPLOAD",
                        image: currentAttachedImage
                    }));
                }
            };
            reader.readAsDataURL(file);
        }
    });
}

if (removeImageBtn) {
    removeImageBtn.addEventListener('click', () => {
        currentAttachedImage = null;
        imagePreview.src = "";
        imagePreviewContainer.style.display = 'none';
        imageInput.value = ""; // Reset input
    });
}

// Text Input Logic
function sendTextCommand() {
    let text = textInput.value.trim();
    if (text && ws && ws.readyState === WebSocket.OPEN) {
        // Intercept macro commands typed manually
        if (text === "generate-snippet" || text === "generate-flashcard" || text === "generate-handwritten") {
            const tempBtn = document.createElement('button');
            tempBtn.className = 'macro-btn';
            tempBtn.setAttribute('data-cmd', text);
            // Simulate click to trigger existing macro logic
            macroBtns.forEach(btn => {
                if (btn.getAttribute('data-cmd') === text) {
                    btn.click();
                }
            });
            textInput.value = '';
            return;
        }

        // Dev Mode / Student Mode Injection
        const devToggle = document.getElementById('dev-mode-btn');
        const studentToggle = document.getElementById('student-mode-btn');
        
        if (devToggle && devToggle.classList.contains('active')) {
            const devFolder = document.getElementById('dev-folder-input').value.trim() || "C:\\";
            text = `[DEV_MODE: ${devFolder}] ${text}`;
        } else if (studentToggle && studentToggle.classList.contains('active')) {
            const studentUrl = document.getElementById('student-url-input').value.trim();
            text = `[STUDENT_MODE: ${studentUrl}] ${text}`;
        }

        appendMessage('USER', textInput.value.trim()); // Display clean text to user
        // Temporarily set lastVoiceText to avoid duping it when the server echoes it back
        lastVoiceText = textInput.value.trim();
        
        updateState('PLANNING');
        ws.send(JSON.stringify({
            command: "TEXT_INPUT",
            text: text
        }));
        
        textInput.value = '';
        
        // Clear attached image after sending
        if (currentAttachedImage) {
            currentAttachedImage = null;
            imagePreview.src = "";
            imagePreviewContainer.style.display = 'none';
            imageInput.value = "";
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    fetchTheme();
});


sendBtn.addEventListener('click', (e) => {
    e.preventDefault();
    sendTextCommand();
});
textInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        sendTextCommand();
    }
});

// Control Panel Logic
const modeBtns = document.querySelectorAll('.mode-btn');
modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            appendMessage('SYSTEM', '⚠️ Backend is Offline! Please start server.py to enable Camera & Voice modes.');
            return;
        }
        
        const mode = btn.dataset.mode;
        ws.send(JSON.stringify({
            command: "SET_MODE",
            mode: mode
        }));

        modeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

const dictateToggle = document.getElementById('dictate-toggle');
const meetingToggle = document.getElementById('meeting-toggle');
const devModeToggle = document.getElementById('dev-mode-btn');
const devModeConfig = document.getElementById('dev-mode-config');
const studentModeToggle = document.getElementById('student-mode-btn');
const studentModeConfig = document.getElementById('student-mode-config');

if (devModeToggle && devModeConfig) {
    devModeToggle.addEventListener('click', () => {
        devModeToggle.classList.toggle('active');
        if (devModeToggle.classList.contains('active')) {
            devModeConfig.style.display = 'flex';
            // Auto-disable Student Mode if turning on Dev Mode
            if(studentModeToggle) { studentModeToggle.classList.remove('active'); studentModeConfig.style.display = 'none'; }
        } else {
            devModeConfig.style.display = 'none';
        }
    });
}

if (studentModeToggle && studentModeConfig) {
    studentModeToggle.addEventListener('click', () => {
        studentModeToggle.classList.toggle('active');
        if (studentModeToggle.classList.contains('active')) {
            studentModeConfig.style.display = 'flex';
            // Auto-disable Dev Mode if turning on Student Mode
            if(devModeToggle) { devModeToggle.classList.remove('active'); devModeConfig.style.display = 'none'; }
        } else {
            studentModeConfig.style.display = 'none';
        }
    });
}

let isDictating = false;
let isMeeting = false;

if (dictateToggle) {
    dictateToggle.addEventListener('click', () => {
        isDictating = !isDictating;
        dictateToggle.classList.toggle('active', isDictating);
        if(ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: "TOGGLE_DICTATION", state: isDictating }));
            appendMessage('SYSTEM', isDictating ? 'Dictation Mode ON. Voice input will be typed directly.' : 'Dictation Mode OFF.');
        }
    });
}

if (meetingToggle) {
    meetingToggle.addEventListener('click', () => {
        isMeeting = !isMeeting;
        meetingToggle.classList.toggle('active', isMeeting);
        if(ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: "TOGGLE_MEETING", state: isMeeting }));
            if (isMeeting) {
                appendMessage('SYSTEM', 'Meeting Summarizer Started. Recording background audio...');
            } else {
                appendMessage('SYSTEM', 'Meeting Ended. Transcribing and Summarizing (this may take a few minutes)...');
            }
        }
    });
}

// Quick Action Buttons
const actionBtns = document.querySelectorAll('.action-btn');
actionBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        if (btn.classList.contains('macro-btn')) return; // Prevent double-firing
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        const cmd = btn.dataset.cmd;
        appendMessage('USER', cmd);
        lastVoiceText = cmd;
        ws.send(JSON.stringify({
            command: "TEXT_INPUT",
            text: cmd
        }));
    });
});

// Background Selection
const bgDropdown = document.getElementById('bg-dropdown');
const bgSelectedText = document.getElementById('bg-selected-text');
const bgImage = document.getElementById('bg-image');
const bgVideo = document.getElementById('bg-video');

if (bgDropdown && bgImage && bgVideo) {
    const options = bgDropdown.querySelectorAll('.custom-dropdown-option');
    options.forEach(opt => {
        opt.addEventListener('click', () => {
            bgSelectedText.textContent = opt.textContent;
            const value = opt.dataset.value;
            const pipeIdx = value.indexOf('|');
            const type = value.substring(0, pipeIdx);
            const url = value.substring(pipeIdx + 1);
            
            if (type === 'image') {
                bgVideo.style.display = 'none';
                bgImage.style.display = 'block';
                bgImage.style.background = `url('${url}') center/cover no-repeat`;
                if (bgVideo.pause) bgVideo.pause();
            } else if (type === 'gradient') {
                bgVideo.style.display = 'none';
                bgImage.style.display = 'block';
                bgImage.style.background = url;
                if (bgVideo.pause) bgVideo.pause();
            } else if (type === 'video') {
                bgImage.style.display = 'none';
                bgVideo.style.display = 'block';
                const source = bgVideo.querySelector('source');
                if (source) {
                    source.src = url;
                    bgVideo.load();
                    bgVideo.play();
                }
            }
        });
    });
}

// Global Custom Dropdown Logic
document.addEventListener('click', (e) => {
    const isDropdownClick = e.target.closest('.custom-dropdown');
    document.querySelectorAll('.custom-dropdown').forEach(dropdown => {
        if (dropdown === isDropdownClick) {
            dropdown.classList.toggle('open');
        } else {
            dropdown.classList.remove('open');
        }
    });
});

// Start connection
connectWebSocket();

// Sidebar Toggle Logic
const sidebarToggle = document.getElementById('sidebar-toggle');
const quickActionsPanel = document.getElementById('quick-actions-panel');

const modesSidebarToggle = document.getElementById('modes-sidebar-toggle');
const modesPanel = document.getElementById('modes-panel');

if (sidebarToggle) {
    const historyDrawer = document.getElementById('chat-history-drawer');
    sidebarToggle.addEventListener('click', () => {
        if (historyDrawer) {
            historyDrawer.classList.toggle('open');
        }
    });
}
const qaToggleBtn = document.getElementById('qa-toggle-btn');
const quickActions = document.getElementById('quick-actions-panel');
if (qaToggleBtn && quickActions) {
    qaToggleBtn.addEventListener('click', () => {
        quickActions.classList.toggle('collapsed');
        qaToggleBtn.innerHTML = quickActions.classList.contains('collapsed') ? '<i class="fa-solid fa-chevron-right"></i>' : '<i class="fa-solid fa-chevron-left"></i>';
    });
}

const historyCloseBtn = document.getElementById('history-close-btn');
if (historyCloseBtn) {
    const historyDrawer = document.getElementById('chat-history-drawer');
    historyCloseBtn.addEventListener('click', () => {
        if (historyDrawer) {
            historyDrawer.classList.remove('open');
        }
    });
}

if (modesSidebarToggle && modesPanel) {
    modesSidebarToggle.addEventListener('click', () => {
        modesPanel.classList.toggle('collapsed');
    });
}
    
// Auto open/close based on window size
function checkWindowSize() {
    if (window.innerWidth >= 1200) {
        if(quickActionsPanel) quickActionsPanel.classList.remove('collapsed');
        if(modesPanel) modesPanel.classList.remove('collapsed');
    } else {
        if(quickActionsPanel) quickActionsPanel.classList.add('collapsed');
        if(modesPanel) modesPanel.classList.add('collapsed');
    }
}

window.addEventListener('resize', checkWindowSize);
// Initial check
checkWindowSize();

// Accordion Logic
const groupHeaders = document.querySelectorAll('.group-header');
groupHeaders.forEach(header => {
    header.addEventListener('click', () => {
        header.classList.toggle('collapsed');
        const content = header.nextElementSibling;
        if (content && content.classList.contains('accordion-content')) {
            content.classList.toggle('collapsed');
        }
    });
});

// Settings Modal Logic
const settingsToggle = document.getElementById('settings-toggle');
const topSettingsBtn = document.getElementById('top-settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');

if (settingsModal) {
    if (settingsToggle) {
        settingsToggle.addEventListener('click', () => {
            settingsModal.classList.add('active');
        });
    }
    if (topSettingsBtn) {
        topSettingsBtn.addEventListener('click', () => {
            settingsModal.classList.add('active');
        });
    }
    
    if (closeSettingsBtn) {
        closeSettingsBtn.addEventListener('click', () => {
            settingsModal.classList.remove('active');
        });
    }
    
    // Close on click outside
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.remove('active');
        }
    });
}

// Right Context Sidebar Toggle Logic
const contextToggleBtn = document.getElementById('context-toggle-btn');
const contextSidebar = document.getElementById('context-sidebar');
if (contextToggleBtn && contextSidebar) {
    contextToggleBtn.addEventListener('click', () => {
        contextSidebar.classList.toggle('collapsed');
    });
}

// Workspace Selector Logic
const workspaceDropdown = document.getElementById('workspace-dropdown');
if (workspaceDropdown) {
    const options = workspaceDropdown.querySelectorAll('.custom-dropdown-option');
    const selectedText = document.getElementById('workspace-text');
    options.forEach(opt => {
        opt.addEventListener('click', (e) => {
            selectedText.textContent = e.target.textContent;
            appendMessage('SYSTEM', `Switched workspace to: ${e.target.textContent}`);
        });
    });
}

// Terminal Toggle
const terminalToggleBtn = document.getElementById('terminal-toggle');
const terminalPanel = document.getElementById('terminal-panel');
if (terminalToggleBtn && terminalPanel) {
    terminalToggleBtn.addEventListener('click', () => {
        terminalPanel.classList.toggle('open');
    });
}

function logToTerminal(msg, type='info') {
    if (!terminalPanel) return;
    const output = document.getElementById('terminal-output');
    const div = document.createElement('div');
    div.className = `term-line ${type}`;
    div.textContent = `> ${msg}`;
    output.appendChild(div);
    output.scrollTop = output.scrollHeight;
}

// Mock System Metrics & Tokens
let tokenCount = 4024;
setInterval(() => {
    // CPU/RAM
    const cpuVal = document.getElementById('cpu-val');
    const cpuBar = document.getElementById('cpu-bar');
    const ramVal = document.getElementById('ram-val');
    const ramBar = document.getElementById('ram-bar');
    if (cpuVal && cpuBar) {
        const cpu = Math.floor(Math.random() * 30) + 5;
        cpuVal.textContent = `${cpu}%`;
        cpuBar.style.width = `${cpu}%`;
    }
    if (ramVal && ramBar) {
        const ram = (Math.random() * 1.5 + 7.5).toFixed(1);
        ramVal.textContent = `${ram}GB`;
        ramBar.style.width = `${(ram / 32) * 100}%`;
    }
    
    // Tokens
    const tokenFill = document.getElementById('token-bar-fill');
    const tokenText = document.getElementById('token-count-text');
    if (tokenFill && tokenText) {
        tokenCount += Math.floor(Math.random() * 10);
        const percent = ((tokenCount / 128000) * 100).toFixed(1);
        tokenText.textContent = `${tokenCount.toLocaleString()} / 128,000 (${percent}%)`;
        tokenFill.style.width = `${percent}%`;
    }
}, 2500);

// Slash Commands Logic
const commandInput = document.getElementById('text-command-input');
const slashMenu = document.getElementById('slash-menu');
if (commandInput && slashMenu) {
    const slashItems = slashMenu.querySelectorAll('.slash-item');
    commandInput.addEventListener('input', (e) => {
        const val = e.target.value;
        if (val.startsWith('/')) {
            slashMenu.classList.add('active');
            const search = val.toLowerCase();
            slashItems.forEach(item => {
                const cmd = item.getAttribute('data-val');
                if (cmd.startsWith(search)) item.style.display = 'flex';
                else item.style.display = 'none';
            });
        } else {
            slashMenu.classList.remove('active');
        }
    });
    
    slashItems.forEach(item => {
        item.addEventListener('click', () => {
            commandInput.value = item.getAttribute('data-val') + " ";
            slashMenu.classList.remove('active');
            commandInput.focus();
        });
    });
}

// Macro Buttons Logic
const macroBtns = document.querySelectorAll('.macro-btn');
const macroProgress = document.getElementById('macro-progress');
const macroProgressText = document.getElementById('macro-progress-text');

macroBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const cmd = btn.getAttribute('data-cmd');
        if (ws && ws.readyState === WebSocket.OPEN) {
            appendMessage('USER', cmd);
            lastVoiceText = cmd;
            
            ws.send(JSON.stringify({
                command: "TEXT_INPUT",
                text: cmd
            }));
        } else {
            appendMessage('SYSTEM', 'Cannot execute macro: Disconnected from server.');
        }
        logToTerminal(`Sending macro to backend: ${cmd}`, 'info');
    });
});

// Mode Switching Logic
const devModeBtn = document.getElementById('dev-mode-btn');
const studentModeBtn = document.getElementById('student-mode-btn');
const devToolsContainer = document.getElementById('developer-tools-container');
const studentToolsContainer = document.getElementById('student-tools-container');

if (devModeBtn && devToolsContainer) {
    devModeBtn.addEventListener('click', () => {
        devToolsContainer.style.display = 'block';
        studentToolsContainer.style.display = 'none';
        appendMessage('SYSTEM', 'Switched to Developer Mode.');
    });
}
if (studentModeBtn && studentToolsContainer) {
    studentModeBtn.addEventListener('click', () => {
        devToolsContainer.style.display = 'none';
        studentToolsContainer.style.display = 'block';
        appendMessage('SYSTEM', 'Switched to Student Focus Mode. Ready to study!');
    });
}

// Chat History Logic & Dynamic Drawer Renderer
function updateHistoryDrawer(history) {
    const historyContent = document.getElementById('history-content');
    if (!historyContent) return;

    historyContent.innerHTML = "";

    if (!history || history.length === 0) {
        historyContent.innerHTML = '<div style="padding: 24px; color: rgba(255,255,255,0.4); text-align: center; font-size: 0.85rem;">No saved chats</div>';
        return;
    }

    // Extract user prompts for session items
    const userPrompts = history.filter(h => h.sender === 'USER');
    if (userPrompts.length === 0) {
        historyContent.innerHTML = '<div style="padding: 24px; color: rgba(255,255,255,0.4); text-align: center; font-size: 0.85rem;">No saved chats</div>';
        return;
    }

    const groupDiv = document.createElement('div');
    groupDiv.className = 'history-group';
    groupDiv.innerHTML = '<div class="history-group-title">Recent Conversations</div>';

    // Show last 10 user chat prompts
    userPrompts.slice(-10).reverse().forEach((item, idx) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = `history-item ${idx === 0 ? 'active' : ''}`;
        
        const cleanTitle = item.text.replace(/\[IMAGE_ATTACHED:.*?\]/g, '').trim();
        itemDiv.innerHTML = `
            <div style="flex:1; display:flex; align-items:center; gap:10px; overflow:hidden;">
                <i class="fa-regular fa-message"></i> 
                <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${cleanTitle}">${cleanTitle}</span>
            </div>
            <i class="fa-solid fa-trash-can delete-chat-btn" title="Delete History"></i>
        `;
        groupDiv.appendChild(itemDiv);
    });

    historyContent.appendChild(groupDiv);
}

const newChatBtn = document.querySelector('.new-chat-btn');
if (newChatBtn) {
    newChatBtn.addEventListener('click', () => {
        chatLog.innerHTML = '';
        lastVoiceText = '';
        lastReplyText = '';

        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: "CLEAR_HISTORY" }));
        }

        const usageBar = document.querySelector('.context-usage-bar-fill');
        const usageText = document.querySelector('.context-usage-text');
        if (usageBar) usageBar.style.width = '0%';
        if (usageText) usageText.textContent = '0 / 128,000 (0%)';
        
        updateHistoryDrawer([]);
        appendMessage('SYSTEM', 'Started a fresh conversation. How can I help you today?');
        
        const historyDrawer = document.getElementById('chat-history-drawer');
        if (historyDrawer) historyDrawer.classList.remove('open');
    });
}

const historyContent = document.getElementById('history-content');
if (historyContent) {
    historyContent.addEventListener('click', (e) => {
        const deleteBtn = e.target.closest('.delete-chat-btn');
        if (deleteBtn) {
            e.stopPropagation();
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ command: "CLEAR_HISTORY" }));
            }
            chatLog.innerHTML = '';
            lastVoiceText = '';
            lastReplyText = '';
            updateHistoryDrawer([]);
            appendMessage('SYSTEM', 'Chat history deleted.');
        }
    });
}

// Settings Sync Logic
function syncSettings() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        const headlessToggle = document.getElementById('headless-mode-toggle');
        const userContext = document.getElementById('user-context-input');
        
        ws.send(JSON.stringify({
            command: "UPDATE_SETTINGS",
            settings: {
                headlessMode: headlessToggle ? headlessToggle.checked : true,
                userContext: userContext ? userContext.value : ""
            }
        }));
    }
}

const headlessModeToggle = document.getElementById('headless-mode-toggle');
if (headlessModeToggle) {
    headlessModeToggle.addEventListener('change', syncSettings);
}
const userContextInput = document.getElementById('user-context-input');
if (userContextInput) {
    userContextInput.addEventListener('change', syncSettings);
}
