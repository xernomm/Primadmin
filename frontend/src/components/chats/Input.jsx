import React, { useState } from 'react';
import { FaCircleArrowUp } from "react-icons/fa6";
import { FaTools } from "react-icons/fa";
import { RiCustomerService2Fill } from "react-icons/ri";
import axios from 'axios';
import Button from '@mui/material/Button';
import DeleteIcon from '@mui/icons-material/Delete';
import SendIcon from '@mui/icons-material/Send';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';

import '../../style/Button.css';
import '../../style/Form.css';

const Input = () => {
  const [inputText, setInputText] = useState('');
  const [useTools, setUseTools] = useState(true); // default: true
  const base = process.env.REACT_APP_API_BASE;
  const token = localStorage.getItem('accessToken');

  const fetchResponse = async (prompt) => {
    const endpoint = useTools ? '/ask' : '/ask-rag';
    try {
      await axios.post(`${base}${endpoint}`, { question: prompt }, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
    } catch (error) {
      console.error("Error fetching response:", error);
      alert("Gagal mengambil respon.");
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = inputText.trim();
    if (!trimmed) {
      alert("Masukkan pertanyaan dulu.");
      return;
    }
    fetchResponse(trimmed);
    setInputText('');
  };

  const handleKeyDown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey) {
    e.preventDefault(); // cegah newline
    handleSubmit(e);    // submit form
  }
};

  return (
    <div className='inputBox py-3 px-4 col-12'>


      <form onSubmit={handleSubmit} className="d-flex align-items-center">
        <div className='formInput text-light flex-grow-1'>
          <TextField
            id="standard-multiline-static"
            label="Ask anything.."
            multiline
            maxRows={6}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            variant="standard"
            fullWidth
              InputProps={{
              disableUnderline: true, // hilangkan underline
              style: { color: "white" }, // warna teks
            }}
            InputLabelProps={{
              style: { color: "gray" }, // warna label
            }}
            sx={{
              backgroundColor: "transparent",
              "& .MuiInputBase-root": {
                border: "none",
              },
            }}
          />
        </div>

      </form>

        <div className="buttonInput mt-3">
          <div className="buttonInput mt-3 d-flex justify-content-between align-items-center flex-wrap">
            <div className="d-flex align-items-center gap-2">
            <Button
              variant="outlined"
              onClick={() => setUseTools(prev => !prev)}
              startIcon={useTools ? <FaTools /> : <RiCustomerService2Fill />}
              sx={{
                color: useTools ? "#000" : "#fff",
                backgroundColor: useTools ? "#fff" : "transparent",
                borderColor: "#fff",
                "&:hover": {
                  backgroundColor: useTools ? "#eee" : "#333",
                  borderColor: "#fff",
                },
              }}
            >
              {useTools ? "Managing" : "Asking"}
            </Button>

            </div>
          </div>

        

        <div className=" ms-2">
          <button type="submit" className="sendButton" title="Kirim">
            <FaCircleArrowUp size={34} />
          </button>
        </div>
      </div>
    </div>

    
  );
};

export default Input;
