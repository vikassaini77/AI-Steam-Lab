import { motion, AnimatePresence } from 'framer-motion';
import { useState, useRef, useEffect } from 'react';
import { Send, Mic, Sparkles, Plus, Square, Download, Share, CheckCircle2, RefreshCw, Edit2, Check, X, Volume2, Loader2 } from 'lucide-react';
import { useChatStore } from '../../lib/chatStore';
import type { Message } from '../../lib/chatStore';
import ReactMarkdown from 'react-markdown';

export default function AITutorPanel() {
  const { chats = [], activeChatId, addMessage, updateMessage, createNewChat, setMessages, botName, botVoiceURI } = useChatStore();
  const currentChat = chats.find(c => c.id === activeChatId);
  const messages = currentChat?.messages || [];

  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [showCopied, setShowCopied] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [editInput, setEditInput] = useState('');
  const [kgPopup, setKgPopup] = useState('');
  
  // Phase 2: Engagement Tracker States
  const [engagementState, setEngagementState] = useState<'FOCUSED' | 'CONFUSED' | 'DISENGAGED' | null>(null);
  const [showNudge, setShowNudge] = useState(false);
  const disengagedTimerRef = useRef<NodeJS.Timeout | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const recognitionRef = useRef<any>(null);

  // Initialize new chat if none exists
  useEffect(() => {
    if (!activeChatId) {
      createNewChat();
    }
  }, [activeChatId, createNewChat]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Setup Speech Recognition
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        recognitionRef.current = new SpeechRecognition();
        recognitionRef.current.continuous = true;
        recognitionRef.current.interimResults = true;

        recognitionRef.current.onresult = (event: any) => {
          let currentTranscript = '';
          for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
              currentTranscript += event.results[i][0].transcript + ' ';
            } else {
              currentTranscript += event.results[i][0].transcript;
            }
          }
          setInput((prev) => prev + currentTranscript);
        };

        recognitionRef.current.onerror = (event: any) => {
          console.error('Speech recognition error', event.error);
          setIsListening(false);
        };

        recognitionRef.current.onend = () => {
          setIsListening(false);
        };
      }
    }
  }, []);

  // Handle Engagement States
  useEffect(() => {
    if (engagementState === 'DISENGAGED') {
      disengagedTimerRef.current = setTimeout(() => {
        setShowNudge(true);
      }, 8000);
    } else {
      setShowNudge(false);
      if (disengagedTimerRef.current) clearTimeout(disengagedTimerRef.current);
    }

    if (engagementState === 'CONFUSED' && !isTyping) {
      // Automatically ask the agent to simplify
      setInput("[SYSTEM: CONFUSED_USER]");
      setTimeout(() => handleSend(), 500);
      setEngagementState(null); // Reset
    }

    return () => {
      if (disengagedTimerRef.current) clearTimeout(disengagedTimerRef.current);
    };
  }, [engagementState]);

  const toggleListen = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      if (recognitionRef.current) {
        recognitionRef.current.start();
        setIsListening(true);
      } else {
        alert("Microphone dictation is not supported in this browser.");
      }
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsTyping(false);
  };

  const handleDownload = () => {
    if (!currentChat) return;
    let content = `# ${currentChat.title}\n\n`;
    messages.forEach(m => {
      content += `### ${m.sender === 'user' ? 'You' : botName}\n${m.text}\n\n`;
    });
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentChat.title.replace(/\s+/g, '_')}_transcript.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleShare = () => {
    if (!currentChat) return;
    let content = `Chat with ${botName}:\n\n`;
    messages.forEach(m => {
      content += `${m.sender === 'user' ? 'You' : botName}: ${m.text}\n\n`;
    });
    navigator.clipboard.writeText(content).then(() => {
      setShowCopied(true);
      setTimeout(() => setShowCopied(false), 2000);
    });
  };

  const handleSpeak = (text: string) => {
    window.speechSynthesis.cancel();
    // Clean markdown bold/italic asterisks before speaking
    const cleanText = text.replace(/[*#]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    
    if (botVoiceURI) {
      const voices = window.speechSynthesis.getVoices();
      const selectedVoice = voices.find(v => v.voiceURI === botVoiceURI);
      if (selectedVoice) {
        utterance.voice = selectedVoice;
      }
    }
    
    window.speechSynthesis.speak(utterance);
  };

  const handleSend = async (regenerateMessageId?: number, editMessagePayload?: { id: number, newText: string }) => {
    if (!activeChatId) return;

    let userPrompt = input;
    let historyToUse = messages;
    let targetAiMessageId: number | null = null;

    if (editMessagePayload) {
      const index = messages.findIndex(m => m.id === editMessagePayload.id);
      if (index === -1) return;
      userPrompt = editMessagePayload.newText;
      
      const truncated = messages.slice(0, index);
      setMessages(activeChatId, truncated);
      historyToUse = truncated;
      
      const userMessage: Message = {
        id: Date.now(),
        text: userPrompt,
        sender: 'user',
        timestamp: new Date().toISOString(),
      };
      addMessage(activeChatId, userMessage);
    } else if (typeof regenerateMessageId === 'number') {
      const index = messages.findIndex(m => m.id === regenerateMessageId);
      if (index === -1) return;
      for (let i = index - 1; i >= 0; i--) {
        if (messages[i].sender === 'user') {
          userPrompt = messages[i].text;
          break;
        }
      }
      historyToUse = messages.slice(0, index);
      targetAiMessageId = regenerateMessageId;
      updateMessage(activeChatId, targetAiMessageId, ""); // clear text
    } else {
      if (!input.trim()) return;
      if (isListening) toggleListen();

      const userMessage: Message = {
        id: Date.now(),
        text: userPrompt,
        sender: 'user',
        timestamp: new Date().toISOString(),
      };
      addMessage(activeChatId, userMessage);
      setInput('');
    }

    setIsTyping(true);
    abortControllerRef.current = new AbortController();

    try {
      const formattedHistory = historyToUse.map(msg => ({
        role: msg.sender === 'ai' ? 'assistant' : 'user',
        content: msg.text
      }));

      let experimentState = null;
      try {
        const stored = localStorage.getItem('neurolab_experiment_state');
        if (stored) experimentState = JSON.parse(stored);
      } catch (err) {}

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
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const aiMessageId = targetAiMessageId || (Date.now() + 1);
      
      if (!targetAiMessageId) {
        const initialAiMessage: Message = {
          id: aiMessageId,
          text: '',
          sender: 'ai',
          timestamp: new Date().toISOString()
        };
        addMessage(activeChatId, initialAiMessage);
      }
      
      setIsTyping(false);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let fullText = '';
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.substring(6));
                if (data.text) {
                  fullText += data.text;
                  updateMessage(activeChatId, aiMessageId, fullText);
                }
                if (data.kg_update) {
                  setKgPopup(data.kg_update);
                  setTimeout(() => setKgPopup(''), 4000);
                }
              } catch (e) {}
            }
          }
        }
      }

    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Stream aborted');
      } else {
        console.error('Tutor chat API connection failed:', error);
        addMessage(activeChatId, {
          id: Date.now() + 2,
          text: "I'm running in offline mode because I couldn't reach the backend server. Make sure FastAPI is running on port 8000!",
          sender: 'ai',
          timestamp: new Date().toISOString(),
        });
      }
    } finally {
      setIsTyping(false);
      abortControllerRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  return (
    <div className="flex-1 flex flex-col relative bg-ambient-glow bg-[#070714]">
      
      {/* Top Bar (Optional Model Selector & Actions) */}
      <div className="absolute top-0 left-0 right-0 h-14 flex items-center justify-between px-4 z-10 glass border-b-0">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-gray-300 font-semibold text-lg ml-12">
          {botName} <span className="text-gray-500 text-sm font-normal">v2.5</span>
          {engagementState && (
            <span className={`ml-3 text-[10px] px-2 py-0.5 rounded-full uppercase tracking-widest font-bold border ${
              engagementState === 'FOCUSED' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
              engagementState === 'CONFUSED' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' :
              'bg-red-500/20 text-red-400 border-red-500/30'
            }`}>
              {engagementState}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setEngagementState('CONFUSED')}
            className="px-2 py-1 bg-amber-500/20 text-amber-400 rounded-lg text-[10px] font-bold border border-amber-500/30 hover:bg-amber-500/30"
          >
            Mock Confused
          </button>
          <button 
            onClick={() => setEngagementState('DISENGAGED')}
            className="px-2 py-1 bg-red-500/20 text-red-400 rounded-lg text-[10px] font-bold border border-red-500/30 hover:bg-red-500/30"
          >
            Mock Away
          </button>
          <button 
            onClick={() => {
              setEngagementState('FOCUSED');
              setInput("[SYSTEM: ENGAGEMENT_SPIKE]");
              setTimeout(() => handleSend(), 100);
            }}
            className="px-2 py-1 bg-cyan-500/20 text-cyan-400 rounded-lg text-[10px] font-bold border border-cyan-500/30 hover:bg-cyan-500/30"
          >
            Mock Lean
          </button>
          {messages.length > 0 && (
            <>
              <button 
                onClick={handleDownload}
                className="p-2 text-gray-400 hover:text-cyan-400 hover:bg-white/5 rounded-lg transition-colors"
                title="Download Chat"
              >
                <Download className="w-5 h-5" />
              </button>
              <button 
                onClick={handleShare}
                className="p-2 text-gray-400 hover:text-cyan-400 hover:bg-white/5 rounded-lg transition-colors relative"
                title="Share Chat"
              >
                {showCopied ? <CheckCircle2 className="w-5 h-5 text-green-400" /> : <Share className="w-5 h-5" />}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto w-full pt-16 pb-32">
        <div className="max-w-3xl mx-auto px-4 flex flex-col space-y-6">
          <AnimatePresence>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-4 w-full ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {message.sender === 'ai' && (
                  <div className="w-8 h-8 rounded-full border border-white/10 flex flex-shrink-0 items-center justify-center bg-white">
                    <Sparkles className="w-5 h-5 text-black" />
                  </div>
                )}
                <div
                  className={`text-[15px] leading-relaxed max-w-[85%] ${
                    message.sender === 'user'
                      ? 'glass text-gray-100 px-5 py-2.5 rounded-3xl group'
                      : 'text-gray-100 py-1 group'
                  }`}
                >
                  {editingMessageId === message.id ? (
                    <div className="flex flex-col gap-2 min-w-[250px]">
                      <textarea
                        value={editInput}
                        onChange={(e) => setEditInput(e.target.value)}
                        className="w-full bg-black/40 text-white rounded-lg p-2 text-sm focus:outline-none border border-cyan-500/30 resize-none min-h-[80px]"
                      />
                      <div className="flex justify-end gap-2">
                        <button 
                          onClick={() => setEditingMessageId(null)}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 text-gray-300 transition-colors"
                        >
                          Cancel
                        </button>
                        <button 
                          onClick={() => {
                            setEditingMessageId(null);
                            handleSend(undefined, { id: message.id, newText: editInput });
                          }}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-cyan-500 text-black hover:bg-cyan-400 transition-colors"
                        >
                          Save & Submit
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="relative">
                      {message.sender === 'ai' ? (
                        <div className="prose prose-invert max-w-none text-gray-200 prose-p:leading-relaxed prose-pre:bg-black/50 prose-pre:border prose-pre:border-white/10 prose-strong:text-white">
                          <ReactMarkdown>{message.text}</ReactMarkdown>
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap">{message.text}</p>
                      )}
                      
                      {message.sender === 'user' && (
                        <div className="absolute -left-10 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button 
                            onClick={() => {
                              setEditingMessageId(message.id);
                              setEditInput(message.text);
                            }}
                            className="p-1.5 bg-black/40 hover:bg-black/60 rounded-full border border-white/5 text-gray-400 hover:text-cyan-400 transition-colors shadow-sm"
                            title="Edit message"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {message.sender === 'ai' && (
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity mt-2 flex gap-2">
                      <button 
                        onClick={() => handleSend(message.id)}
                        className="flex items-center gap-1.5 px-2 py-1 bg-white/5 hover:bg-white/10 rounded-md text-[10px] text-gray-400 hover:text-cyan-400 font-medium transition-colors border border-white/5"
                        title="Regenerate response"
                      >
                        <RefreshCw className="w-3 h-3" />
                        Regenerate
                      </button>
                      <button 
                        onClick={() => handleSpeak(message.text)}
                        className="flex items-center gap-1.5 px-2 py-1 bg-white/5 hover:bg-white/10 rounded-md text-[10px] text-gray-400 hover:text-cyan-400 font-medium transition-colors border border-white/5"
                        title="Read aloud"
                      >
                        <Volume2 className="w-3 h-3" />
                        Read Aloud
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center min-h-[50vh] w-full max-w-2xl mx-auto px-4">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center mb-6 shadow-lg shadow-cyan-500/20"
              >
                <Sparkles className="w-8 h-8 text-white" />
              </motion.div>
              <motion.h2 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="text-3xl font-bold text-white mb-10 text-center"
              >
                How can I help you today?
              </motion.h2>

              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full"
              >
                {[
                  { title: 'Explain Quantum Computing', desc: 'Break down qubits and superposition simply' },
                  { title: 'Help debug my Python code', desc: 'Find logic errors in my data science script' },
                  { title: 'Brainstorm project ideas', desc: 'For my final year Machine Learning project' },
                  { title: 'Review my resume', desc: 'For an AI Engineering internship role' }
                ].map((topic, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      const fullText = `${topic.title}: ${topic.desc}`;
                      setInput(fullText);
                      if (inputRef.current) {
                        inputRef.current.focus();
                      }
                    }}
                    className="flex flex-col text-left p-4 rounded-xl bg-[#12121a]/50 border border-white/5 hover:bg-[#12121a] hover:border-cyan-500/30 transition-all group"
                  >
                    <span className="text-sm font-medium text-gray-200 group-hover:text-cyan-400">{topic.title}</span>
                    <span className="text-xs text-gray-500 mt-1">{topic.desc}</span>
                  </button>
                ))}
              </motion.div>
            </div>
          )}

          {isTyping && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-4 w-full justify-start"
            >
              <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center bg-white">
                <Sparkles className="w-5 h-5 text-black" />
              </div>
              <div className="bg-[#12121a]/80 border border-white/5 rounded-3xl px-5 py-2.5 flex flex-col gap-2 min-w-[200px]">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                  <span className="text-xs text-cyan-400 font-semibold uppercase tracking-wider">Thinking</span>
                </div>
                <div className="flex flex-col gap-1.5">
                  <div className="h-2 bg-white/10 rounded w-full animate-pulse" />
                  <div className="h-2 bg-white/10 rounded w-3/4 animate-pulse" />
                  <div className="h-2 bg-white/10 rounded w-5/6 animate-pulse" />
                </div>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} className="h-4" />
        </div>
      </div>

      <AnimatePresence>
        {kgPopup && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className="absolute bottom-24 left-1/2 -translate-x-1/2 z-50 bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 border border-emerald-500/50 text-white px-6 py-3 rounded-full shadow-[0_0_20px_rgba(16,185,129,0.3)] backdrop-blur-md flex items-center gap-3"
          >
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            <span className="font-semibold text-sm">{kgPopup}</span>
          </motion.div>
        )}
        
        {showNudge && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="absolute top-20 left-1/2 -translate-x-1/2 z-50 bg-gradient-to-r from-blue-900/80 to-purple-900/80 border border-blue-500/50 text-white px-6 py-3 rounded-2xl shadow-xl backdrop-blur-md flex items-center gap-3 cursor-pointer"
            onClick={() => setEngagementState('FOCUSED')}
          >
            <div className="w-8 h-8 rounded-full bg-blue-500/30 flex items-center justify-center animate-pulse">
              <Sparkles className="w-4 h-4 text-blue-300" />
            </div>
            <div>
              <p className="font-semibold text-sm text-blue-100">Are you still there?</p>
              <p className="text-xs text-blue-300">I noticed you stepped away. Click to resume.</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input Area */}
      <div className="absolute bottom-0 left-0 right-0 p-4 glass border-t-0 z-10 pt-8 pb-6">
        <div className="max-w-3xl mx-auto w-full relative">
          <div className="bg-[#12121a]/90 backdrop-blur-md rounded-[24px] pl-4 pr-2 py-2 flex items-end shadow-[0_0_15px_rgba(0,255,255,0.05)] border border-white/10">
            <button 
              onClick={() => pushNotification('File attachments will be supported in v3.0.', 'info')}
              className="p-2 mr-1 rounded-full text-gray-400 hover:text-white hover:bg-white/10 transition-colors flex-shrink-0 mb-1"
            >
              <Plus className="w-5 h-5" />
            </button>
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything..."
              rows={1}
              className="flex-1 max-h-[200px] bg-transparent text-white placeholder-gray-400 resize-none focus:outline-none py-3 text-[15px] scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent"
              style={{ minHeight: '44px' }}
            />
            <div className="flex gap-1 ml-2 mb-1 flex-shrink-0">
              {isTyping ? (
                <button
                  onClick={handleStop}
                  className="w-8 h-8 rounded-full bg-red-500/20 text-red-500 flex items-center justify-center hover:bg-red-500/30 transition-colors shadow-md"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                </button>
              ) : input.trim() ? (
                <button
                  onClick={() => handleSend()}
                  className="w-8 h-8 rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 text-white flex items-center justify-center hover:opacity-90 transition-opacity shadow-md shadow-cyan-500/20"
                >
                  <Send className="w-4 h-4 ml-0.5" />
                </button>
              ) : (
                <button 
                  onClick={toggleListen}
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                    isListening ? 'bg-red-500/20 text-red-500 animate-pulse' : 'text-gray-400 hover:text-white hover:bg-white/10'
                  }`}
                >
                  <Mic className="w-5 h-5" />
                </button>
              )}
            </div>
          </div>
          <p className="text-center text-xs text-gray-500 mt-3 font-medium">
            {botName} can make mistakes. Check important information.
          </p>
        </div>
      </div>
    </div>
  );
}
