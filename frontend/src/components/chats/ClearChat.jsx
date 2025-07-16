import React, { useContext } from 'react';
import axios from 'axios';
import '../../style/Button.css';

const ClearChat = () => {
  const base = process.env.REACT_APP_API_BASE;
  const token = localStorage.getItem('accessToken'); // akses langsung


  const handleClearChat = async () => {
    try {
      await axios.post(`${base}/truncate-chat-history`, {}, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
    } catch (error) {
      console.error('Gagal menghapus riwayat chat:', error);
      alert('Gagal menghapus riwayat chat.');
    }
  };

  return (
    <button onClick={handleClearChat} className="btn btn-danger clear-chat-button">
      Clear Chat
    </button>
  );
};

export default ClearChat;
