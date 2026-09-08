import axios from "axios";
import { useState, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";

const API_BASE = "http://localhost:8000";

const Home = () => {
  const [status, setStatus] = useState("Click mic to speak...");
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [messages, setMessages] = useState([]);
  const [sessionId] = useState(() => uuidv4());

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      chunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
        await sendToBackend(audioBlob);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      setStatus("🔴 Listening... Click to stop");
    } catch {
      setStatus("❌ Mic access denied!");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    setStatus("⏳ AI is thinking...");
  };

  // Backend sends X-Audio-Format: "wav" (Orpheus) or "mp3" (gTTS fallback).
  // Blob MIME type must match the actual bytes or the browser silently
  // refuses to play the audio.
  const mimeFromFormat = (format) => {
    if (format === "wav") return "audio/wav";
    if (format === "mp3") return "audio/mpeg";
    return "audio/mpeg"; // safe default
  };

  const sendToBackend = async (audioBlob) => {
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      formData.append("session_id", sessionId);

      const response = await axios.post(`${API_BASE}/voice-chat`, formData, {
        responseType: "arraybuffer",
      });

      const userText = decodeURIComponent(response.headers["x-transcript"] || "");
      const aiText = decodeURIComponent(response.headers["x-ai-reply"] || "");
      const audioFormat = response.headers["x-audio-format"];

      setMessages((prev) => [
        ...prev,
        { role: "user", text: userText },
        { role: "ai", text: aiText },
      ]);

      const blob = new Blob([response.data], { type: mimeFromFormat(audioFormat) });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);

      audio.onerror = () => {
        setIsSpeaking(false);
        setStatus("❌ Couldn't play AI voice");
        URL.revokeObjectURL(url);
      };

      setIsSpeaking(true);
      setStatus("🔊 AI is speaking...");
      await audio.play();

      audio.onended = () => {
        setIsSpeaking(false);
        setStatus("Click mic to speak...");
        URL.revokeObjectURL(url);
      };
    } catch (err) {
      // Backend errors arrive as arraybuffer too, so decode them for a
      // useful message instead of a generic failure.
      let message = "❌ Something went wrong, try again";
      const data = err?.response?.data;
      if (data instanceof ArrayBuffer) {
        try {
          const parsed = JSON.parse(new TextDecoder().decode(data));
          if (parsed?.error) message = `❌ ${parsed.error}`;
        } catch {
          // not JSON, keep generic message
        }
      }
      console.error("voice-chat failed:", err);
      setStatus(message);
    } finally {
      setIsLoading(false);
    }
  };

  const clearConversation = async () => {
    try {
      await axios.post(`${API_BASE}/clear-session?session_id=${sessionId}`);
      setMessages([]);
      setStatus("Click mic to speak...");
    } catch (err) {
      console.error("clear-session failed:", err);
      setStatus("❌ Could not clear chat");
    }
  };

  const getMicLabel = () => {
    if (isLoading) return "⏳";
    if (isSpeaking) return "🔊";
    if (isRecording) return "⏹️";
    return "🎤";
  };

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col items-center justify-center p-4">
      <div className="bg-gray-800 shadow-2xl rounded-2xl w-full max-w-lg flex flex-col h-[85vh]">

        <div className="p-6 border-b border-gray-700 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-blue-400">🎙️ Voice AI</h1>
            <p className="text-gray-400 text-xs mt-1">LangChain + Groq + Orpheus TTS</p>
          </div>
          <button
            onClick={clearConversation}
            className="text-xs text-gray-400 hover:text-red-400 border border-gray-600 hover:border-red-400 px-3 py-1 rounded-lg transition-all"
          >
            Clear Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-500 text-sm">Start speaking to begin conversation...</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm"
                    : "bg-gray-700 text-gray-100 rounded-bl-sm"
                }`}
              >
                <p className="text-xs mb-1 opacity-60">
                  {msg.role === "user" ? "🗣️ You" : "🤖 AI"}
                </p>
                {msg.text}
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        <div className="p-6 border-t border-gray-700 flex flex-col items-center gap-3">
          <p className="text-gray-400 text-xs">{status}</p>
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isLoading || isSpeaking}
            className={`w-20 h-20 rounded-full text-4xl transition-all duration-200 shadow-lg
              ${isRecording
                ? "bg-red-500 animate-pulse shadow-red-500/50"
                : isSpeaking
                ? "bg-green-600 animate-pulse shadow-green-500/50"
                : "bg-blue-600 hover:bg-blue-500 shadow-blue-500/30"}
              disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {getMicLabel()}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Home;