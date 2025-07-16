import React from "react";
import { Navbar, Container, Nav } from "react-bootstrap";
import { FiMenu } from "react-icons/fi";

const AppNavbar = ({ toggleSidebar }) => {
  return (
    <Navbar expand="lg" bg="dark" variant="dark" sticky="top">
      <Container>
        {/* Hamburger button */}
        <button
          className="btn btn-outline-primary me-2 d-lg-none"
          onClick={toggleSidebar}
        >
          <FiMenu size={20} />
        </button>

        {/* Brand Title */}
        <Navbar.Brand className="fw-bold fs-4">
          <span className="text-danger">Prima</span>dmin.
        </Navbar.Brand>

        <Navbar.Toggle aria-controls="basic-navbar-nav" />

        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="ms-auto">
            <Nav.Link href="/chats">Chat</Nav.Link>
            <Nav.Link href="/settings">Pengaturan</Nav.Link>
            {/* Tambah Nav lainnya jika perlu */}
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
};

export default AppNavbar;
