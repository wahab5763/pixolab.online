const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

async function request(path, options = {}, timeoutMs = 120_000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_URL}${path}`, { ...options, signal: controller.signal })
    const contentType = res.headers.get('content-type') || ''
    const payload = contentType.includes('application/json') ? await res.json() : await res.text()
    if (!res.ok) {
      const detail = payload?.detail || payload?.message || payload || 'Request failed'
      throw new Error(detail)
    }
    return payload
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Request timed out. Please try again.')
    throw err
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  templates: () => request('/generation/templates'),
  generateFromTemplate: (formData) => request('/generation/generate-template', { method: 'POST', body: formData }),
  generate: (formData) => request('/generation/generate', { method: 'POST', body: formData }),
}
