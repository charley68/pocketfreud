const chatBox = document.getElementById("chatBox");
//const botTypeSelector = document.getElementById("botTypeSelector");
let demoMessages = [];
const DEMO_LIMIT = 12;
let pendingRestore = null;
let moreJustOpened = false;
let availableVoices = [];

let speechEnabled = false;

function loadVoices() {
  availableVoices = speechSynthesis.getVoices();
  if (availableVoices.length === 0) {
    speechSynthesis.addEventListener("voiceschanged", () => {
      availableVoices = speechSynthesis.getVoices();
    });
  }
}

loadVoices();

function closeModal() {
    document.getElementById('confirmModal').classList.remove('show');
    pendingRestore = null;
  }

  function startNewChat() {
    // NEW: if current chat already has a group title, skip the label modal
    if (CURRENT_GROUP_TITLE && CURRENT_GROUP_TITLE.trim() !== '') {
      fetch('/api/new_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ groupTitle: null })  // start fresh
      }).then(() => {
        location.reload();
      });
      return;
    }
  
    // Otherwise, prompt to label and archive
    document.getElementById('sessionLabel').value = '';
    document.getElementById('modalTitle').textContent = 'Label This Session?';
    document.getElementById('modalMessage').textContent = 'You can label this session to save it before starting a new one.';
    document.getElementById('confirmModalAction').textContent = 'Save & Start New';
  
    document.getElementById('confirmModalAction').onclick = () => {
      const label = document.getElementById('sessionLabel').value.trim();
      closeModal();
  
      fetch('/api/new_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ groupTitle: label || 'Untitled Chat' })
      }).then(() => {
        location.reload();
      });
    };
  
    document.getElementById('confirmModal').classList.add('show');
  }
  

  async function restoreSession(groupTitle) {
    const countRes = await fetch('/api/unlabled_message_count');
    const { count } = await countRes.json();
    if (count <= 1) {
      await performRestore(groupTitle);
    } else {
      document.getElementById('sessionLabel').value = '';
      document.getElementById('modalTitle').textContent = 'Archive Current Session?';
      document.getElementById('modalMessage').textContent = 'Do you want to give the current conversation a label so it can be restored later or discard it ?';
      document.getElementById('confirmModalAction').textContent = 'Label & Switch';
      pendingRestore = groupTitle;
      document.getElementById('confirmModalAction').onclick = async () => {
        const label = document.getElementById('sessionLabel').value.trim();
        closeModal();
        await fetch('/api/new_chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ groupTitle: label || 'Untitled' })
        });
        await performRestore(pendingRestore);
      };

      document.getElementById('confirmModal').classList.add('show');
    }
  }

  async function about() {
    console.log("Opening About modal...");
    const tokenDisplay = document.getElementById("tokenCount");
    tokenDisplay.textContent = "Loading...";
  
    // Show the modal
    document.getElementById("aboutModal").style.display = "flex";
  
    try {
      console.log("Sending fetch request to /api/token_usage...");
      const response = await fetch("/api/token_usage");
  
      console.log("Raw response received:", response);
  
      // If it's not JSON, this will throw
      const data = await response.json();
      console.log("Parsed JSON data:", data);
  
      if (response.ok) {
        tokenDisplay.textContent = `${data.month_tokens} tokens`;
        console.log("Updated token count successfully.");
      } else {
        tokenDisplay.textContent = "Unavailable";
        console.warn("Server responded with error status:", response.status);
      }
    } catch (error) {
      tokenDisplay.textContent = "Error fetching usage";
      console.error("Exception during fetch or parse:", error);
    }
  }
  
  
  


  async function performRestore(groupTitle) {
    await fetch('/api/restore_chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ restore: groupTitle })
    });
    location.reload();
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

function closeHistoryModal() {
    document.getElementById('historyModal').classList.remove('show');
  }

  function deleteModal() {
    document.getElementById('deleteConfirmModal').classList.add('show');
  }
  
  function closeDeleteModal() {
    document.getElementById('deleteConfirmModal').classList.remove('show');
  }
  
  function closeAbout() {
    document.getElementById("aboutModal").style.display = "none";
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

    let endpoint = IS_DEMO ? "/api/demo_chat" : "/api/chat";
    let payload;
  
    if (IS_DEMO) {
      demoMessages.push({ role: "user", content: userText });
      payload = { messages: demoMessages };
    } else {
      payload = {
        messages: [{ role: "user", content: userText }],
        groupTitle: CURRENT_GROUP_TITLE // if defined
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
  
      const botDiv = document.createElement("div");
      botDiv.className = "bot-message";
      botDiv.innerHTML = `<strong>PocketFreud:</strong> `;
      chatBox.appendChild(botDiv);
      speakText(data.response, botDiv);
  
      const words = data.response.split(" ");
      let i = 0;
      const interval = setInterval(() => {
        if (i < words.length) {
          botDiv.innerHTML += words[i] + " ";
          i++;
          chatBox.scrollTop = chatBox.scrollHeight;
        } else {
          clearInterval(interval);
        }
      }, 150);
  
      if (IS_DEMO) {
        demoMessages.push({ role: "assistant", content: data.response });
      }
  
      inputField.value = "";
    } catch (err) {
        if (chatBox.contains(typingMessage)) {
            chatBox.removeChild(typingMessage);
            }

      const errorDiv = document.createElement("div");
      errorDiv.className = "bot-message";
      errorDiv.innerHTML = `<strong>Error:</strong> ${err.message}`;
      chatBox.appendChild(errorDiv);
    }
  }
  
 




async function loadHistoryModal() {
    const modal = document.getElementById('historyModal');
    const tableBody = document.querySelector('#historyTable tbody');
    tableBody.innerHTML = '';

    try {
      const res = await fetch("/api/chat_history");
      const data = await res.json();

      data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${row.groupTitle}</td>
          <td>${new Date(row.latest).toLocaleString()}</td>
          <td><button onclick="restoreSession('${row.groupTitle}')">Restore</button></td>
        `;
        tableBody.appendChild(tr);
      });

      modal.classList.add('show');
    } catch (err) {
      alert('Failed to load chat history.');
    }
  }



   
  async function promptArchiveBeforeHistory() {
    document.getElementById('moreMenu')?.classList.remove('show');
  
    // NEW: skip modal if already labeled
    if (CURRENT_GROUP_TITLE && CURRENT_GROUP_TITLE.trim() !== '') {
      loadHistoryModal();
      return;
    }
  
    const countRes = await fetch(unlabledMessageCountURL);
    const { count } = await countRes.json();
  
    if (count <= 1) {
      loadHistoryModal();
    } else {
      document.getElementById('sessionLabel').value = '';
      document.getElementById('modalTitle').textContent = 'Label & Save Current Session?';
      document.getElementById('modalMessage').textContent = 'You can give this session a label before switching.';
      document.getElementById('confirmModalAction').textContent = 'Save';
  
      document.getElementById('confirmModalAction').onclick = async () => {
        const label = document.getElementById('sessionLabel').value.trim();
        closeModal();
  
        await fetch('/api/new_chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ groupTitle: label || 'Untitled Chat' })
        });
  
        loadHistoryModal();
      };
  
      document.getElementById('confirmModal').classList.add('show');
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
