import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Chat from './pages/Chat';
import Memories from './pages/Memories';
import RiskMetrics from './pages/RiskMetrics';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <div className="app-container">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Chat />} />
            <Route path="/memories" element={<Memories />} />
            <Route path="/risk" element={<RiskMetrics />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
