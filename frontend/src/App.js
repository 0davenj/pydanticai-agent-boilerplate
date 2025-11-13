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
  const ws = useRef(null);

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
      } else if (data.type === 'chunk') {
        setMessages(prev => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === 'assistant' && !lastMessage.done) {
            // Append to existing assistant message
            return [
              ...prev.slice(0, -1),
              { ...lastMessage, content: lastMessage.content + data.content }
            ];
          } else {
            // Create new assistant message
            return [...prev, { role: 'assistant', content: data.content, done: false }];
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

    // Add user message to chat
    setMessages(prev => [...prev, { role: 'user', content: inputMessage, done: true }]);
    
    // Send message to server
    ws.current.send(JSON.stringify({ message: inputMessage }));
    
    // Add placeholder for assistant response
    setMessages(prev => [...prev, { role: 'assistant', content: '', done: false }]);
    
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
        <h1>PydanticAI Agent</h1>
        <div className={`connection-status ${isConnected && isAuthenticated ? 'connected' : 'disconnected'}`}>
          {connectionStatus}
        </div>
      </header>
      
      <main className="chat-container">
        <div className="messages">
          {messages.length === 0 && (
            <div className="welcome-message">
              <p>Welcome to PydanticAI Agent! Your session is ready.</p>
              <p>Ask me anything...</p>
            </div>
          )}
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <div className="message-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
        <p>AI Provider: <strong>{process.env.REACT_APP_AI_PROVIDER || 'Azure'}</strong></p>
        <p>Session: <code>{sessionId ? `${sessionId.substring(0, 8)}...` : 'Not established'}</code></p>
      </footer>
    </div>
  );
}

export default App;