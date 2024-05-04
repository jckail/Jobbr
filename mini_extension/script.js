document.getElementById("sendButton").addEventListener("click", function () {
  const statusMessage = document.getElementById("statusMessage");
  statusMessage.textContent = "Sending URL..."; // Immediate feedback when button is clicked
  statusMessage.style.display = "block"; // Make sure the message is visible

  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
    const apiUrl =
      "http://127.0.0.1:8000/api/parse/stg_role?input_url=" +
      encodeURIComponent(tabs[0].url);
    fetch(apiUrl, { method: "POST" }); // Send the request

    // Optionally clear the message after a few seconds
    setTimeout(() => {
      statusMessage.textContent = "";
      statusMessage.style.display = "none"; // Hide the message
    }, 3000); // Message clears after 3 seconds
  });
});
