// theme.js
import { createTheme } from '@mui/material/styles'

const theme = createTheme({
  palette: {
    primary: {
      main: '#007FFF',
      dark: '#0066CC',
      contrastText: '#fff'
    },
    background: {
      default: '#F0F4FF',
      paper: '#ffffff'
    }
  },
  components: {
    MuiBox: {
      styleOverrides: {
        root: {
          borderColor: '#007FFF'
        }
      }
    }
  },
  typography: {
    fontFamily: 'Roboto, sans-serif'
  }
})

export default theme
