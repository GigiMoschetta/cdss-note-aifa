// Costruzione dei link "Apri nel PDF" con evidenziazione del passaggio citato.
// I link puntano alla stessa SPA con ?pdf=&page=&q=, che monta il viewer PDF.js
// (il viewer nativo di Chrome ignora i parametri di ricerca: non evidenzia).

/** Estrae una frase breve e distintiva da evidenziare nel PDF. */
const TRIM_EDGES = /^[\s"'“”«».,;:()]+|[\s"'“”«».,;:()]+$/g

export function searchPhrase(text?: string | null): string {
  if (!text) return ''
  const s = text.replace(/\s+/g, ' ').replace(TRIM_EDGES, '')
  // prime ~6 parole, max ~50 caratteri (più corto = match più robusto)
  let phrase = s.split(' ').slice(0, 6).join(' ')
  if (phrase.length > 50) phrase = phrase.slice(0, 50).replace(/\s+\S*$/, '')
  return phrase.replace(TRIM_EDGES, '')
}

/** URL del viewer interno con pagina ed eventuale testo da evidenziare. */
export function pdfHref(pdfFile?: string, page?: number | string, text?: string | null): string {
  if (!pdfFile) return '#'
  const params = new URLSearchParams({ pdf: pdfFile })
  if (page !== undefined && page !== '') params.set('page', String(page))
  const q = searchPhrase(text)
  if (q) params.set('q', q)
  return `/?${params.toString()}`
}
