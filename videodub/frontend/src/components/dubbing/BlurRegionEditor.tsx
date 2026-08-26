import { useEffect, useLayoutEffect, useState, type KeyboardEvent, type RefObject } from 'react'
import { Check, Maximize2, Move } from 'lucide-react'
import { Rnd, type DraggableData, type RndResizeCallback } from 'react-rnd'
import { clampBlurRegion, clampUnit, type BlurRegion } from '@/lib/workflow'

interface BlurRegionEditorProps {
  stageRef: RefObject<HTMLDivElement>
  region: BlurRegion
  subtitleY: number
  editing: boolean
  onRegionChange: (region: BlurRegion) => void
  onSubtitleYChange: (value: number) => void
  onEditModeChange: (editing: boolean) => void
}

interface StageSize {
  width: number
  height: number
}

const MIN_REGION_RATIO = 0.02
const SUBTITLE_LABEL_HEIGHT = 34

function getStageSize(stage: HTMLDivElement | null): StageSize {
  if (!stage) return { width: 1, height: 1 }
  const rect = stage.getBoundingClientRect()
  return {
    width: Math.max(rect.width, 1),
    height: Math.max(rect.height, 1),
  }
}

function normalizeRegionFromPixels(
  x: number,
  y: number,
  width: number,
  height: number,
  stageSize: StageSize,
): BlurRegion {
  return clampBlurRegion({
    x: x / stageSize.width,
    y: y / stageSize.height,
    width: width / stageSize.width,
    height: height / stageSize.height,
  })
}

function nudgeRegion(region: BlurRegion, dx: number, dy: number): BlurRegion {
  return clampBlurRegion({
    ...region,
    x: region.x + dx,
    y: region.y + dy,
  })
}

function nudgeSubtitle(value: number, delta: number): number {
  return clampUnit(value + delta)
}

function handleKeyDown(
  event: KeyboardEvent<HTMLElement>,
  region: BlurRegion,
  onChange: (region: BlurRegion) => void,
) {
  const step = event.shiftKey ? 0.02 : 0.005
  let dx = 0
  let dy = 0
  if (event.key === 'ArrowLeft') dx = -step
  if (event.key === 'ArrowRight') dx = step
  if (event.key === 'ArrowUp') dy = -step
  if (event.key === 'ArrowDown') dy = step
  if (!dx && !dy) return
  event.preventDefault()
  onChange(nudgeRegion(region, dx, dy))
}

function ResizeHandle() {
  return <span className="block h-3 w-3 rounded-full border border-accent-cyan bg-surface-950 shadow-sm shadow-black/50" aria-hidden="true" />
}

export default function BlurRegionEditor({
  stageRef,
  region,
  subtitleY,
  editing,
  onRegionChange,
  onSubtitleYChange,
  onEditModeChange,
}: BlurRegionEditorProps) {
  const [stageSize, setStageSize] = useState<StageSize>(() => getStageSize(stageRef.current))

  useLayoutEffect(() => {
    const stage = stageRef.current
    if (!stage) return undefined

    const measure = () => setStageSize(getStageSize(stage))
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(stage)
    window.addEventListener('resize', measure)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [stageRef])

  useEffect(() => {
    if (!editing) return undefined
    const frame = window.requestAnimationFrame(() => setStageSize(getStageSize(stageRef.current)))
    return () => window.cancelAnimationFrame(frame)
  }, [editing, stageRef])

  const regionPixels = {
    x: region.x * stageSize.width,
    y: region.y * stageSize.height,
    width: region.width * stageSize.width,
    height: region.height * stageSize.height,
  }
  const subtitleLabelWidth = Math.max(80, Math.min(stageSize.width * 0.74, Math.max(stageSize.width - 24, 80)))
  const subtitleLabelX = Math.max(12, (stageSize.width - subtitleLabelWidth) / 2)
  const subtitleLabelY = Math.min(
    Math.max(subtitleY * stageSize.height - SUBTITLE_LABEL_HEIGHT / 2, 8),
    Math.max(stageSize.height - SUBTITLE_LABEL_HEIGHT - 8, 8),
  )
  const canResize = stageSize.width > 1 && stageSize.height > 1

  const handleRegionDragStop = (_event: unknown, data: DraggableData) => {
    onRegionChange(normalizeRegionFromPixels(
      data.x,
      data.y,
      regionPixels.width,
      regionPixels.height,
      stageSize,
    ))
  }

  const handleRegionResizeStop: RndResizeCallback = (_event, _direction, elementRef, _delta, position) => {
    onRegionChange(normalizeRegionFromPixels(
      position.x,
      position.y,
      elementRef.offsetWidth,
      elementRef.offsetHeight,
      stageSize,
    ))
  }

  const handleSubtitleDragStop = (_event: unknown, data: DraggableData) => {
    const nextY = clampUnit((data.y + SUBTITLE_LABEL_HEIGHT / 2) / stageSize.height)
    onSubtitleYChange(nextY)
  }

  return (
    <div className="pointer-events-none absolute inset-0 z-30">
      <div className="pointer-events-auto absolute left-3 top-3 flex flex-wrap items-center gap-2 rounded-xl border border-surface-700/70 bg-surface-950/90 p-2 shadow-xl shadow-black/30 backdrop-blur-md">
        {!editing ? (
          <button
            type="button"
            onClick={() => onEditModeChange(true)}
            className="inline-flex min-h-9 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-surface-200 transition-colors hover:bg-surface-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-primary-500/60"
            aria-label="Chỉnh vùng làm mờ phụ đề cũ"
          >
            <Maximize2 className="h-4 w-4 text-accent-cyan" aria-hidden="true" />
            Chỉnh vùng làm mờ
          </button>
        ) : (
          <>
            <span className="inline-flex items-center gap-2 px-1 text-xs font-medium text-accent-cyan">
              <Move className="h-4 w-4" aria-hidden="true" />
              Đang chỉnh vùng
            </span>
            <button
              type="button"
              onClick={() => onEditModeChange(false)}
              className="inline-flex min-h-9 items-center gap-2 rounded-lg bg-accent-cyan/15 px-3 py-2 text-xs font-medium text-accent-cyan transition-colors hover:bg-accent-cyan/25 focus:outline-none focus:ring-2 focus:ring-accent-cyan/60"
            >
              <Check className="h-4 w-4" aria-hidden="true" />
              Xong
            </button>
          </>
        )}
      </div>

      {editing && canResize && (
        <>
          <Rnd
            bounds="parent"
            position={{ x: regionPixels.x, y: regionPixels.y }}
            size={{ width: regionPixels.width, height: regionPixels.height }}
            minWidth={Math.max(32, stageSize.width * MIN_REGION_RATIO)}
            minHeight={Math.max(24, stageSize.height * MIN_REGION_RATIO)}
            enableResizing={{
              top: true,
              right: true,
              bottom: true,
              left: true,
              topRight: true,
              bottomRight: true,
              bottomLeft: true,
              topLeft: true,
            }}
            resizeHandleComponent={{
              top: <ResizeHandle />,
              right: <ResizeHandle />,
              bottom: <ResizeHandle />,
              left: <ResizeHandle />,
              topRight: <ResizeHandle />,
              bottomRight: <ResizeHandle />,
              bottomLeft: <ResizeHandle />,
              topLeft: <ResizeHandle />,
            }}
            resizeHandleStyles={{
              top: { width: 22, height: 14, top: -7, left: 'calc(50% - 11px)', cursor: 'ns-resize' },
              right: { width: 14, height: 22, right: -7, top: 'calc(50% - 11px)', cursor: 'ew-resize' },
              bottom: { width: 22, height: 14, bottom: -7, left: 'calc(50% - 11px)', cursor: 'ns-resize' },
              left: { width: 14, height: 22, left: -7, top: 'calc(50% - 11px)', cursor: 'ew-resize' },
              topRight: { width: 18, height: 18, right: -9, top: -9, cursor: 'nesw-resize' },
              bottomRight: { width: 18, height: 18, right: -9, bottom: -9, cursor: 'nwse-resize' },
              bottomLeft: { width: 18, height: 18, left: -9, bottom: -9, cursor: 'nesw-resize' },
              topLeft: { width: 18, height: 18, left: -9, top: -9, cursor: 'nwse-resize' },
            }}
            onDragStop={handleRegionDragStop}
            onResizeStop={handleRegionResizeStop}
            onKeyDown={(event: KeyboardEvent<HTMLElement>) => handleKeyDown(event, region, onRegionChange)}
            role="region"
            aria-label="Vùng làm mờ phụ đề cũ"
            tabIndex={0}
            className="pointer-events-auto border-2 border-accent-cyan bg-accent-cyan/10 shadow-[0_0_0_1px_rgba(2,6,23,0.5)] outline-none focus:ring-2 focus:ring-accent-cyan/70"
          >
            <span className="pointer-events-none absolute left-2 top-2 rounded bg-surface-950/75 px-2 py-1 text-[10px] font-medium text-accent-cyan">
              Vùng làm mờ phụ đề cũ
            </span>
          </Rnd>

          <Rnd
            bounds="parent"
            position={{ x: subtitleLabelX, y: subtitleLabelY }}
            size={{ width: subtitleLabelWidth, height: SUBTITLE_LABEL_HEIGHT }}
            enableResizing={false}
            dragAxis="y"
            onDragStop={handleSubtitleDragStop}
            onKeyDown={(event: KeyboardEvent<HTMLElement>) => {
              const step = event.shiftKey ? 0.02 : 0.005
              if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
                event.preventDefault()
                onSubtitleYChange(nudgeSubtitle(subtitleY, event.key === 'ArrowUp' ? -step : step))
              }
              if (event.key === 'Home' || event.key === 'End') {
                event.preventDefault()
                onSubtitleYChange(event.key === 'Home' ? 0.05 : 0.95)
              }
            }}
            role="slider"
            aria-label="Vị trí nhãn phụ đề mới"
            aria-valuemin={0}
            aria-valuemax={1}
            aria-valuenow={Number(subtitleY.toFixed(3))}
            aria-valuetext={`${Math.round(subtitleY * 100)} phần trăm chiều cao video`}
            tabIndex={0}
            className="pointer-events-auto flex cursor-ns-resize items-center justify-center rounded-lg border border-white/80 bg-surface-950/75 px-3 text-xs font-medium text-white shadow-lg shadow-black/30 outline-none focus:ring-2 focus:ring-white/80"
          >
            <span className="truncate">Nhấn kéo để đặt phụ đề mới</span>
          </Rnd>

          <div className="pointer-events-auto absolute bottom-3 left-1/2 -translate-x-1/2 rounded-lg border border-surface-700/70 bg-surface-950/90 px-3 py-2 text-center text-[11px] leading-4 text-surface-300 shadow-lg shadow-black/25 backdrop-blur-md">
            Kéo khung để di chuyển · Kéo cạnh/góc để đổi kích thước
            <span className="ml-1 text-surface-500">• Shift + mũi tên = nhanh hơn</span>
          </div>
        </>
      )}
    </div>
  )
}
