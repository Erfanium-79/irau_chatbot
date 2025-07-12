/**
 * Communicates with the chatbot API.
 *
 * @param {string} userMessage The message from the user.
 * @returns {Promise<string>} A promise that resolves to the chatbot's reply.
 * @throws {Error} Throws an error if the API request fails.
 */
async function getChatbotResponse(userMessage) {
  // The full URL for your deployed API endpoint
  const apiUrl = 'https://iran-australia-chatbot.onrender.com/chat/';

  try {
    const response = await fetch(apiUrl, {
      method: 'POST', // The HTTP method specified in your FastAPI code
      headers: {
        'Content-Type': 'application/json', // Specifies the format of the data we're sending
      },
      // The body of the request, which must match the Pydantic model in FastAPI
      // We convert the JavaScript object to a JSON string.
      body: JSON.stringify({
        message: userMessage
      }),
    });

    // Check if the request was successful (HTTP status code 200-299)
    if (!response.ok) {
      // If not, we throw an error to be caught by the calling code
      throw new Error(`API request failed with status ${response.status}`);
    }

    // Parse the JSON response from the server
    const data = await response.json();

    // Return the 'reply' field from the response, as defined in ChatResponse
    return data.reply;

  } catch (error) {
    // Log any errors that occur during the fetch operation
    console.error("Error communicating with the chatbot:", error);
    // You might want to return a user-friendly error message here
    return "Sorry, something went wrong. Please try again later.";
  }
}

// --- Example Usage ---
// This is how the frontend team can use the function.

const sampleMessage = "Hello, I have a question about visas.";

getChatbotResponse(sampleMessage)
  .then(reply => {
    console.log("Chatbot's reply:", reply);
    // Here, they would update the UI with the chatbot's reply
  })
  .catch(error => {
    console.error("Failed to get response:", error);
  });