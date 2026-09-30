import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

/**
 * Thin React wrapper around uPlot, whose API is imperative. Keeping the
 * instance in a ref means the rest of the UI never touches it directly.
 */
export function Chart({ data, series, markers = [], height = 320, yRange, yLabel }) {
  const containerRef = useRef(null)
  const plotRef = useRef(null)

  // Read through a ref inside the draw hook so new waterings repaint without
  // tearing down and rebuilding the whole plot on every fetch.
  const markersRef = useRef(markers)
  markersRef.current = markers

  useEffect(() => {
    const container = containerRef.current
    if (!container) return undefined

    const plot = new uPlot(
      {
        width: container.clientWidth || 600,
        height,
        // Timestamps arrive as epoch seconds, which is uPlot's native x format.
        scales: { x: { time: true }, y: yRange ? { range: yRange } : {} },
        legend: { live: true },
        cursor: { drag: { x: true, y: false } },
        axes: [
          { stroke: '#8fae9c', grid: { stroke: 'rgba(143, 174, 156, 0.12)' } },
          {
            stroke: '#8fae9c',
            label: yLabel,
            grid: { stroke: 'rgba(143, 174, 156, 0.12)' },
          },
        ],
        series,
        hooks: {
          draw: [
            (u) => {
              const { ctx } = u
              ctx.save()
              ctx.strokeStyle = 'rgba(125, 200, 255, 0.55)'
              ctx.lineWidth = 1
              ctx.setLineDash([4, 3])
              for (const marker of markersRef.current) {
                const x = u.valToPos(marker.t, 'x', true)
                if (x < u.bbox.left || x > u.bbox.left + u.bbox.width) continue
                ctx.beginPath()
                ctx.moveTo(x, u.bbox.top)
                ctx.lineTo(x, u.bbox.top + u.bbox.height)
                ctx.stroke()
              }
              ctx.restore()
            },
          ],
        },
      },
      data,
      container,
    )
    plotRef.current = plot

    const observer = new ResizeObserver(() => {
      plot.setSize({ width: container.clientWidth || 600, height })
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      plot.destroy()
      plotRef.current = null
    }
    // Rebuilt only when the plot's shape changes, not when its data does.
  }, [series, height, yRange, yLabel])

  useEffect(() => {
    plotRef.current?.setData(data)
  }, [data])

  return <div className="chart" ref={containerRef} />
}
