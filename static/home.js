async function fetchDefaultSessionName() {
    const response = await fetch('/api/get-next-session-name');
    const data = await response.json();
    return data.defaultName;
}

let moreJustOpened = false;

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

  if (!button.contains(e.target) && !moreJustOpened) {
    menu.classList.remove('show');
  }
});


function logMood(mood) {
  fetch('/log_mood', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ mood: mood })
  }).then(response => {
    if (response.ok) {
      if (mood === 'happy') {
        showHappyModal();
      } else {
        showSupportModal(mood);
      }
    } else {
      alert('Something went wrong. Please try again.');
    }
  });
}

// Modal handlers
function showHappyModal() {
  document.getElementById('supportModal').classList.add('show');
}

function closeHappyModal() {
  document.getElementById('supportModal').classList.remove('show');
}

function showSupportModal(mood) {
  const modalTitle = document.querySelector('#supportModal .modal h2');
  const formattedMood = mood.charAt(0).toUpperCase() + mood.slice(1);
  modalTitle.textContent = `Your mood of ${formattedMood} has been noted in today's journal.`;

  document.getElementById('supportModal').classList.add('show');
}

function goToChat() {
  window.location.href = '/chat';
}

function goToJournal() {
  window.location.href = '/journal';
}

function comingSoon(feature) {
    alert(`${feature} is coming soon!`);
}

function closeSupportModal() {
   document.getElementById('supportModal').classList.remove('show'); // ✅ matches how it was shown
}


function openNewSessionModal() {
  fetchDefaultSessionName().then(defaultName => {
    document.getElementById("sessionNameInput").value = defaultName;
    const input = document.getElementById("sessionNameInput");
    input.value = defaultName;

    fetch("/api/session_types")
      .then(res => res.json())
      .then(types => {
        const dropdown = document.getElementById("sessionTypeSelect");
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
        document.getElementById("newSessionModal").classList.add("show");
        input.focus();
        input.select();
      });
  });
}

async function confirmNewSession() {
    const name = document.getElementById("sessionNameInput").value.trim();
    const type = document.getElementById("sessionTypeSelect").value;
    if (!name || !type) return;

    // Increment session counter only when starting a new session
    await fetch("/api/increment-session-counter", { method: "POST" });

    fetch("/api/new_session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_name: name, persona: type })
    }).then(() => {
        window.location.href = "/therapy";
    });
}

document.addEventListener("DOMContentLoaded", async () => {
  const defaultName = await fetchDefaultSessionName();
  console.log(defaultName); // Use defaultName as needed

  const therapyButton = document.getElementById("therapyButton");
  therapyButton?.addEventListener("click", async (e) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/current_session");
      const data = await res.json();

      if (data.session_name) {
        const label = document.getElementById("currentSessionLabel");
        if (label) label.textContent = data.session_name;
        document.getElementById("chooseTherapyModal").classList.add("show");
      } else {
        openNewSessionModal();
      }
    } catch (err) {
      console.error("Failed to load current session", err);
      openNewSessionModal();
    }
  });
});

function closeHistoryModal() {
  document.getElementById('historyModal').classList.remove('show');
}

function openSessionHistory() {
  loadHistoryModal();
}

async function loadHistoryModal() {
  const res = await fetch("/api/chat_history");
  const history = await res.json();

  const tbody = document.querySelector("#historyTable tbody");
  tbody.innerHTML = "";

  history.forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.session_name}</td>
      <td>${new Date(row.start_date).toLocaleString()}</td>
      <td><button onclick="restoreSession('${row.session_name}')">Restore</button></td>
      <td><button class="delete-btn" onclick="deleteSession('${row.session_name}')"><img src="/static/icons/bin.png" alt="Delete"></button>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById("historyModal").classList.add("show");
}

async function deleteSession(sessionName) {
    const modal = document.getElementById("confirmDeleteModal");
    const labelSpan = document.getElementById("sessionToDelete");
    const confirmBtn = document.getElementById("confirmDeleteBtn");
  
    labelSpan.textContent = sessionName;
    modal.classList.add("show");
  
    confirmBtn.onclick = async () => {
      try {
        const res = await fetch("/api/delete_session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_name: sessionName })
        });
  
        if (res.ok) {
          modal.classList.remove("show");
          loadHistoryModal();
        } else {
          alert("Failed to delete session");
        }
      } catch (err) {
        console.error("Error deleting session:", err);
        alert("Error deleting session");
      }
    };
  }
  

function restoreSession(label) {
  fetch("/api/restore_chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ restore: label })
  }).then(() => {
    window.location.href = "/therapy";
  });
}

function toggleTherapyHelp() {
  const helpBox = document.getElementById("typeHelp");
  if (helpBox) helpBox.classList.toggle("hidden");
}