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

  function closeAbout() {
    document.getElementById("aboutModal").style.display = "none";
  }

  function toggleMobileMenu() {
      document.getElementById('mobileMenu').classList.toggle('show');
  }

  document.addEventListener('click', function(event) {
      const menu = document.getElementById('mobileMenu');
      const hamburger = document.querySelector('.hamburger');
      
      // If menu is open and click is outside both menu and hamburger icon, close it
      if (menu.classList.contains('show') &&
          !menu.contains(event.target) &&
          !hamburger.contains(event.target)) {
        menu.classList.remove('show');
      }
});

    // Close mobile menu when a link is clicked
const menuLinks = document.querySelectorAll('.mobile-menu a');
menuLinks.forEach(link => {
    link.addEventListener('click', () => {
      document.getElementById('mobileMenu').classList.remove('show');
    });
});