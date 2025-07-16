// ChatField.jsx
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { FaUserCircle } from 'react-icons/fa';
import Markdown from 'react-markdown';
import Loading from '../../utils/Spinner';
import NoChat from './NoChat';
import '../../style/ChatBox.css';
import '../../style/ChatField.css';
import '../../style/Font.css';
import { useRef } from 'react';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw'
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Box from '@mui/material/Box';

function CustomTabPanel(props) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 1 }}>{children}</Box>}
    </div>
  );
}

function a11yProps(index) {
  return {
    id: `simple-tab-${index}`,
    'aria-controls': `simple-tabpanel-${index}`,
  };
}
const ChatField = () => {
  const [chats, setChats] = useState([]);
  const [error, setError] = useState('');
  const token = localStorage.getItem('accessToken'); // akses langsung
  const [showThink, setShowThink] = useState({});


  const base = process.env.REACT_APP_API_BASE;

const extractThinkAndMain = (content) => {
  const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/i);
  const thinkContent = thinkMatch ? thinkMatch[1].trim() : null;
  const mainContent = content.replace(/<think>[\s\S]*?<\/think>/i, '').trim();
  return { thinkContent, mainContent };
};


useEffect(() => {
  const fetchChats = async () => {
    try {
      const response = await axios.get(`${base}/chat-history`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      setChats(response.data.chat_history);
      setError('');

    } catch (err) {
      if (
        axios.isAxiosError(err) &&
        err.response?.data?.error === "Token kedaluwarsa."
      ) {
        console.warn("🔁 Access token expired. Refreshing...");

        try {
          const refreshToken = localStorage.getItem('refreshToken');
          const refreshResponse = await axios.post(`${base}/api/refresh`, {
            refresh_token: refreshToken,
          });

          const newAccessToken = refreshResponse.data.access_token;
          localStorage.setItem("accessToken", newAccessToken);

          // Retry fetch with new token
          const retry = await axios.get(`${base}/chat-history`, {
            headers: {
              Authorization: `Bearer ${newAccessToken}`,
            },
          });

          setChats(retry.data.chat_history);
          setError('');

        } catch (refreshErr) {
          console.error("❌ Gagal refresh token:", refreshErr);
          setError("Sesi habis. Silakan login kembali.");
          // Redirect ke login page jika perlu
          // navigate("/"); <-- jika pakai react-router
        }

      } else {
        setError('Failed to fetch chat history');
        console.error(err);
      }
    }
  };

  fetchChats();
  const intervalId = setInterval(fetchChats, 1000);
  return () => clearInterval(intervalId);
}, [base]);

const bottomRef = useRef(null);
const prevLastChatRef = useRef(null);


useEffect(() => {
  const lastChat = chats[chats.length - 1];

  const prevLastChat = prevLastChatRef.current;

  if (
    lastChat &&
    (!prevLastChat || lastChat.content !== prevLastChat.content)
  ) {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
    prevLastChatRef.current = lastChat;
  }
}, [chats]);




const [tabStates, setTabStates] = useState({});
const handleTabChange = (chatId, newValue) => {
  setTabStates(prev => ({
    ...prev,
    [chatId]: newValue,
  }));
};


  return (

      <div className={`col-12 ${chats.length > 0 ? 'chatfield' : ''}`}>
        {chats.length > 0 ? (
          chats.map((chat, index) => (
            <div key={index}>
              {chat.role === 'user' ? (
                <div className="d-flex col-12 justify-content-end">
                  <div className="user-message mb-0">
                    <Markdown
                      rehypePlugins={[rehypeRaw]}
                      remarkPlugins={[remarkGfm]}
                      remarkRehypeOptions={{ passThrough: ['link'] }}
                      >{chat.content}</Markdown>
                  </div>
                  <div className="d-flex align-items-center">
                    <FaUserCircle className="text-white ms-2 px32" />
                  </div>
                </div>
              ) : (
                <div className="d-flex col-12 justify-content-start my-5">
                  <div className="bot-message">
                    {chat.content ? (() => {
                      const { thinkContent, mainContent } = extractThinkAndMain(chat.content);
                      const chatId = chat.id ?? index;
                      const currentTab = tabStates[chatId] ?? 0;

                      return (
                        <Box sx={{ width: '100%' }}>
                          {thinkContent && (
                            <>
                              <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                                <Tabs
                                  value={currentTab}
                                  onChange={(e, newValue) => handleTabChange(chatId, newValue)}
                                  aria-label="Response Tabs"
                                >
                                  <Tab sx={{ color:'white'}} label="📝 Final Answer" {...a11yProps(0)} />
                                  <Tab sx={{ color:'white'}} label="🧠 Process" {...a11yProps(1)} />
                                </Tabs>
                              </Box>
                              <CustomTabPanel value={currentTab} index={0}>
                                <Markdown
                                  rehypePlugins={[rehypeRaw]}
                                  remarkPlugins={[remarkGfm]}
                                  remarkRehypeOptions={{ passThrough: ['link'] }}
                                >
                                  {mainContent}
                                </Markdown>
                              </CustomTabPanel>
                              <CustomTabPanel value={currentTab} index={1}>
                                <Markdown
                                  rehypePlugins={[rehypeRaw]}
                                  remarkPlugins={[remarkGfm]}
                                  remarkRehypeOptions={{ passThrough: ['link'] }}
                                >
                                  {thinkContent}
                                </Markdown>
                              </CustomTabPanel>
                            </>
                          )}

                          {!thinkContent && (
                            <Markdown
                              rehypePlugins={[rehypeRaw]}
                              remarkPlugins={[remarkGfm]}
                              remarkRehypeOptions={{ passThrough: ['link'] }}
                            >
                              {mainContent}
                            </Markdown>
                          )}
                        </Box>
                      );
                    })() : <Loading />}
                  </div>
                </div>

              )}
            </div>
          ))
        ) : (
          <NoChat />
        )}

        <div ref={bottomRef} />
      </div>

  );
};

export default ChatField;
