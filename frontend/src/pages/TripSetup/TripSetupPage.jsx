import { useNavigate } from 'react-router-dom';
import ChatPage from '../ChatPage/ChatPage';

export default function TripSetupPage() {
  const navigate = useNavigate();
  return <ChatPage setupMode onSetupContinue={() => navigate('/chat')} />;
}
