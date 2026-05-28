import { useState } from 'react'
import Navbar from '@/components/Navbar'
import FeatureStrip from '@/components/FeatureStrip'
import BackgroundRemover from '@/pages/BackgroundRemover'
import ChangeBackground from '@/pages/ChangeBackground'
import SmartPoster from '@/pages/SmartPoster'
import PhotoStudio from '@/pages/PhotoStudio'
import ImageTools from '@/pages/ImageTools'

export default function App() {
  const [feature, setFeature] = useState('remove-bg')

  return (
    <div className="min-h-screen bg-hero-gradient">
      <Navbar activeFeature={feature} onNavigate={setFeature} />

      <main className="max-w-6xl mx-auto px-3 sm:px-4 lg:px-6 py-4 sm:py-6 space-y-4 sm:space-y-6">
        <FeatureStrip active={feature} onSelect={setFeature} />

        <div className="animate-fade-up" key={feature}>
          {feature === 'remove-bg'    && <BackgroundRemover />}
          {feature === 'change-bg'    && <ChangeBackground />}
          {feature === 'smart-poster' && <SmartPoster />}
          {feature === 'photo-studio' && <PhotoStudio />}
          {feature === 'image-tools'  && <ImageTools />}
        </div>
      </main>

      <footer className="border-t border-white/[0.06] mt-16 py-6 text-center">
        <p className="text-xs text-white/25">
          Pixolab — Free online image editor · pixolab.online · No account required.
        </p>
      </footer>
    </div>
  )
}
