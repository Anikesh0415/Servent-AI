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
    
    // Set selected voice
    const voiceSelectedText = document.getElementById('voice-selected-text');
    const selectedVoiceName = voiceSelectedText ? (voiceSelectedText.dataset.value || voiceSelectedText.textContent) : null;
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
        
        if (data.type === "CHAT_HISTORY") {
            chatLog.innerHTML = ""; // Clear existing log
            
            if (data.history.length === 0) {
                const hour = new Date().getHours();
                let greeting = "Good evening";
                if (hour < 12) greeting = "Good morning";
                else if (hour < 17) greeting = "Good afternoon";
                
                appendMessage('SYSTEM', `${greeting}, Developer! System is online and ready.`);
            } else {
                data.history.forEach(msg => {
                    appendMessage(msg.sender, msg.text);
                });
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
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');

if (settingsToggle && settingsModal) {
    settingsToggle.addEventListener('click', () => {
        settingsModal.classList.add('active');
    });
    
    closeSettingsBtn.addEventListener('click', () => {
        settingsModal.classList.remove('active');
    });
    
    // Close on click outside
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.remove('active');
        }
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
        
        if (cmd === "generate-snippet") {
            const snippetHtml = `
            <div class="code-snippet">
                <div class="code-header">
                    <span>utils.js</span>
                    <button class="copy-btn"><i class="fa-regular fa-copy"></i> Copy</button>
                </div>
                <pre class="code-body"><span class="token-keyword">export function</span> <span class="token-function">calculateEntropy</span>(data) {
    <span class="token-keyword">let</span> entropy = 0;
    <span class="token-keyword">for</span> (<span class="token-keyword">const</span> key <span class="token-keyword">in</span> data) {
        <span class="token-keyword">const</span> p = data[key];
        entropy -= p * Math.<span class="token-function">log2</span>(p);
    }
    <span class="token-keyword">return</span> entropy;
}</pre>
            </div>`;
            
            const msgDiv = document.createElement('div');
            msgDiv.className = `message system-msg`;
            msgDiv.innerHTML = `<div class="msg-bubble" style="padding:0; background:transparent; border:none; box-shadow:none;">${snippetHtml}</div>`;
            document.getElementById('chat-log').appendChild(msgDiv);
            document.getElementById('chat-log').scrollTop = document.getElementById('chat-log').scrollHeight;
            return;
        }

        if (cmd === "generate-flashcard") {
            const fcHtml = `
            <div class="flashcard-container">
                <div class="flashcard" onclick="this.classList.toggle('flipped')">
                    <div class="flashcard-front">
                        <div class="flashcard-title">Front</div>
                        <div class="flashcard-content">What is the powerhouse of the cell?</div>
                        <div class="flashcard-hint">Click to flip</div>
                    </div>
                    <div class="flashcard-back">
                        <div class="flashcard-title">Back</div>
                        <div class="flashcard-content">Mitochondria</div>
                        <div class="flashcard-hint">Click to flip back</div>
                    </div>
                </div>
            </div>`;
            const msgDiv = document.createElement('div');
            msgDiv.className = `message system-msg`;
            msgDiv.innerHTML = `<div class="msg-bubble" style="padding:0; background:transparent; border:none; box-shadow:none;">${fcHtml}</div>`;
            document.getElementById('chat-log').appendChild(msgDiv);
            document.getElementById('chat-log').scrollTop = document.getElementById('chat-log').scrollHeight;
            return;
        }

        if (cmd === "generate-handwritten") {
            const hwHtml = `
            <div style="background: #fdf6e3; padding: 20px; border-radius: 4px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); font-family: 'Comic Sans MS', cursive, sans-serif; color: #2c3e50; line-height: 1.6; position: relative; max-width: 400px; margin: 16px 0;">
                <div style="position: absolute; top: 0; left: 40px; bottom: 0; width: 2px; background: rgba(255,0,0,0.2);"></div>
                <div style="padding-left: 30px;">
                    <div style="text-align: right; font-size: 0.8rem; margin-bottom: 10px; color: #34495e;">Name: Balram<br>Date: Oct 12</div>
                    <h3 style="margin-top: 0; text-decoration: underline; font-size: 1.2rem;">Photosynthesis Project</h3>
                    <p style="font-size: 0.95rem;">Photosynthesis is the process by which green plants and some other organisms use sunlight to synthesize foods from carbon dioxide and water. Photosynthesis in plants generally involves the green pigment chlorophyll and generates oxygen as a byproduct.</p>
                </div>
            </div>`;
            const msgDiv = document.createElement('div');
            msgDiv.className = `message system-msg`;
            msgDiv.innerHTML = `<div class="msg-bubble" style="padding:0; background:transparent; border:none; box-shadow:none;">${hwHtml}</div>`;
            document.getElementById('chat-log').appendChild(msgDiv);
            document.getElementById('chat-log').scrollTop = document.getElementById('chat-log').scrollHeight;
            return;
        }

        if (macroProgress) {
            macroProgress.classList.add('active');
            let steps = ["Initializing automation...", "Executing tasks...", "Finalizing..."];
            let stepIdx = 0;
            macroProgressText.textContent = steps[stepIdx];
            
            const interval = setInterval(() => {
                stepIdx++;
                if (stepIdx < steps.length) {
                    macroProgressText.textContent = steps[stepIdx];
                } else {
                    clearInterval(interval);
                    macroProgress.classList.remove('active');
                    appendMessage('SYSTEM', `Automation Complete: ${cmd}`);
                    logToTerminal(`Execution finished with exit code 0`, 'info');
                }
            }, 1000);
        }
        logToTerminal(`Running macro: ${cmd}`, 'info');
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
