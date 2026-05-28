import { useState } from 'react'
import { LayoutTemplate, CheckCircle2 } from 'lucide-react'
import TemplateGallery from '@/components/TemplateGallery'
import TemplateForm from '@/components/TemplateForm'

export default function SmartPoster() {
  const [selectedTemplate, setSelectedTemplate] = useState(null)

  return (
    <div className="space-y-5 sm:space-y-6">
      <div>
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <div className="w-8 h-8 rounded-xl bg-violet-400/15 flex items-center justify-center shrink-0">
            <LayoutTemplate className="w-4 h-4 text-violet-400" />
          </div>
          <h2 className="font-space text-xl sm:text-2xl font-bold">Smart Poster</h2>
          <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-violet-400 text-white">FREE</span>
        </div>
        <p className="text-muted text-sm">Pick a professionally designed template, upload your images, fill in the text — done.</p>
      </div>

      {!selectedTemplate && (
        <div className="flex flex-wrap gap-3 sm:gap-4 text-xs text-muted">
          {['Instant generation', '9 premium templates', 'Influencer image optional', 'No account needed'].map(t => (
            <span key={t} className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-violet-400 shrink-0" /> {t}
            </span>
          ))}
        </div>
      )}

      {selectedTemplate ? (
        <TemplateForm
          template={selectedTemplate}
          onBack={() => setSelectedTemplate(null)}
        />
      ) : (
        <TemplateGallery onSelectTemplate={setSelectedTemplate} />
      )}
    </div>
  )
}
