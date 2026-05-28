import { Loader2, WandSparkles, ImagePlus, Download, Sparkles } from 'lucide-react'

const posterSteps = [
  { label: 'Uploading images', icon: ImagePlus },
  { label: 'Preparing safe ad layout', icon: WandSparkles },
  { label: 'Compositing product stage and typography', icon: Loader2 },
  { label: 'Ready to download', icon: Download },
]

const creativeSteps = [
  { label: 'Uploading images', icon: ImagePlus },
  { label: 'Building clean reference composition', icon: WandSparkles },
  { label: 'Calling AI creative refinement if configured', icon: Sparkles },
  { label: 'Adding readable marketing text', icon: Download },
]

export default function ProcessingStatus({ currentStep = 0, mode = 'poster' }) {
  const steps = mode === 'ai_creative' ? creativeSteps : posterSteps
  return (
    <div className="glass rounded-3xl p-8 w-full max-w-xl">
      <div className="flex items-center gap-3 mb-6">
        <Loader2 className="w-6 h-6 text-primary animate-spin" />
        <div>
          <h3 className="font-space text-xl font-bold">Generating your ad creative</h3>
          <p className="text-sm text-muted">AI modes can take longer depending on Hugging Face provider response.</p>
        </div>
      </div>
      <div className="space-y-3">
        {steps.map((step, index) => {
          const Icon = step.icon
          const active = index <= currentStep
          return (
            <div key={step.label} className="flex items-center gap-3">
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${active ? 'bg-primary/20 text-primary' : 'bg-white/5 text-muted'}`}><Icon className="w-4 h-4" /></div>
              <span className={active ? 'text-white font-medium' : 'text-muted'}>{step.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
