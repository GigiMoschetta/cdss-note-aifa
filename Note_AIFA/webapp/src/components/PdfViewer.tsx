import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ExternalLink } from 'lucide-react'
// @ts-expect-error — pdfjs-dist build non espone i tipi del bundle .mjs
import * as pdfjsLib from 'pdfjs-dist/build/pdf.mjs'
// @ts-expect-error — i componenti viewer non hanno tipi pubblicati
import { EventBus, PDFFindController, PDFLinkService, PDFViewer as PdfJsViewer } from 'pdfjs-dist/web/pdf_viewer.mjs'
import 'pdfjs-dist/web/pdf_viewer.css'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc

export function PdfViewer({ file, page, q }: { file: string; page: number; q?: string }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false

    const eventBus = new EventBus()
    const linkService = new PDFLinkService({ eventBus })
    const findController = new PDFFindController({ eventBus, linkService })
    const viewer = new PdfJsViewer({ container, eventBus, linkService, findController })
    linkService.setViewer(viewer)

    const onPagesInit = () => {
      viewer.currentScaleValue = 'page-width'
      if (page > 1) viewer.currentPageNumber = page
      if (q && q.trim()) {
        eventBus.dispatch('find', {
          source: null,
          type: '',
          query: q,
          caseSensitive: false,
          entireWord: false,
          highlightAll: true,
          findPrevious: false,
          matchDiacritics: false,
        })
      }
    }
    eventBus.on('pagesinit', onPagesInit)

    const task = pdfjsLib.getDocument({ url: file })
    task.promise.then(
      (doc: unknown) => {
        if (cancelled) return
        viewer.setDocument(doc)
        linkService.setDocument(doc, null)
      },
      (err: { message?: string }) => !cancelled && setError(String(err?.message ?? err)),
    )

    return () => {
      cancelled = true
      eventBus.off('pagesinit', onPagesInit)
      try { task.destroy() } catch { /* noop */ }
      try { viewer.cleanup() } catch { /* noop */ }
    }
  }, [file, page, q])

  const fileName = file.replace(/^\//, '')

  return (
    <div className="fixed inset-0 bg-[#525659]">
      <div className="flex h-11 items-center gap-3 border-b border-black/20 bg-[#323639] px-4 text-white">
        <button
          onClick={() => (window.history.length > 1 ? window.history.back() : window.close())}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[13px] font-medium hover:bg-white/10"
        >
          <ArrowLeft size={15} /> Torna alla demo
        </button>
        <span className="font-mono text-[12.5px] text-white/80">{fileName}</span>
        {q && (
          <span className="rounded-full bg-[var(--color-brand)] px-2 py-0.5 text-[11px] font-semibold">
            evidenziato: “{q}”
          </span>
        )}
        <a
          href={`/${fileName}#page=${page}`}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto flex items-center gap-1 rounded-md px-2 py-1 text-[12px] text-white/70 hover:bg-white/10"
        >
          Apri grezzo <ExternalLink size={12} />
        </a>
      </div>
      {error ? (
        <div className="p-8 text-[14px] text-white">Impossibile caricare il PDF: {error}</div>
      ) : (
        <div ref={containerRef} className="pdfViewerContainer absolute inset-x-0 bottom-0 top-11 overflow-auto">
          <div className="pdfViewer" />
        </div>
      )}
    </div>
  )
}
