import React from "react";
import { Outlet, useNavigate, Link } from "react-router-dom";
import { Navbar, Nav, Container, Button, NavDropdown } from "react-bootstrap";
import LogoutButton from "../auth/Logout";
import axios from "axios";

const AppLayout = () => {
  const navigate = useNavigate();
  const base = process.env.REACT_APP_API_BASE;

  const handleClearChat = async () => {
    const accessToken = localStorage.getItem("accessToken");

    try {
      await axios.post(`${base}/truncate-chat-history`, {}, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

    } catch (err) {
      // Jika error karena token kedaluwarsa
      if (
        axios.isAxiosError(err) &&
        err.response?.data?.error === "Token kedaluwarsa."
      ) {
        try {
          const refreshToken = localStorage.getItem("refreshToken");

          const refreshResponse = await axios.post(`${base}/api/refresh`, {
            refresh_token: refreshToken,
          });

          const newAccessToken = refreshResponse.data.access_token;
          localStorage.setItem("accessToken", newAccessToken);

          // Retry dengan token baru
          await axios.post(`${base}/truncate-chat-history`, {}, {
            headers: {
              Authorization: `Bearer ${newAccessToken}`,
            },
          });

          alert("Riwayat chat berhasil dihapus setelah refresh token.");
        } catch (refreshErr) {
          console.error("❌ Refresh token gagal:", refreshErr);
          alert("Gagal memperbarui token. Silakan login ulang.");
          navigate("/"); // arahkan ke login
        }
      } else {
        console.error("❌ Gagal menghapus riwayat:", err);
        alert("Gagal menghapus riwayat chat.");
      }
    }
  };

  return (
    <>
      <Navbar bg="dark" variant="dark" expand="lg" sticky="top">
        <Container>
          <Navbar.Brand as={Link} to="/chats" className="fw-bold fs-4">
            <span className="text-danger">Prima</span>dmin.
          </Navbar.Brand>

          <Navbar.Toggle aria-controls="main-navbar" />
          <Navbar.Collapse id="main-navbar">
            <Nav className="me-auto">
              <Nav.Link as={Link} to="/chats">Chat</Nav.Link>

              <NavDropdown title="Opsi Lain" id="main-nav-dropdown">
                <NavDropdown.Item onClick={handleClearChat}>
                  🧹 Clear Chat
                </NavDropdown.Item>
                <NavDropdown.Divider />
                <NavDropdown.Item href="#about">Tentang Aplikasi</NavDropdown.Item>
              </NavDropdown>
            </Nav>

            <LogoutButton />
          </Navbar.Collapse>
        </Container>
      </Navbar>

      <main className="bg-dark vh-100">
        <Outlet />
      </main>
    </>
  );
};

export default AppLayout;
