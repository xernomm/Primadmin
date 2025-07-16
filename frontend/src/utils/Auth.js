export const getAuth = () => ({
  accessToken: localStorage.getItem('accessToken'),
  refreshToken: localStorage.getItem('refreshToken'),
  email: localStorage.getItem('email'),
});

// src/utils/auth.js
export const isAuthenticated = () => {
  const accessToken = localStorage.getItem('accessToken');
  const refreshToken = localStorage.getItem('refreshToken');
  const email = localStorage.getItem('email');

  return !!(accessToken && refreshToken && email); // akan true kalau ketiganya ada
};
