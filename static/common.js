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