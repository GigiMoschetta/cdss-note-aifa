import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

const params = new URLSearchParams(window.location.search)
const pdfParam = params.get('pdf')
const root = createRoot(document.getElementById('root')!)

if (pdfParam) {
  // Viewer PDF (con pdfjs) caricato solo su richiesta: non appesantisce la demo.
  import('./components/PdfViewer.tsx').then(({ PdfViewer }) => {
    root.render(
      <StrictMode>
        <PdfViewer
          file={`/${pdfParam}`}
          page={Number(params.get('page')) || 1}
          q={params.get('q') ?? undefined}
        />
      </StrictMode>,
    )
  })
} else {
  import('./App.tsx').then(({ default: App }) => {
    root.render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  })
}
