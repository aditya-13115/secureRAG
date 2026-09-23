import type {
  ChatRequest,
  ChatResponse,
} from "../types";

const API_URL =
  import.meta.env.VITE_API_URL ??
  "http://127.0.0.1:8000";

export async function sendChatMessage(
  email: string,
  request: ChatRequest
): Promise<ChatResponse> {
  const response = await fetch(
    `${API_URL}/api/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
        "X-User-Email": email,
      },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    let message =
      "Unable to complete the request.";

    try {
      const data = await response.json();

      if (typeof data?.detail === "string") {
        message = data.detail;
      }
    } catch {
      // Keep fallback error message.
    }

    throw new Error(message);
  }

  return response.json();
}