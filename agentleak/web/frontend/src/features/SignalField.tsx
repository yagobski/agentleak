import { useEffect, useRef } from "react"

/** A drifting plume in the field: position, radius and color are all
 * fractions of the canvas size so the composition holds at any viewport. */
interface Plume {
  cx: number
  cy: number
  r: number
  h: number
  s: number
  l: number
  a: number
  fx: number
  fy: number
  phx: number
  phy: number
}

const HERO_PLUMES: Plume[] = [
  // Cool "clean signal" — soft white light, the dominant read.
  { cx: 0.76, cy: 0.28, r: 0.42, h: 0, s: 0, l: 97, a: 0.1, fx: 0.6, fy: 0.8, phx: 0, phy: 1.3 },
  { cx: 0.58, cy: 0.56, r: 0.28, h: 0, s: 0, l: 97, a: 0.055, fx: 0.4, fy: 0.5, phx: 2.1, phy: 0.4 },
  // Warm "leaked signal" — the accent bleeding through the dark, low and slow.
  { cx: 0.71, cy: 0.7, r: 0.2, h: 14, s: 82, l: 54, a: 0.16, fx: 0.35, fy: 0.55, phx: 4.2, phy: 2.8 },
  { cx: 0.85, cy: 0.4, r: 0.13, h: 30, s: 85, l: 56, a: 0.13, fx: 0.5, fy: 0.3, phx: 1.4, phy: 3.6 },
]

const PANEL_PLUMES: Plume[] = [
  { cx: 0.62, cy: 0.22, r: 0.5, h: 0, s: 0, l: 97, a: 0.09, fx: 0.5, fy: 0.7, phx: 0.6, phy: 2.0 },
  { cx: 0.4, cy: 0.55, r: 0.3, h: 16, s: 80, l: 54, a: 0.14, fx: 0.4, fy: 0.5, phx: 3.1, phy: 1.1 },
  { cx: 0.68, cy: 0.72, r: 0.22, h: 30, s: 84, l: 56, a: 0.1, fx: 0.45, fy: 0.35, phx: 2.0, phy: 4.4 },
]

/** Slow ambient canvas backdrop: drifting light/leak plumes over near-black,
 * standing in for the flat blurred-gradient-orb hero every dark SaaS page
 * seems to ship. Cheap (2D canvas, no deps), pauses off-screen and for
 * prefers-reduced-motion, and draws one static frame either way. */
export function SignalField({ variant = "hero" }: { variant?: "hero" | "panel" }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas?.getContext("2d")
    if (!canvas || !ctx) return

    const plumes = variant === "hero" ? HERO_PLUMES : PANEL_PLUMES
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 0
    let h = 0
    let raf = 0
    let start = performance.now()

    function resize() {
      const rect = canvas!.getBoundingClientRect()
      w = rect.width
      h = rect.height
      canvas!.width = Math.round(w * dpr)
      canvas!.height = Math.round(h * dpr)
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    function draw(t: number) {
      ctx!.clearRect(0, 0, w, h)
      ctx!.fillStyle = "#080909"
      ctx!.fillRect(0, 0, w, h)

      ctx!.globalCompositeOperation = "screen"
      for (const p of plumes) {
        const dx = Math.sin(t * p.fx * 0.08 + p.phx) * 0.07
        const dy = Math.cos(t * p.fy * 0.08 + p.phy) * 0.07
        const cx = (p.cx + dx) * w
        const cy = (p.cy + dy) * h
        const r = p.r * Math.max(w, h)
        const grad = ctx!.createRadialGradient(cx, cy, 0, cx, cy, r)
        grad.addColorStop(0, `hsla(${p.h}, ${p.s}%, ${p.l}%, ${p.a})`)
        grad.addColorStop(1, `hsla(${p.h}, ${p.s}%, ${p.l}%, 0)`)
        ctx!.fillStyle = grad
        ctx!.fillRect(0, 0, w, h)
      }
      ctx!.globalCompositeOperation = "source-over"
    }

    function frame(now: number) {
      draw((now - start) / 1000)
      raf = requestAnimationFrame(frame)
    }

    resize()
    if (reduceMotion) {
      draw(0)
    } else {
      raf = requestAnimationFrame(frame)
    }

    function onVisibility() {
      if (reduceMotion) return
      if (document.hidden) {
        cancelAnimationFrame(raf)
      } else {
        start = performance.now()
        raf = requestAnimationFrame(frame)
      }
    }
    window.addEventListener("resize", resize)
    document.addEventListener("visibilitychange", onVisibility)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("resize", resize)
      document.removeEventListener("visibilitychange", onVisibility)
    }
  }, [variant])

  return (
    <div className="al-field-wrap" aria-hidden="true">
      <canvas ref={ref} className="al-field" />
      <span className="al-field-scan" />
    </div>
  )
}

/** Fixed, page-wide film-grain texture — the single cheapest move toward the
 * tactile, non-flat look of a hand-shaded page instead of a flat vector one. */
export function Grain() {
  return <div className="al-grain" aria-hidden="true" />
}
