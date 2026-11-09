import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import LicenseGate from './components/license/LicenseGate'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <LicenseGate>
        <App />
      </LicenseGate>
    </BrowserRouter>
  </React.StrictMode>,
)
