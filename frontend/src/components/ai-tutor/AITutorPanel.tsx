import { motion, AnimatePresence } from 'framer-motion';
import { useState, useRef, useEffect } from 'react';
import { Send, Mic, Sparkles, User, Volume2, VolumeX } from 'lucide-react';

interface Message {
  id: number;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

export default function AITutorPanel() {
  const [voiceEnabled, setVoiceEnabled] = useState<boolean>(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      text: "Hello! I'm Professor Nova, your AI STEM mentor. I can help you understand the physics of pendulum motion, explain complex concepts, and verify your lab experiments in real time. What would you like to explore today?",
      sender: 'ai',
      timestamp: new Date(),
    },
    {
      id: 2,
      text: "I've synchronized with your Live Lab. Toggling the webcam lets us calibrate physical motion. Would you like me to guide you through a Newton's Laws of Motion experiment?",
      sender: 'ai',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const speakText = (text: string) => {
    if (!voiceEnabled) return;
    try {
      window.speechSynthesis.cancel();
      // Clean LaTeX & math markers for clean TTS output
      const clean = text.replace(/[\$\#\*\_]/g, '').replace(/\\pi/g, 'pi').replace(/\\sqrt/g, 'square root of ');
      const utterance = new SpeechSynthesisUtterance(clean);
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.error('Speech synthesis error:', e);
    }
  };

  useEffect(() => {
    const handleTopic = (e: Event) => {
      const topic = (e as CustomEvent).detail;
      setInput("Tell me more about: " + topic);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    };
    window.addEventListener('ai-tutor-select-topic', handleTopic);
    return () => window.removeEventListener('ai-tutor-select-topic', handleTopic);
  }, []);

  // Speak welcome message if voice is activated
  useEffect(() => {
    if (voiceEnabled && messages.length > 0) {
      speakText(messages[messages.length - 1].text);
    }
  }, [voiceEnabled]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userPrompt = input;
    const userMessage: Message = {
      id: messages.length + 1,
      text: userPrompt,
      sender: 'user',
      timestamp: new Date(),
    };

    // Update messages local state
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      // 1. Format chat history into standard API expected role/content structure
      // We map "ai" -> "assistant" and "user" -> "user"
      const formattedHistory = messages.map(msg => ({
        role: msg.sender === 'ai' ? 'assistant' : 'user',
        content: msg.text
      }));

      // 2. Fetch active physical laboratory experiment measurements if any
      let experimentState = null;
      try {
        const stored = localStorage.getItem('neurolab_experiment_state');
        if (stored) {
          experimentState = JSON.parse(stored);
        }
      } catch (err) {
        console.error('Error reading physical lab context state:', err);
      }

      // 3. Resolve FastAPI endpoint dynamically (supports Vite dev port 5173 & FastAPI built port 8000)
      const apiHost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? `${window.location.protocol}//${window.location.hostname}:8000`
        : window.location.origin;

      const response = await fetch(`${apiHost}/api/tutor/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          prompt: userPrompt,
          history: formattedHistory,
          experiment_state: experimentState
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const aiMessageId = Date.now();
      setMessages((prev) => [
        ...prev,
        { id: aiMessageId, text: '', sender: 'ai', timestamp: new Date() }
      ]);
      setIsTyping(false);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let fullText = '';
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.substring(6));
                if (data.text) {
                  fullText += data.text;
                  setMessages((prev) =>
                    prev.map((m) => (m.id === aiMessageId ? { ...m, text: fullText } : m))
                  );
                }
              } catch (e) {
                // Ignore chunk parse errors
              }
            }
          }
        }
        speakText(fullText);
      }

    } catch (error) {
      console.error('Tutor chat API connection failed:', error);
      
      // Dynamic mathematical fallback response to guarantee flawless continuity
      const fallbackMessage: Message = {
        id: messages.length + 2,
        text: "I'm running in offline mode because I couldn't reach the FastAPI server. Just a quick reminder: Simple Harmonic Motion follows $T = 2\\pi\\sqrt{L/g}$. Please verify the server is running on port 8000!",
        sender: 'ai',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, fallbackMessage]);
      speakText(fallbackMessage.text);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="h-[calc(100vh-200px)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="relative w-10 h-10 rounded-full bg-gradient-to-tr from-cyan-500 to-violet-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Sparkles className="w-5 h-5 text-white animate-pulse" />
            <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 rounded-full border-2 border-[#0d0d20] shadow-md animate-pulse" />
          </div>
          <div>
            <h3 className="text-white font-semibold flex items-center gap-2">
              Professor Nova
            </h3>
            <p className="text-green-400 text-xs font-semibold flex items-center gap-1">
              Online - Ready to help
            </p>
          </div>
        </div>
        
        {/* TTS Voice Activator Toggle */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => {
            setVoiceEnabled(!voiceEnabled);
            if (voiceEnabled) window.speechSynthesis.cancel();
          }}
          className={`p-2.5 rounded-xl border transition-all flex items-center gap-1.5 text-xs font-bold ${
            voiceEnabled 
              ? 'bg-cyan-500/20 border-cyan-500/35 text-cyan-400 shadow-md shadow-cyan-500/10' 
              : 'bg-white/5 border-white/10 text-gray-400 hover:text-white'
          }`}
          title={voiceEnabled ? "Mute Professor Nova" : "Enable Voice explanations"}
        >
          {voiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          <span>Voice Output</span>
        </motion.button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
        <AnimatePresence>
          {messages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 ${message.sender === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  message.sender === 'ai'
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-500'
                    : 'bg-gradient-to-r from-violet-500 to-purple-500'
                }`}
              >
                {message.sender === 'ai' ? (
                  <Sparkles className="w-4 h-4 text-white" />
                ) : (
                  <User className="w-4 h-4 text-white" />
                )}
              </div>
              <div
                className={`flex-1 p-4 rounded-xl max-w-[85%] ${
                  message.sender === 'ai'
                    ? 'bg-gradient-to-br from-cyan-500/10 to-blue-500/10 border border-cyan-500/20'
                    : 'bg-gradient-to-br from-violet-500/10 to-purple-500/10 border border-violet-500/20 ml-auto'
                }`}
              >
                <p className="text-sm text-gray-200 leading-relaxed">{message.text}</p>
                <p className="text-xs text-gray-500 mt-2">
                  {message.timestamp.toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {isTyping && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    animate={{ y: [0, -5, 0] }}
                    transition={{
                      duration: 0.6,
                      repeat: Infinity,
                      delay: i * 0.2,
                    }}
                    className="w-2 h-2 rounded-full bg-cyan-400"
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-white/10">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask me anything about STEM..."
              className="w-full pl-4 pr-12 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all"
            />
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-cyan-400 transition-colors"
            >
              <Mic className="w-5 h-5" />
            </motion.button>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleSend}
            disabled={!input.trim()}
            className="w-12 h-12 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:shadow-lg hover:shadow-cyan-500/20 text-white flex items-center justify-center flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-5 h-5" />
          </motion.button>
        </div>
      </div>
    </div>
  );
}
