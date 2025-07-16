import React from "react";
import { Button } from "@mui/material";
import LogoutIcon from "@mui/icons-material/Logout";
import axios from "axios";
import { useNavigate } from "react-router";



const LogoutButton = ({ onLoggedOut }) => {

const base = process.env.REACT_APP_API_BASE;
const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      const accessToken = localStorage.getItem("accessToken");

      const response = await axios.post(
        `${base}/api/logout`,
        {},
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      );

      console.log(response.data.message);

      // Bersihkan localStorage
      localStorage.removeItem("accessToken");
      localStorage.removeItem("refreshToken");
      navigate('/');

      // Callback setelah logout
      if (onLoggedOut) onLoggedOut();
    } catch (err) {
      // Cek jika token expired
      if (
        axios.isAxiosError(err) &&
        err.response?.data?.error === "Token kedaluwarsa."
      ) {
        console.warn("🔁 Access token expired. Refreshing...");

        try {
          const refreshToken = localStorage.getItem("refreshToken");
          const refreshResponse = await axios.post(`${base}/api/refresh`, {
            refresh_token: refreshToken,
          });

          const newAccessToken = refreshResponse.data.access_token;
          localStorage.setItem("accessToken", newAccessToken);

          // Coba logout ulang setelah refresh token
          await handleLogout();
        } catch (refreshErr) {
          console.error("❌ Refresh token gagal:", refreshErr);
        }
      } else {
        console.error("❌ Logout gagal:", err);
      }
    }
  };

  return (
    <Button
      variant="outlined"
      color="error"
      startIcon={<LogoutIcon />}
      onClick={handleLogout}
    >
      Logout
    </Button>
  );
};

export default LogoutButton;
