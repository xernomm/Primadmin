import React from 'react';
import ChatField from '../components/chats/ChatField';
import Input from '../components/chats/Input';
import "../style/ChatPage.css"

const ChatPage = () => {
  return (
    <div className="chat-page d-flex flex-column align-items-center justify-content-center bg-dark text-light">
      {/* Chat Field */}
      <div className="col-12 overflowChat">
        <div className="chat-container w-100 d-flex justify-content-center">
          <div className="chat-box col-sm-11 col-md-10 col-lg-7">
            <ChatField />
          </div>
        </div>
      </div>

      {/* Input - Sticky Bottom */}
      <div className="input-container w-100 d-flex justify-content-center">
        <div className="col-12 col-sm-11 col-md-10 col-lg-7">
          <Input />
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
