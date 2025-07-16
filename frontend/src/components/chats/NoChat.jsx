import React from 'react';
import ai from '../../img/Vanka-logo.png';
import '../../style/ChatBox.css';

const NoChat = () => {
  return (
    <div className='col-12 d-flex justify-content-center align-items-center 100vh'>
      <div className="col-12 d-flex flex-column justify-content-center align-items-center">
        <img src={ai} alt="AI Logo" className='vankaImg' />
        <p className="lead text-white text-center">Apa yang anda ingin lakukan hari ini?</p>
      </div>
    </div>
  );
};

export default NoChat;
