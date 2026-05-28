import { Instagram, Linkedin, Rocket, Crown, Youtube } from 'lucide-react'
import { cn } from '@/lib/utils'

export const styles = [
  { id: 'instagram_ad', label: 'Instagram Ad', desc: 'Square social creative', icon: Instagram },
  { id: 'linkedin_post', label: 'LinkedIn Promo', desc: 'Professional business post', icon: Linkedin },
  { id: 'product_poster', label: 'Launch Poster', desc: 'Bold product campaign', icon: Rocket },
  { id: 'brand_ambassador', label: 'Brand Ambassador', desc: 'Premium editorial look', icon: Crown },
  { id: 'youtube_thumbnail', label: 'YouTube Thumbnail', desc: 'High-click 16:9 creative', icon: Youtube },
]

export default function StyleSelector({ selected, onSelect }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-space text-lg font-bold">Choose output style</h3>
          <p className="text-sm text-muted">Each style creates a different final image size and layout.</p>
        </div>
      </div>
      <div className="grid md:grid-cols-5 gap-3">
        {styles.map((style) => {
          const Icon = style.icon
          const active = selected === style.id
          return (
            <button key={style.id} type="button" onClick={() => onSelect(style.id)} className={cn('text-left rounded-2xl border p-4 transition-all hover:bg-white/8', active ? 'border-primary bg-primary/15 shadow-lg shadow-primary/10' : 'border-border bg-white/[0.03]')}>
              <Icon className={cn('w-5 h-5 mb-3', active ? 'text-primary' : 'text-muted')} />
              <div className="text-sm font-bold">{style.label}</div>
              <div className="text-xs text-muted mt-1 leading-relaxed">{style.desc}</div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
