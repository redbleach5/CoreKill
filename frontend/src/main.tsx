import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import AppWithIDECompat from './AppWithIDECompat.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppWithIDECompat />
  </StrictMode>,
)
