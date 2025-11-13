import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('Disconnected');
  const [aiProvider, setAiProvider] = useState('Unknown'); // Track AI provider
  const [modelName, setModelName] = useState('Unknown'); // Track model name
  const ws = useRef(null);
  const currentResponseId = useRef(null);

  useEffect(() => {
    // Get session ID on component mount
    const getSession = async () => {
      try {
        const response = await fetch('/auth/login', { method: 'POST' });
        if (!response.ok) {
          throw new Error('Failed to get session');
        }
        const data = await response.json();
        setSessionId(data.session_id);
      } catch (error) {
        console.error('Failed to get session:', error);
        setConnectionStatus('Error: Failed to authenticate');
      }
    };
    
    getSession();
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setConnectionStatus('Connected - Authenticating...');
      
      // Send authentication
      ws.current.send(JSON.stringify({ session_id: sessionId }));
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'auth_success') {
        setIsAuthenticated(true);
        setConnectionStatus('Connected and Authenticated');
        console.log('Authenticated successfully');
        // Set AI provider and model from backend
        if (data.ai_provider) {
          setAiProvider(data.ai_provider);
        }
        if (data.model_name) {
          setModelName(data.model_name);
        }
      } else if (data.type === 'chunk') {
        console.log(`Received chunk ${data.chunk_id}: "${data.content}"`);
        
        // Use functional update to ensure we always have latest state
        setMessages(prevMessages => {
          // Find the last assistant message that is not done
          const lastAssistantIndex = prevMessages.findLastIndex(m => m.role === 'assistant' && !m.done);
          
          if (lastAssistantIndex !== -1) {
            // Get current content and append new chunk
            const currentContent = prevMessages[lastAssistantIndex].content;
            const newContent = currentContent + data.content;
            
            // Create new array with updated message
            return [
              ...prevMessages.slice(0, lastAssistantIndex),
              {
                ...prevMessages[lastAssistantIndex],
                content: newContent
              },
              ...prevMessages.slice(lastAssistantIndex + 1)
            ];
          } else {
            // Create new message
            return [...prevMessages, {
              role: 'assistant',
              content: data.content,
              done: false,
              response_id: data.response_id
            }];
          }
        });
      } else if (data.type === 'done') {
        setMessages(prev => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              { ...lastMessage, done: true }
            ];
          }
          return prev;
        });
      } else if (data.type === 'sources') {
        console.log(`Received sources: "${data.content}"`);
        
        // Add sources as a separate message
        setMessages(prevMessages => [
          ...prevMessages,
          {
            role: 'sources',
            content: data.content,
            done: true,
            response_id: data.response_id
          }
        ]);
      } else if (data.type === 'error') {
        console.error('Error from server:', data.message);
        setConnectionStatus(`Error: ${data.message}`);
      }
    };

    ws.current.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      setIsAuthenticated(false);
      setConnectionStatus('Disconnected');
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('Error: Connection failed');
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [sessionId]);

  const sendMessage = () => {
    if (!inputMessage.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN || !isAuthenticated) {
      return;
    }

    // Generate a unique ID for this response
    const responseId = Date.now().toString();
    currentResponseId.current = responseId;
    
    // Add user message to chat
    setMessages(prev => [...prev, { role: 'user', content: inputMessage, done: true }]);
    
    // Send message to server
    ws.current.send(JSON.stringify({ message: inputMessage }));
    
    // Clear input
    setInputMessage('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Microsoft Expert Agent</h1>
        <div className={`connection-status ${isConnected && isAuthenticated ? 'connected' : 'disconnected'}`}>
          {connectionStatus}
        </div>
      </header>
      
      <main className="chat-container">
        <div className="messages">
          {messages.length === 0 && (
            <div className="welcome-message">
              <p>Welcome to Microsoft Expert Agent by Opteia! Your session is ready.</p>
              <p>Ask me anything...</p>
            </div>
          )}
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <div className="message-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children, ...props }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        {...props}
                      >
                        {children}
                      </a>
                    )
                  }}
                >
                  {message.content}
                </ReactMarkdown>
                {message.role === 'assistant' && !message.done && (
                  <span className="typing-indicator">▌</span>
                )}
              </div>
            </div>
          ))}
        </div>
        
        <div className="input-container">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
            rows="3"
            disabled={!isConnected || !isAuthenticated}
          />
          <button 
            onClick={sendMessage} 
            disabled={!isConnected || !isAuthenticated || !inputMessage.trim()}
            className="send-button"
          >
            Send
          </button>
        </div>
      </main>
      
      <footer className="App-footer">
        <p>AI Provider: <strong>{aiProvider}</strong></p>
        <p>Model: <strong>{modelName}</strong></p>
        <p>Session: <code>{sessionId ? `${sessionId.substring(0, 8)}...` : 'Not established'}</code></p>
      </footer>
    </div>
  );
}

export default App;