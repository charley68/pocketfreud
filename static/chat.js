const chatBox = document.getElementById("chatBox");
//const botTypeSelector = document.getElementById("botTypeSelector");
let memoryMessages = [];
const DEMO_LIMIT = 12;
let pendingRestore = null;
let moreJustOpened = false;
let availableVoices = [];
let speechEnabled = false;
let APP_CONFIG = {};




function loadVoices() {
  availableVoices = speechSynthesis.getVoices();
  if (availableVoices.length === 0) {
    speechSynthesis.addEventListener("voiceschanged", () => {
      availableVoices = speechSynthesis.getVoices();
    });
  }
}



function closeModal() {
    document.getElementById('confirmModal').classList.remove('show');
    pendingRestore = null;
  }

  function startNewChat() {

    if (typeof IS_CASUAL !== 'undefined' && IS_CASUAL) {
      // 🚫 No saving, just reset and reload
      memoryMessages = [];
      location.reload();
      return;
    }
  }



function openSuggestions() {
  fetch(SUGGESTIONS_URL )
    .then(res => res.json())
    .then(data => {
      const list = document.getElementById('suggestionsList');
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
      document.getElementById('suggestionsModal').classList.add('show');
    });
}

function toggleMoreMenu() {
  const menu = document.getElementById('moreMenu');
  const isVisible = menu.classList.contains('show');

  if (!isVisible) {
    menu.classList.add('show');
    moreJustOpened = true;
    setTimeout(() => { moreJustOpened = false; }, 200);
  } else {
    menu.classList.remove('show');
  }
}

window.addEventListener('click', function (e) {
  const menu = document.getElementById('moreMenu');
  const button = document.querySelector('.more-button');

  if (menu && button && !button.contains(e.target) && !moreJustOpened) {
    menu.classList.remove('show');
  }
});

function closeSuggestions() {
  document.getElementById('suggestionsModal').classList.remove('show');
}

function openDemoInfo() {
    document.getElementById('demoInfoModal').classList.add('show');
}

function closeDemoInfo() {
    document.getElementById('demoInfoModal').classList.remove('show');
}


  function deleteModal() {
    document.getElementById('deleteConfirmModal').classList.add('show');
  }
  
  function closeDeleteModal() {
    document.getElementById('deleteConfirmModal').classList.remove('show');
  }
  

  
  async function confirmDelete() {
    closeDeleteModal();
    closeModal(); // closes the label modal too
  
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
    const userText = inputField.value.trim();
    if (!userText) return;
  
    const userMessageDiv = document.createElement("div");
    userMessageDiv.className = "user-message";
    userMessageDiv.innerHTML = `<strong>You:</strong> ${userText}`;
    chatBox.appendChild(userMessageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
  
    const typingDiv = document.createElement("div");
    typingDiv.className = "bot-message";
    typingDiv.innerHTML = `<em>PocketFreud is typing...</em>`;
    chatBox.appendChild(typingDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
  
    let endpoint;
    if (IS_DEMO) {
      endpoint = "/api/demo_chat";
    } else if (IS_CASUAL) {
      endpoint = "/api/casual_chat";
    } else {
      endpoint = "/api/chat";
    }
  
    let payload;
    if (IS_DEMO || IS_CASUAL) {
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
      chatBox.removeChild(typingDiv);
  
      const botReplies = data.responses || [data.response]; // fallback for old format
      typing_delay = settings.typing_delay || 150;
  
      botReplies.forEach((reply, idx) => {
        const botDiv = document.createElement("div");
        botDiv.className = "bot-message";
        botDiv.innerHTML = `<strong>PocketFreud:</strong> `;
        chatBox.appendChild(botDiv);
  
        if (idx < botReplies.length - 1) {
          if (reply.toLowerCase().includes("if you're in crisis")) {
            if (localStorage.getItem("crisis_dismissed") === "true") {
              return; // skip rendering if already dismissed
            }
            
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

            
            botDiv.classList.add("crisis-message");
        
            // Extract phone number (basic example)
            const phoneMatch = reply.match(/(\+?\d[\d\s\-().]{7,})/);
            if (phoneMatch) {
              const telLink = phoneMatch[1].replace(/\s+/g, ''); // remove spaces
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
        }
        else {
          // Animate the final reply
          speakText(reply, botDiv);
          const words = reply.split(" ");
          let i = 0;
          interval = setInterval(() => {
            if (i < words.length) {
              botDiv.innerHTML += words[i] + " ";
              i++;
              chatBox.scrollTop = chatBox.scrollHeight;
            } else {
              clearInterval(interval);
            }
          }, typing_delay);
  
          if (IS_DEMO || IS_CASUAL) {
            memoryMessages.push({ role: "assistant", content: reply });
          }
        }
      });
  
      inputField.value = "";
    } catch (err) {
      if (chatBox.contains(typingDiv)) {
        chatBox.removeChild(typingDiv);
      }
  
      const errorDiv = document.createElement("div");
      errorDiv.className = "bot-message";
      errorDiv.innerHTML = `<strong>Error:</strong> ${err.message}`;
      chatBox.appendChild(errorDiv);
    }
  }
  
  

function toggleSpeech() {
  speechEnabled = !speechEnabled;

  const btn = document.getElementById("speechToggleBtn");
  const icon = btn.querySelector("img");
  const statusMessage = speechEnabled ? "Speech Enabled" : "Speech Disabled";

  if (speechEnabled) {
    btn.classList.add("active");
    icon.src = ICON_DIR + "speaking.png";
    btn.setAttribute("aria-label", statusMessage);
  } else {
    btn.classList.remove("active");
    icon.src = ICON_DIR + "speaking.png";
    btn.setAttribute("aria-label", statusMessage);
  }

  // Speak the status message
  const utterance = new SpeechSynthesisUtterance(statusMessage);
  speechSynthesis.speak(utterance);
}

function speakText(text) {
    if (!speechEnabled) 
        return;

    const utterance = new SpeechSynthesisUtterance(text);
    const selectedIndex = document.getElementById("voiceSelect")?.value;
    if (availableVoices[selectedIndex]) {
      utterance.voice = availableVoices[selectedIndex];
    }
    speechSynthesis.speak(utterance);
}

let recognition; // Declare recognition globally to manage its lifecycle
let isRecording = false; // Track recording state for desktop toggle

function initializeSpeechRecognition() {
  if (recognition) {
    return recognition; // Reuse the existing recognition instance
  }

  try {
    const isSpeechRecognitionSupported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;

    if (!isSpeechRecognitionSupported) {
      console.warn("Speech recognition is not supported in this browser.");
      alert("Speech recognition is not supported on your device or browser. Please try using a different browser.");
      return null;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition(); // Initialize and assign to the global variable

    recognition.lang = 'en-US'; // Set the language
    recognition.interimResults = false; // Enable interim results for real-time feedback
    recognition.continuous = true; // Enable continuous recognition

    recognition.onresult = (event) => {
      const inputField = document.getElementById("userInput");
      let transcript = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript; // Combine both interim and final results
      }

      inputField.value += transcript.trim() + ". "; // Update the input field in real-time
      console.log("Transcript:", inputField.value);
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error);
      alert("An error occurred during speech recognition: " + event.error);
    };

    console.log("Speech recognition initialized successfully.");
    return recognition;
  } catch (error) {
    console.error("Error initializing speech recognition:", error);
    alert("An unexpected error occurred while initializing speech recognition.");
    return null;
  }
}

function toggleRecording() {
  if (!recognition) {
    if (!initializeSpeechRecognition()) {
      return; // Prevent further execution if initialization fails
    }
  }

  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

function startRecording() {
  if (!recognition) {
    alert("Speech recognition is not initialized or supported in this browser.");
    return;
  }
  recognition.start();
  isRecording = true;
  console.log("Voice recognition started...");
}

function stopRecording() {
  if (!recognition || !isRecording) { // Ensure stopRecording is only called when recording is active
    return;
  }
  recognition.stop();
  isRecording = false;
  console.log("Voice recognition stopped.");
}

// Detect device type and adjust behavior
const isMobile = /Mobi|Android/i.test(navigator.userAgent);
const recordButton = document.getElementById("recordButton");

if (isMobile) {
  // Mobile: Press and hold behavior
  recordButton.addEventListener("mousedown", startRecording);
  recordButton.addEventListener("mouseup", stopRecording);
  recordButton.addEventListener("mouseleave", stopRecording); // Stop if the cursor leaves the button
} else {
  // Desktop: Toggle behavior
  recordButton.addEventListener("click", toggleRecording);
}


function renameTherapySession() {
  const inputField = document.getElementById("renameSessionInput");
  inputField.value = CURRENT_SESSION_NAME; // Set the current session name
  document.getElementById("renameSessionModal").classList.add("show"); // Show the modal
  inputField.focus(); // Focus on the input field
  inputField.select(); // Select the text so the user can type over it
}

function closeRenameModal() {
  document.getElementById("renameSessionModal").classList.remove("show");
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
      CURRENT_SESSION_NAME = newName;
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
              if (type.toLowerCase() === "cbt") {
                opt.selected = true;
              }
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
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      current_session_name: CURRENT_SESSION_NAME,
      persona: selectedType
    })
  })
  .then(res => {
    if (res.ok) {
      CURRENT_SESSION_TYPE = selectedType;
      document.querySelector(".chat-title").textContent = `${CURRENT_SESSION_NAME} (${CURRENT_SESSION_TYPE})`;
      closeChangePersonaModal();
    } else {
      alert("Failed to update therapy style.");
    }
  })
}

function closeChangePersonaModal() {
  document.getElementById("changePersonaModal").style.display = "none";
}




loadVoices();