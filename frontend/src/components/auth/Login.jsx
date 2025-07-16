import React, { useState } from 'react'
import {
  OutlinedInput,
  InputAdornment,
  IconButton,
  Button,
  Alert,
  FormControl,
  InputLabel
} from '@mui/material'
import { Visibility, VisibilityOff } from '@mui/icons-material'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'

const Login = () => {
  const base = process.env.REACT_APP_API_BASE

  const navigate = useNavigate();
  
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const handleClickShowPassword = () => setShowPassword((prev) => !prev)
  const handleMouseDownPassword = (event) => event.preventDefault()
  const handleMouseUpPassword = (event) => event.preventDefault()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    try {
      const res = await axios.post(`${base}/api/login`, {
        email,
        password
      })

    if (res.status === 200) {
      setSuccess('Login berhasil!');
      localStorage.setItem('accessToken', res.data.access_token);
      localStorage.setItem('refreshToken', res.data.refresh_token);
      localStorage.setItem('email', email);
      navigate('/chats');
    }

    } catch (err) {
      const msg = err.response?.data?.error || 'Terjadi kesalahan saat login'
      setError(msg)
    }
  }

  return (
    <div className="col-lg-9 col-sm-12 d-flex justify-content-center align-items-center mt-5">
      <div className="outline bg-light rounded-4 shadow-lg p-4 col-12">
        <p className='lead fw-bold text-center'>Login</p>

        <form onSubmit={handleSubmit} className="d-flex flex-column gap-3">
          {error && <Alert severity="error">{error}</Alert>}
          {success && <Alert severity="success">{success}</Alert>}

          {/* Email */}
          <FormControl variant="outlined" required>
            <InputLabel htmlFor="outlined-adornment-email">Email</InputLabel>
            <OutlinedInput
              id="outlined-adornment-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              label="Email"
            />
          </FormControl>

          {/* Password */}
          <FormControl variant="outlined" required>
            <InputLabel htmlFor="outlined-adornment-password">Password</InputLabel>
            <OutlinedInput
              id="outlined-adornment-password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              endAdornment={
                <InputAdornment position="end">
                  <IconButton
                    aria-label={showPassword ? 'hide password' : 'show password'}
                    onClick={handleClickShowPassword}
                    onMouseDown={handleMouseDownPassword}
                    onMouseUp={handleMouseUpPassword}
                    edge="end"
                  >
                    {showPassword ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              }
              label="Password"
            />
          </FormControl>

          <Button type="submit" color='error' variant='contained' fullWidth>
            Login
          </Button>
        </form>
      </div>

    </div>
  )
}

export default Login
