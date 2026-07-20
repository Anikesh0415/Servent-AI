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

// TTS Toggle Logic
ttsToggle.addEventListener('click', () => {
    ttsEnabled = !ttsEnabled;
    if(ttsEnabled) {
        ttsToggle.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
    } else {
        ttsToggle.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
    }
});

// Load Voices
function loadVoices() {
    voices = window.speechSynthesis.getVoices();
    voiceSelect.innerHTML = '';
    
    voices.forEach((voice, i) => {
        const option = document.createElement('option');
        option.value = voice.name;
        // Prioritize female or beautiful natural voices if possible in the label
        let label = voice.name;
        if (voice.default) label += ' (Default)';
        option.textContent = label;
        voiceSelect.appendChild(option);
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
    
    // Set selected voice
    const selectedVoiceName = voiceSelect.selectedOptions[0]?.value;
    if (selectedVoiceName) {
        const voice = voices.find(v => v.name === selectedVoiceName);
        if (voice) utterance.voice = voice;
    }
    
    utterance.pitch = 1.0; // Normal human pitch
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
}

function appendMessage(sender, text) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message');
    
    if (sender === 'USER') {
        msgDiv.classList.add('user-msg');
    } else {
        msgDiv.classList.add('system-msg');
    }
    
    const bubble = document.createElement('div');
    bubble.classList.add('msg-bubble');
    bubble.textContent = text;
    msgDiv.appendChild(bubble);
    
    chatLog.appendChild(msgDiv);
    chatLog.scrollTop = chatLog.scrollHeight; 
}

function connectWebSocket() {
    ws = new WebSocket('ws://localhost:8765');

    ws.onopen = () => {
        wsStatus.textContent = 'CONNECTED';
        wsStatus.style.color = '#34c759';
        statusDot.classList.add('active');
        appendMessage('SYSTEM', 'Connection established. Servent is online.');
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
        // If server clears the text, we can reset our local tracking
        if (!data.voice_text) {
            lastVoiceText = "";
        }
        
        if (data.reply_text && data.reply_text !== lastReplyText) {
            lastReplyText = data.reply_text;
            appendMessage('SYSTEM', data.reply_text);
            speakText(data.reply_text);
        }
        if (!data.reply_text) {
            lastReplyText = '';
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
        setTimeout(connectWebSocket, reconnectInterval);
    };
}

function updateState(stateName) {
    sysState.textContent = stateName;
    const confirmWrapper = document.getElementById('confirmation-wrapper');
    const inputWrapper = document.getElementById('input-wrapper');
    if (confirmWrapper && inputWrapper) {
        if (stateName === 'AWAITING_CONFIRMATION') {
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
        // Dev Mode / Student Mode Injection
        const devToggle = document.getElementById('dev-mode-toggle');
        const studentToggle = document.getElementById('student-mode-toggle');
        
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
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        
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
const devModeToggle = document.getElementById('dev-mode-toggle');
const devModeConfig = document.getElementById('dev-mode-config');
const studentModeToggle = document.getElementById('student-mode-toggle');
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
const bgSelect = document.getElementById('bg-select');
const bgImage = document.getElementById('bg-image');
const bgVideo = document.getElementById('bg-video');

if (bgSelect && bgImage && bgVideo) {
    bgSelect.addEventListener('change', (e) => {
        const value = e.target.value;
        const [type, url] = value.split('|');
        
        if (type === 'image') {
            bgVideo.style.display = 'none';
            bgImage.style.display = 'block';
            bgImage.style.backgroundImage = `url('${url}')`;
            bgVideo.pause();
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
}

// Start connection
connectWebSocket();

// Sidebar Toggle Logic
const sidebarToggle = document.getElementById('sidebar-toggle');
const quickActionsPanel = document.getElementById('quick-actions-panel');

const modesSidebarToggle = document.getElementById('modes-sidebar-toggle');
const modesPanel = document.getElementById('modes-panel');

if (sidebarToggle && quickActionsPanel) {
    sidebarToggle.addEventListener('click', () => {
        quickActionsPanel.classList.toggle('collapsed');
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
