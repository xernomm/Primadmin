import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";
import { isAuthenticated } from "./utils/Auth";
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/dist/js/bootstrap.bundle.min.js"; // sangat penting
import "./index.css";
import AppLayout from "./components/widgets/AppLayout";
import 'primereact/resources/themes/md-light-deeppurple/theme.css'; 
import 'primereact/resources/primereact.min.css';

import * as bootstrap from 'bootstrap';
window.bootstrap = bootstrap;

const root = ReactDOM.createRoot(document.getElementById("root"));

const ProtectedRoute = ({ children }) => {
  return isAuthenticated() ? children : <Navigate to="/" />;
};

root.render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="chats" element={<ChatPage />} />
        {/* <Route path="settings" element={<SettingsPage />} /> */}
      </Route>
    </Routes>
  </BrowserRouter>
);
