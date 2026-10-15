import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Inventory from './pages/Inventory';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [username, setUsername] = useState(null);

  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }, [token]);

  useEffect(() => {
    const fetchMe = async () => {
      try {
        if (!token) return;
        const res = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error('Failed to fetch user');
        const data = await res.json();
        setUsername(data.username);
      } catch {
        setUsername(null);
      }
    };

    fetchMe();
  }, [token]);

  const handleLogout = () => {
    setToken(null);
    setUsername(null);
  };

  return (
    <BrowserRouter>
      {token && <Navbar username={username} onLogout={handleLogout} />}
      <div className="app-container">
        <Routes>
          <Route 
            path="/login" 
            element={!token ? <Login setToken={setToken} /> : <Navigate to="/" />} 
          />
          <Route 
            path="/" 
            element={token ? <Dashboard /> : <Navigate to="/login" />} 
          />
          <Route 
            path="/inventory" 
            element={token ? <Inventory /> : <Navigate to="/login" />} 
          />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
