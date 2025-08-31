// --- PocketFreud chat.js (no browser STT; mic handled by stt.js) ---

const chatBox = document.getElementById("chatBox");
let memoryMessages = [];
const DEMO_LIMIT = 12;
let pendingRestore = null;
let moreJustOpened = false;
let availableVoices = [];
let speechEnabled = false;
let APP_CONFIG = {};

// Add Enter/Return key support for sending chat (top-level, always active)
const userInputField = document.getElementById("userInput");
if (userInputField) {
  userInputField.addEventListener("keydown", function(event) {
    if ((event.key === "Enter" || event.key === "Return") && !event.shiftKey) {
      event.preventDefault();
      if (!userInputField.disabled) {
        sendChatMessage();
      }
    }
  });
}

// ---- safety shims (must be before any use of `settings`) ----
if (typeof window === 'object' && typeof window.settings === 'undefined') {
  window.settings = {};
}
// convenience accessor for settings with safe fallback
const S = () => (window.settings || {});

// -------------------------------------

function closeModal() {
  document.getElementById('confirmModal')?.classList.remove('show');
  pendingRestore = null;
}

function startNewChat() {
  if (typeof IS_CASUAL !== 'undefined' && IS_CASUAL) {
    memoryMessages = [];
    location.reload();
    return;
  }
}

// -------- Native-first TTS (Capacitor) with web fallback --------
const isNative = () => {
  try {
    return !!(window.Capacitor?.getPlatform && ['ios','android'].includes(window.Capacitor.getPlatform()));
  } catch { return false; }
};

// Web-voices only for desktop
function loadVoices() {
  if (isNative()) return;
  if (typeof speechSynthesis === 'undefined') return;
  availableVoices = speechSynthesis.getVoices?.() || [];
  if (availableVoices.length === 0) {
    speechSynthesis.addEventListener("voiceschanged", () => {
      availableVoices = speechSynthesis.getVoices?.() || [];
    }, { once: true });
  }
}
loadVoices();

async function stopSpeaking() {
  if (isNative() && window.Capacitor?.Plugins?.TextToSpeech?.stop) {
    try { await window.Capacitor.Plugins.TextToSpeech.stop(); } catch {}
  } else if (typeof speechSynthesis !== 'undefined') {
    try { speechSynthesis.cancel(); } catch {}
  }
}

async function toggleSpeech() {
  speechEnabled = !speechEnabled;
  const btn  = document.getElementById("speechToggleBtn");
  const icon = btn?.querySelector("img");
  btn?.classList.toggle("active", speechEnabled);
  btn?.setAttribute("aria-label", speechEnabled ? "Speech Enabled" : "Speech Disabled");
  if (icon && typeof ICON_DIR !== 'undefined') icon.src = ICON_DIR + "speaking.png";

  if (!speechEnabled) {
    await stopSpeaking();
    await speakText("Speech disabled", { force: true });
  } else {
    await speakText("Speech enabled", { force: true });
  }
}

function webSpeak(text) {
  try {
    if (typeof speechSynthesis === 'undefined') return;
    speechSynthesis.cancel?.();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang  = S().voice_lang  || "en-GB";
    utter.rate  = (S().voice_rate  ?? 0.95);
    utter.pitch = (S().voice_pitch ?? 1.05);
    const idx = document.getElementById("voiceSelect")?.value;
    if (availableVoices[idx]) utter.voice = availableVoices[idx];
    speechSynthesis.speak(utter);
  } catch {}
}

async function speakText(text, opts = {}) {
  const { force = false } = opts;
  if (!force && !speechEnabled) return;
  if (!text) return;

  const TTS = window.Capacitor?.Plugins?.TextToSpeech;

  if (isNative() && TTS) {
    const lang  = S().voice_lang  || "en-GB";
    const rate  = (S().voice_rate  ?? 0.95); // 0.1..2.0
    const pitch = (S().voice_pitch ?? 1.05); // 0.5..2.0
    try {
      await TTS.stop?.(); // flush any queued speech
      await TTS.speak({
        text, lang, rate, pitch, volume: 1.0,
        category: "playback" // iOS: route to speaker
      });
      return;
    } catch (e) {
      console.warn("Native TTS failed, falling back to web:", e);
    }
  }

  // Desktop web fallback
  webSpeak(text);
}

// (Optional) helper to open system TTS settings (Android supports this)
async function installBetterVoices() {
  const TTS = window.Capacitor?.Plugins?.TextToSpeech;
  if (isNative() && TTS?.openInstall) {
    try { await TTS.openInstall(); } catch {}
  }
}

function openSuggestions() {
  fetch(SUGGESTIONS_URL)
    .then(res => res.json())
    .then(data => {
      const list = document.getElementById('suggestionsList');
      if (!list) return;
      list.innerHTML = '';
      data.forEach(prompt => {
        const li = document.createElement('li');
        li.textContent = prompt;
        li.onclick = () => {
          document.getElementById('userInput').value = prompt;
          closeSuggestions();
        };
        list.appendChild(li);
      });
      document.getElementById('suggestionsModal')?.classList.add('show');
    });
}

function toggleMoreMenu() {
  const menu = document.getElementById('moreMenu');
  const isVisible = menu?.classList.contains('show');
  if (!menu) return;

  if (!isVisible) {
    menu.classList.add('show');
    moreJustOpened = true;
    setTimeout(() => { moreJustOpened = false; }, 200);
  } else {
    menu.classList.remove('show');
  }
}

window.addEventListener('click', (e) => {
  const menu = document.getElementById('moreMenu');
  const button = document.querySelector('.more-button');
  if (menu && button && !button.contains(e.target) && !moreJustOpened) {
    menu.classList.remove('show');
  }
});

function closeSuggestions() {
  document.getElementById('suggestionsModal')?.classList.remove('show');
}

function deleteModal() {
  document.getElementById('deleteConfirmModal')?.classList.add('show');
}

function closeDeleteModal() {
  document.getElementById('deleteConfirmModal')?.classList.remove('show');
}

async function confirmDelete() {
  closeDeleteModal();
  closeModal();

  await fetch('/api/delete_chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });

  chatBox.innerHTML = '';
  const welcome = document.createElement('div');
  welcome.className = 'bot-message';
  welcome.innerHTML = `<strong>PocketFreud:</strong> Hi, how are you feeling today?`;
  chatBox.appendChild(welcome);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendChatMessage() {
  const inputField = document.getElementById("userInput");
  if (inputField.disabled) return;

  const userText = inputField.value.trim();
  if (!userText) return;

  setInputDisabled(true);
  inputField.value = "";

  const userMessageDiv = document.createElement("div");
  userMessageDiv.className = "user-message";
  userMessageDiv.innerHTML = `<strong>You:</strong> ${userText}`;
  chatBox.appendChild(userMessageDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  const typingDiv = document.createElement("div");
  typingDiv.className = "bot-message thinking";
  typingDiv.innerHTML = `<strong>PocketFreud</strong> is thinking`;
  chatBox.appendChild(typingDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  let endpoint = IS_CASUAL ? "/api/casual_chat" : "/api/chat";

  let payload;
  if (IS_CASUAL) {
    memoryMessages.push({ role: "user", content: userText });
    payload = {
      messages: memoryMessages,
      session_name: CURRENT_SESSION_NAME,
      session_type: CURRENT_SESSION_TYPE
    };
  } else {
    payload = {
      messages: [{ role: "user", content: userText }],
      session_name: CURRENT_SESSION_NAME,
      session_type: CURRENT_SESSION_TYPE
    };
  }

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) throw new Error(`Server error: ${response.status}`);
    const data = await response.json();
    if (chatBox.contains(typingDiv)) chatBox.removeChild(typingDiv);

    const botReplies = data.responses || [data.response];
    const typing_delay = (S().typing_delay) || 50;
    let hasAnimatedReply = false;

    botReplies.forEach((reply, idx) => {
      const botDiv = document.createElement("div");
      botDiv.className = "bot-message";
      botDiv.innerHTML = `<strong>PocketFreud:</strong> `;
      chatBox.appendChild(botDiv);

      if (idx < botReplies.length - 1) {
        if (reply.toLowerCase().includes("if you're in crisis")) {
          if (localStorage.getItem("crisis_dismissed") === "true") return;

          botDiv.classList.add("crisis-message");

          // Dismiss button
          const dismissBtn = document.createElement("button");
          dismissBtn.innerHTML = "✖";
          dismissBtn.className = "crisis-dismiss";
          dismissBtn.onclick = () => {
            botDiv.remove();
            localStorage.setItem("crisis_dismissed", "true");
          };
          botDiv.appendChild(dismissBtn);

          // Extract phone number
          const phoneMatch = reply.match(/(\+?\d[\d\s\-().]{7,})/);
          if (phoneMatch) {
            const telLink = phoneMatch[1].replace(/\s+/g, '');
            botDiv.innerHTML += `
              ⚠️ ${reply}<br>
              <a href="tel:${telLink}" class="crisis-call-link">📞 Tap to call: ${phoneMatch[1]}</a>
            `;
          } else {
            botDiv.innerHTML += `⚠️ ${reply}`;
          }
        } else {
          botDiv.innerHTML += reply;
        }
      } else {
        // Animate the final reply
        hasAnimatedReply = true;
  speakText(reply);
        const words = reply.split(" ");
        let i = 0;
        const interval = setInterval(() => {
          if (i < words.length) {
            botDiv.innerHTML += words[i] + " ";
            i++;
            chatBox.scrollTop = chatBox.scrollHeight;
          } else {
            clearInterval(interval);
            setInputDisabled(false);
          }
        }, typing_delay);

        if (IS_CASUAL) {
          memoryMessages.push({ role: "assistant", content: reply });
        }
      }
    });

    if (!hasAnimatedReply) {
      setInputDisabled(false);
    }

    inputField.value = "";
  } catch (err) {
    if (chatBox.contains(typingDiv)) chatBox.removeChild(typingDiv);
    const errorDiv = document.createElement("div");
    errorDiv.className = "bot-message";
    errorDiv.innerHTML = `<strong>Error:</strong> ${err.message}`;
    chatBox.appendChild(errorDiv);
    setInputDisabled(false);
  }
}

// ---- Session rename ----
function renameTherapySession() {
  const inputField = document.getElementById("renameSessionInput");
  inputField.value = CURRENT_SESSION_NAME;
  document.getElementById("renameSessionModal").classList.add("show");
  inputField.focus();
  inputField.select();
}

function closeRenameModal() {
  document.getElementById("renameSessionModal").classList.remove('show');
}

function submitRenameSession() {
  const newName = document.getElementById("renameSessionInput").value.trim();
  if (!newName || newName === CURRENT_SESSION_NAME) {
    closeRenameModal();
    return;
  }

  fetch("/api/rename_session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      old_name: CURRENT_SESSION_NAME,
      new_name: newName
    })
  }).then(res => {
    if (res.ok) {
      // ensure we can reassign even if the template declared it const
      try { CURRENT_SESSION_NAME = newName; } catch { window.CURRENT_SESSION_NAME = newName; }
      document.querySelector(".chat-title").textContent = `${newName} (${CURRENT_SESSION_TYPE})`;
      closeRenameModal();
    } else {
      alert("Rename failed.");
    }
  }).catch(err => {
    console.error("Error renaming session:", err);
    alert("Something went wrong.");
  });
}

// ---- Persona change ----
function changePersona() {
  fetch("/api/session_types")
    .then(res => res.json())
    .then(types => {
      const dropdown = document.getElementById("therapyTypeSelect");
      dropdown.innerHTML = "";
      types.forEach(type => {
        if (type.toLowerCase() !== "demo" && type.toLowerCase() !== "casual") {
          const opt = document.createElement("option");
          opt.value = type;
          opt.textContent = type;
          dropdown.appendChild(opt);
          if (type.toLowerCase() === "cbt") opt.selected = true;
        }
      });

      document.getElementById("changePersonaModal").classList.add("show");
    })
    .catch(error => {
      alert("Failed to load session types: " + error.message);
    });
}

function closeChangePersonaModal() {
  document.getElementById("changePersonaModal").style.display = "none";
}

function submitChangePersona() {
  const selectedType = document.getElementById("therapyTypeSelect").value;

  fetch('/change_persona', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      current_session_name: CURRENT_SESSION_NAME,
      persona: selectedType
    })
  })
  .then(res => {
    if (res.ok) {
      try { CURRENT_SESSION_TYPE = selectedType; } catch { window.CURRENT_SESSION_TYPE = selectedType; }
      document.querySelector(".chat-title").textContent =
        `${CURRENT_SESSION_NAME} (${CURRENT_SESSION_TYPE})`;
      closeChangePersonaModal();
    } else {
      alert("Failed to update therapy style.");
    }
  });
}

// ---- Helpers ----
function setInputDisabled(disabled) {
  const inputField = document.getElementById("userInput");
  const sendButtons = document.querySelectorAll('.icon-button');

  inputField.disabled = disabled;
  inputField.placeholder = disabled ? "PocketFreud is typing..." : "Type something...";
  inputField.style.opacity = disabled ? "0.6" : "1";

  // Only disable the send button
  sendButtons.forEach(button => {
    const img = button.querySelector('img');
    if (img && img.alt === 'Send') {
      button.disabled = disabled;
      button.style.opacity = disabled ? "0.6" : "1";
      button.style.cursor = disabled ? "not-allowed" : "pointer";
    }
  });
}

function scrollChatToBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

// After rendering all historic messages, call scrollChatToBottom()
window.addEventListener('DOMContentLoaded', () => {
  scrollChatToBottom();
});
