import { useState, useRef, useEffect } from 'react'
import {
  Type, Image, Plus, Trash2, Square, AlignLeft, AlignCenter, AlignRight,
  Download, RotateCcw, Sparkles, Layers, Droplet, MousePointer2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  FontPreset, FONT_PRESETS, SubtitleConfig, TextOverlay, ImageOverlay,
  ASPECT_RATIOS
} from '@/lib/utils'

interface SubtitleEditorProps {
  config: SubtitleConfig
  onChange: (config: SubtitleConfig) => void
  onReset: () => void
  videoAspectRatio?: number
  sampleText?: string
}

export function SubtitleEditor({
  config,
  onChange,
  onReset,
  videoAspectRatio = 16/9,
  sampleText = 'Phụ đề mẫu - Kéo thả để di chuyển vị trí'
}: SubtitleEditorProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [dragTarget, setDragTarget] = useState<'subtitle' | 'text' | 'image' | null>(null)
  const [dragIndex, setDragIndex] = useState<number>(-1)
  const [activeTab, setActiveTab] = useState<'main' | 'presets' | 'overlays' | 'text' | 'images'>('main')
  const [newTextOverlay, setNewTextOverlay] = useState('')
  const [editingTextIndex, setEditingTextIndex] = useState<number>(-1)
  const [editingTextValue, setEditingTextValue] = useState('')

  const previewRef = useRef<HTMLDivElement>(null)
  const subtitleRef = useRef<HTMLDivElement>(null)

  // Handle drag to reposition subtitle
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>, target: 'subtitle' | 'text' | 'image', index: number = -1) => {
    if (!config.use_custom_position && target === 'subtitle') return
    if (target === 'text' && index === -1) return
    if (target === 'image' && index === -1) return
    e.preventDefault()
    setIsDragging(true)
    setDragTarget(target)
    setDragIndex(index)
  }

  const handleMouseMove = (e: globalThis.MouseEvent) => {
    if (!isDragging || !previewRef.current) return

    const rect = previewRef.current.getBoundingClientRect()
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))

    if (dragTarget === 'subtitle' && config.use_custom_position) {
      onChange({ ...config, custom_x: x, custom_y: y })
    } else if (dragTarget === 'text' && dragIndex >= 0) {
      const newOverlays = [...config.text_overlays]
      newOverlays[dragIndex] = { ...newOverlays[dragIndex], x, y }
      onChange({ ...config, text_overlays: newOverlays })
    } else if (dragTarget === 'image' && dragIndex >= 0) {
      const newOverlays = [...config.image_overlays]
      newOverlays[dragIndex] = { ...newOverlays[dragIndex], x, y }
      onChange({ ...config, image_overlays: newOverlays })
    }
  }

  const handleMouseUp = () => {
    setIsDragging(false)
    setDragTarget(null)
    setDragIndex(-1)
  }

  useEffect(() => {
    if (!isDragging) return
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  // Calculate subtitle position for preview
  const getSubtitlePosition = () => {
    if (config.use_custom_position && config.custom_x !== null && config.custom_y !== null) {
      return {
        left: `${config.custom_x * 100}%`,
        top: `${config.custom_y * 100}%`,
        transform: 'translate(-50%, -50%)'
      }
    }

    const positions: Record<number, { left: string; top: string; transform: string }> = {
      1: { left: '0%', top: '100%', transform: 'translate(0, -100%)' },
      2: { left: '50%', top: '100%', transform: 'translate(-50%, -100%)' },
      3: { left: '100%', top: '100%', transform: 'translate(-100%, -100%)' },
      4: { left: '0%', top: '50%', transform: 'translate(0, -50%)' },
      5: { left: '50%', top: '50%', transform: 'translate(-50%, -50%)' },
      6: { left: '100%', top: '50%', transform: 'translate(-100%, -50%)' },
      7: { left: '0%', top: '0%', transform: 'translate(0, 0)' },
      8: { left: '50%', top: '0%', transform: 'translate(-50%, 0)' },
      9: { left: '100%', top: '0%', transform: 'translate(-100%, 0)' },
    }
    return positions[config.alignment] || positions[2]
  }

  const pos = getSubtitlePosition()

  const subtitleStyle: React.CSSProperties = {
    position: 'absolute',
    left: pos.left,
    top: pos.top,
    transform: pos.transform,
    fontFamily: config.font_family,
    fontSize: `${config.font_size}px`,
    color: config.font_color,
    WebkitTextStroke: `${config.outline_width}px ${config.outline_color}`,
    textShadow: config.shadow_enabled
      ? `${config.shadow_offset_x}px ${config.shadow_offset_y}px 0 ${config.shadow_color}, ` +
        `${-config.shadow_offset_x}px ${config.shadow_offset_y}px 0 ${config.shadow_color}, ` +
        `${config.shadow_offset_x}px ${-config.shadow_offset_y}px 0 ${config.shadow_color}, ` +
        `${-config.shadow_offset_x}px ${-config.shadow_offset_y}px 0 ${config.shadow_color}`
      : 'none',
    textAlign: config.alignment % 3 === 1 ? 'left' : config.alignment % 3 === 0 ? 'right' : 'center',
    padding: `0 ${config.margin_l}px 0 ${config.margin_r}px`,
    marginBottom: `${config.margin_v}px`,
    pointerEvents: (config.use_custom_position || dragTarget === 'subtitle') ? 'all' : 'none',
    cursor: config.use_custom_position ? 'grab' : 'default',
    whiteSpace: 'nowrap',
    userSelect: 'none',
    transition: isDragging ? 'none' : 'transform 0.1s ease',
  }

  const updateConfig = (updates: Partial<SubtitleConfig>) => {
    onChange({ ...config, ...updates })
  }

  const applyFontPreset = (preset: FontPreset) => {
    updateConfig({
      font_family: preset.font_family,
      font_size: preset.font_size,
      font_color: preset.font_color,
      outline_color: preset.outline_color,
      outline_width: preset.outline_width,
      shadow_enabled: preset.shadow_enabled,
      shadow_color: preset.shadow_color,
      shadow_offset_x: preset.shadow_offset_x,
      shadow_offset_y: preset.shadow_offset_y,
      animation: preset.animation,
      animation_speed: preset.animation_speed,
      font_preset_id: preset.id,
    })
  }

  const addTextOverlay = () => {
    if (!newTextOverlay.trim()) return
    const newOverlay: TextOverlay = {
      id: `text_${Date.now()}`,
      text: newTextOverlay,
      font_family: config.font_family,
      font_size: config.font_size,
      font_color: config.font_color,
      outline_color: config.outline_color,
      outline_width: config.outline_width,
      shadow_enabled: config.shadow_enabled,
      shadow_color: config.shadow_color,
      shadow_offset_x: config.shadow_offset_x,
      shadow_offset_y: config.shadow_offset_y,
      x: 0.5,
      y: 0.1,
      animation: config.animation,
      animation_speed: config.animation_speed,
    }
    updateConfig({ text_overlays: [...config.text_overlays, newOverlay] })
    setNewTextOverlay('')
  }

  const removeTextOverlay = (index: number) => {
    const newOverlays = config.text_overlays.filter((_, i) => i !== index)
    updateConfig({ text_overlays: newOverlays })
  }

  const updateTextOverlay = (index: number, updates: Partial<TextOverlay>) => {
    const newOverlays = [...config.text_overlays]
    newOverlays[index] = { ...newOverlays[index], ...updates }
    updateConfig({ text_overlays: newOverlays })
  }

  const startEditingText = (index: number) => {
    setEditingTextIndex(index)
    setEditingTextValue(config.text_overlays[index].text)
  }

  const saveEditingText = () => {
    if (editingTextIndex >= 0) {
      updateTextOverlay(editingTextIndex, { text: editingTextValue })
    }
    setEditingTextIndex(-1)
    setEditingTextValue('')
  }

  const addImageOverlay = (imageData: string) => {
    const newOverlay: ImageOverlay = {
      id: `image_${Date.now()}`,
      image_data: imageData,
      x: 0.9,
      y: 0.1,
      scale: 0.15,
      opacity: 1.0,
      rotation: 0,
    }
    updateConfig({ image_overlays: [...config.image_overlays, newOverlay] })
  }

  const removeImageOverlay = (index: number) => {
    const newOverlays = config.image_overlays.filter((_, i) => i !== index)
    updateConfig({ image_overlays: newOverlays })
  }

  const updateImageOverlay = (index: number, updates: Partial<ImageOverlay>) => {
    const newOverlays = [...config.image_overlays]
    newOverlays[index] = { ...newOverlays[index], ...updates }
    updateConfig({ image_overlays: newOverlays })
  }

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (event) => {
      if (event.target?.result) {
        addImageOverlay(event.target.result as string)
      }
    }
    reader.readAsDataURL(file)
  }

  const ALIGNMENT_OPTIONS = [
    { value: 1, label: 'Trái dưới', icon: AlignLeft },
    { value: 2, label: 'Giữa dưới', icon: AlignCenter },
    { value: 3, label: 'Phải dưới', icon: AlignRight },
    { value: 4, label: 'Trái giữa', icon: AlignLeft },
    { value: 5, label: 'Giữa giữa', icon: AlignCenter },
    { value: 6, label: 'Phải giữa', icon: AlignRight },
    { value: 7, label: 'Trái trên', icon: AlignLeft },
    { value: 8, label: 'Giữa trên', icon: AlignCenter },
    { value: 9, label: 'Phải trên', icon: AlignRight },
  ]

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="glass-card !p-1 flex gap-1" role="tablist">
        {[
          { id: 'main', label: 'Chính', icon: Type },
          { id: 'presets', label: 'Mẫu chữ', icon: Sparkles },
          { id: 'overlays', label: 'Chèn thêm', icon: Layers },
          { id: 'text', label: 'Văn bản', icon: Type },
          { id: 'images', label: 'Hình ảnh/Logo', icon: Image },
        ].map(tab => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
              activeTab === tab.id
                ? 'bg-primary-600/20 text-primary-400 border border-primary-500/30'
                : 'text-surface-400 hover:text-surface-200 hover:bg-surface-800/50'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Main Preview Area - Always Visible */}
      <div className="glass-card !p-0 overflow-hidden relative">
        <div
          ref={previewRef}
          className="relative"
          style={{
            aspectRatio: videoAspectRatio,
            backgroundColor: '#000',
            minHeight: '200px'
          }}
        >
          {/* Video placeholder */}
          <div className="absolute inset-0 flex items-center justify-center text-surface-500">
            <span className="text-sm">Video Preview</span>
          </div>

          {/* Main Subtitle Preview */}
          <div
            ref={subtitleRef}
            style={subtitleStyle}
            onMouseDown={(e) => handleMouseDown(e, 'subtitle')}
            className={cn(
              'select-none',
              config.use_custom_position && 'cursor-grab active:cursor-grabbing'
            )}
          >
            {sampleText}
          </div>

          {/* Text Overlays Preview */}
          {config.text_overlays.map((overlay, index) => (
            <div
              key={overlay.id}
              style={{
                position: 'absolute',
                left: `${overlay.x * 100}%`,
                top: `${overlay.y * 100}%`,
                transform: 'translate(-50%, -50%)',
                fontFamily: overlay.font_family,
                fontSize: `${overlay.font_size}px`,
                color: overlay.font_color,
                WebkitTextStroke: `${overlay.outline_width}px ${overlay.outline_color}`,
                textShadow: overlay.shadow_enabled
                  ? `${overlay.shadow_offset_x}px ${overlay.shadow_offset_y}px 0 ${overlay.shadow_color}`
                  : 'none',
                pointerEvents: dragTarget === 'text' && dragIndex === index ? 'all' : 'none',
                cursor: 'grab',
                whiteSpace: 'nowrap',
                userSelect: 'none',
                zIndex: 10,
              }}
              onMouseDown={(e) => handleMouseDown(e, 'text', index)}
              className={dragTarget === 'text' && dragIndex === index ? 'cursor-grabbing' : ''}
            >
              {editingTextIndex === index ? (
                <input
                  type="text"
                  value={editingTextValue}
                  onChange={(e) => setEditingTextValue(e.target.value)}
                  onBlur={saveEditingText}
                  onKeyDown={(e) => e.key === 'Enter' && saveEditingText()}
                  autoFocus
                  className="bg-primary-600/90 text-white px-2 py-1 rounded text-sm outline-none"
                />
              ) : (
                overlay.text
              )}
            </div>
          ))}

          {/* Image Overlays Preview */}
          {config.image_overlays.map((overlay, index) => (
            <div
              key={overlay.id}
              style={{
                position: 'absolute',
                left: `${overlay.x * 100}%`,
                top: `${overlay.y * 100}%`,
                transform: `translate(-50%, -50%) scale(${overlay.scale}) rotate(${overlay.rotation}deg)`,
                opacity: overlay.opacity,
                pointerEvents: dragTarget === 'image' && dragIndex === index ? 'all' : 'none',
                cursor: 'grab',
                zIndex: 20,
              }}
              onMouseDown={(e) => handleMouseDown(e, 'image', index)}
              className={dragTarget === 'image' && dragIndex === index ? 'cursor-grabbing' : ''}
            >
              {overlay.image_data && (
                <img
                  src={overlay.image_data}
                  alt="Overlay"
                  style={{ maxWidth: '200px', maxHeight: '200px', borderRadius: '8px' }}
                  draggable={false}
                />
              )}
            </div>
          ))}

          {/* Position indicator */}
          {config.use_custom_position && config.custom_x !== null && config.custom_y !== null && (
            <div className="absolute bottom-2 left-2 bg-primary-600/90 text-white text-xs px-2 py-1 rounded">
              Phụ đề: {Math.round(config.custom_x * 100)}%, {Math.round(config.custom_y * 100)}%
            </div>
          )}
        </div>

        {/* Quick position buttons - only on main tab */}
        {activeTab === 'main' && (
          <div className="p-4 border-t border-surface-700/50 flex flex-wrap gap-2 justify-center">
            {ALIGNMENT_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => updateConfig({ alignment: opt.value, use_custom_position: false })}
                className={cn(
                  'btn-ghost !px-3 !py-1.5 text-xs flex items-center gap-1',
                  config.alignment === opt.value && !config.use_custom_position
                    ? 'bg-primary-600/20 text-primary-400 border border-primary-500/30'
                    : 'text-surface-400 hover:text-surface-200'
                )}
              >
                <opt.icon className="w-3.5 h-3.5" />
                {opt.label}
              </button>
            ))}
            <button
              onClick={() => updateConfig({ use_custom_position: true })}
              className={cn(
                'btn-ghost !px-3 !py-1.5 text-xs flex items-center gap-1',
                config.use_custom_position
                  ? 'bg-primary-600/20 text-primary-400 border border-primary-500/30'
                  : 'text-surface-400 hover:text-surface-200'
              )}
            >
              <MousePointer2 className="w-3.5 h-3.5" />
              Kéo thả
            </button>
          </div>
        )}
      </div>

      {/* Tab Content */}
      <div className="space-y-4">
        {/* Main Tab - Font & Text Style */}
        {activeTab === 'main' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Font & Text */}
            <div className="glass-card !p-4 space-y-4">
              <h4 className="font-semibold text-surface-100 flex items-center gap-2">
                <Type className="w-5 h-5 text-primary-400" />
                Font & Văn bản
              </h4>

              <div className="space-y-3">
                <label className="flex items-center justify-between text-sm">
                  <span className="text-surface-400">Font</span>
                  <select
                    value={config.font_family}
                    onChange={(e) => updateConfig({ font_family: e.target.value })}
                    className="glass-input !py-1.5 !px-2 text-sm appearance-none cursor-pointer w-40"
                  >
                    {[
                      'Arial', 'Helvetica', 'Roboto', 'Open Sans', 'Noto Sans',
                      'DejaVu Sans', 'Tahoma', 'Verdana', 'Segoe UI',
                      'Montserrat', 'Cinzel', 'Orbitron', 'Courier New',
                      'Impact', 'Georgia', 'Times New Roman'
                    ].map(f => (
                      <option key={f} value={f} style={{ fontFamily: f }}>{f}</option>
                    ))}
                  </select>
                </label>

                <label className="flex items-center justify-between text-sm">
                  <span className="text-surface-400">Cỡ chữ: {config.font_size}px</span>
                  <input
                    type="range"
                    min="12"
                    max="72"
                    step="1"
                    value={config.font_size}
                    onChange={(e) => updateConfig({ font_size: parseInt(e.target.value) })}
                    className="w-32 accent-primary-500"
                  />
                </label>

                <label className="flex items-center justify-between text-sm">
                  <span className="text-surface-400">Màu chữ</span>
                  <input
                    type="color"
                    value={config.font_color}
                    onChange={(e) => updateConfig({ font_color: e.target.value })}
                    className="w-8 h-8 cursor-pointer border-none bg-transparent"
                  />
                </label>
              </div>
            </div>

            {/* Outline & Shadow */}
            <div className="glass-card !p-4 space-y-4">
              <h4 className="font-semibold text-surface-100 flex items-center gap-2">
                <Droplet className="w-5 h-5 text-primary-400" />
                Viền & Bóng
              </h4>

              <div className="space-y-3">
                <label className="flex items-center justify-between text-sm">
                  <span className="text-surface-400">Màu viền</span>
                  <input
                    type="color"
                    value={config.outline_color}
                    onChange={(e) => updateConfig({ outline_color: e.target.value })}
                    className="w-8 h-8 cursor-pointer border-none bg-transparent"
                  />
                </label>

                <label className="flex items-center justify-between text-sm">
                  <span className="text-surface-400">Độ dày viền: {config.outline_width}px</span>
                  <input
                    type="range"
                    min="0"
                    max="8"
                    step="1"
                    value={config.outline_width}
                    onChange={(e) => updateConfig({ outline_width: parseInt(e.target.value) })}
                    className="w-32 accent-primary-500"
                  />
                </label>

                <label className="flex items-center justify-between text-sm">
                  <span className="text-surface-400">Bóng chữ</span>
                  <input
                    type="checkbox"
                    checked={config.shadow_enabled}
                    onChange={(e) => updateConfig({ shadow_enabled: e.target.checked })}
                    className="w-4 h-4 accent-primary-500"
                  />
                </label>

                {config.shadow_enabled && (
                  <>
                    <label className="flex items-center justify-between text-sm">
                      <span className="text-surface-400">Màu bóng</span>
                      <input
                        type="color"
                        value={config.shadow_color}
                        onChange={(e) => updateConfig({ shadow_color: e.target.value })}
                        className="w-8 h-8 cursor-pointer border-none bg-transparent"
                      />
                    </label>
                    <label className="flex items-center justify-between text-sm">
                      <span className="text-surface-400">Độ lệch bóng X: {config.shadow_offset_x}px</span>
                      <input
                        type="range"
                        min="0"
                        max="10"
                        step="1"
                        value={config.shadow_offset_x}
                        onChange={(e) => updateConfig({ shadow_offset_x: parseInt(e.target.value) })}
                        className="w-32 accent-primary-500"
                      />
                    </label>
                    <label className="flex items-center justify-between text-sm">
                      <span className="text-surface-400">Độ lệch bóng Y: {config.shadow_offset_y}px</span>
                      <input
                        type="range"
                        min="0"
                        max="10"
                        step="1"
                        value={config.shadow_offset_y}
                        onChange={(e) => updateConfig({ shadow_offset_y: parseInt(e.target.value) })}
                        className="w-32 accent-primary-500"
                      />
                    </label>
                  </>
                )}
              </div>
            </div>

            {/* Position & Margins */}
            <div className="glass-card !p-4 space-y-4 lg:col-span-2">
              <h4 className="font-semibold text-surface-100 flex items-center gap-2">
                <Square className="w-5 h-5 text-primary-400" />
                Vị trí & Khoảng cách & Căn lề
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-surface-400">Margin dọc (MarginV): {config.margin_v}px</span>
                  <input
                    type="range"
                    min="0"
                    max="200"
                    step="5"
                    value={config.margin_v}
                    onChange={(e) => updateConfig({ margin_v: parseInt(e.target.value) })}
                    className="accent-primary-500"
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-surface-400">Margin trái: {config.margin_l}px</span>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={config.margin_l}
                    onChange={(e) => updateConfig({ margin_l: parseInt(e.target.value) })}
                    className="accent-primary-500"
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-surface-400">Margin phải: {config.margin_r}px</span>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={config.margin_r}
                    onChange={(e) => updateConfig({ margin_r: parseInt(e.target.value) })}
                    className="accent-primary-500"
                  />
                </label>
              </div>
            </div>

            {/* Presets & Quick Actions */}
            <div className="glass-card !p-4 space-y-4 lg:col-span-2">
              <h4 className="font-semibold text-surface-100 flex items-center gap-2">
                <Download className="w-5 h-5 text-primary-400" />
                Cài đặt nhanh
              </h4>

              <div className="flex flex-wrap gap-3">
                <button onClick={onReset} className="btn-secondary text-sm">
                  <RotateCcw className="w-4 h-4 mr-1" />
                  Khôi phục mặc định
                </button>
                <button
                  onClick={() => updateConfig({
                    font_size: 32,
                    outline_width: 3,
                    margin_v: 60
                  })}
                  className="btn-ghost text-sm"
                >
                  Phụ đề lớn (TV)
                </button>
                <button
                  onClick={() => updateConfig({
                    font_size: 20,
                    outline_width: 1,
                    margin_v: 20
                  })}
                  className="btn-ghost text-sm"
                >
                  Phụ đề nhỏ (Mobile)
                </button>
                <button
                  onClick={() => updateConfig({
                    font_color: '#FFFF00',
                    outline_color: '#FF0000',
                    outline_width: 3,
                  })}
                  className="btn-ghost text-sm"
                >
                  Style Karaoke
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Presets Tab */}
        {activeTab === 'presets' && (
          <div className="glass-card !p-4 space-y-4">
            <h4 className="font-semibold text-surface-100 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary-400" />
              Mẫu chữ CapCut Style
            </h4>
            <p className="text-sm text-surface-500">Chọn mẫu để áp dụng ngay, sau đó có thể tùy chỉnh thêm</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {FONT_PRESETS.map(preset => (
                <button
                  key={preset.id}
                  onClick={() => applyFontPreset(preset)}
                  className={cn(
                    'p-3 rounded-xl border text-left transition-all text-sm',
                    config.font_preset_id === preset.id
                      ? 'border-primary-500 bg-primary-500/10'
                      : 'border-surface-700/50 hover:border-surface-600'
                  )}
                >
                  <div className="font-medium text-surface-100">{preset.name}</div>
                  <div className="text-xs text-surface-500 mt-1">{preset.description}</div>
                  <div className="mt-2 text-xs text-surface-400 flex items-center gap-1">
                    {preset.animation && (
                      <span className="px-1.5 py-0.5 rounded bg-primary-500/20 text-primary-400">
                        {preset.animation}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Overlays Tab */}
        {activeTab === 'overlays' && (
          <div className="glass-card !p-4 space-y-4">
            <h4 className="font-semibold text-surface-100 flex items-center gap-2">
              <Layers className="w-5 h-5 text-primary-400" />
              Chèn thêm văn bản & hình ảnh
            </h4>
            <p className="text-sm text-surface-500">
              Thêm các lớp văn bản hoặc hình ảnh/logo lên video. Có thể kéo thả để định vị.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Text Overlays */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h5 className="font-medium text-surface-200 flex items-center gap-2">
                    <Type className="w-4 h-4 text-primary-400" />
                    Văn bản chèn thêm
                  </h5>
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newTextOverlay}
                    onChange={(e) => setNewTextOverlay(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addTextOverlay()}
                    placeholder="Nhập văn bản muốn chèn..."
                    className="glass-input flex-1"
                  />
                  <button onClick={addTextOverlay} className="btn-primary">
                    <Plus className="w-4 h-4" />
                    Thêm
                  </button>
                </div>

                {config.text_overlays.length === 0 && (
                  <p className="text-sm text-surface-500 text-center py-4">Chưa có văn bản chèn thêm</p>
                )}

                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {config.text_overlays.map((overlay, index) => (
                    <div
                      key={overlay.id}
                      className="glass-input !bg-surface-800/50 p-3 flex flex-col gap-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-surface-200 truncate">{overlay.text}</span>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => startEditingText(index)}
                            className="btn-ghost !p-1.5 text-surface-400 hover:text-surface-200"
                            title="Sửa"
                          >
                            <Type className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => removeTextOverlay(index)}
                            className="btn-ghost !p-1.5 text-red-400 hover:text-red-300"
                            title="Xóa"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">X:</span>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            value={overlay.x}
                            onChange={(e) => updateTextOverlay(index, { x: parseFloat(e.target.value) })}
                            className="flex-1 accent-primary-500"
                          />
                          <span className="text-surface-300 w-10 text-right">{Math.round(overlay.x * 100)}%</span>
                        </label>
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">Y:</span>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            value={overlay.y}
                            onChange={(e) => updateTextOverlay(index, { y: parseFloat(e.target.value) })}
                            className="flex-1 accent-primary-500"
                          />
                          <span className="text-surface-300 w-10 text-right">{Math.round(overlay.y * 100)}%</span>
                        </label>
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">Cỡ:</span>
                          <input
                            type="number"
                            min="10"
                            max="72"
                            value={overlay.font_size}
                            onChange={(e) => updateTextOverlay(index, { font_size: parseInt(e.target.value) })}
                            className="glass-input !w-16 !py-1 text-center"
                          />
                        </label>
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">Màu:</span>
                          <input
                            type="color"
                            value={overlay.font_color}
                            onChange={(e) => updateTextOverlay(index, { font_color: e.target.value })}
                            className="w-6 h-6 cursor-pointer border-none bg-transparent"
                          />
                        </label>
                      </div>

                      {editingTextIndex === index && (
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={editingTextValue}
                            onChange={(e) => setEditingTextValue(e.target.value)}
                            onBlur={saveEditingText}
                            onKeyDown={(e) => e.key === 'Enter' && saveEditingText()}
                            autoFocus
                            className="glass-input flex-1"
                          />
                          <button onClick={saveEditingText} className="btn-primary !px-3">
                            Lưu
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Image Overlays */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h5 className="font-medium text-surface-200 flex items-center gap-2">
                    <Image className="w-4 h-4 text-primary-400" />
                    Hình ảnh / Logo
                  </h5>
                </div>

                <input
                  type="file"
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="glass-input !py-2 text-sm"
                />

                {config.image_overlays.length === 0 && (
                  <p className="text-sm text-surface-500 text-center py-4">Chưa có hình ảnh/logo</p>
                )}

                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {config.image_overlays.map((overlay, index) => (
                    <div
                      key={overlay.id}
                      className="glass-input !bg-surface-800/50 p-3 flex flex-col gap-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {overlay.image_data && (
                            <img
                              src={overlay.image_data}
                              alt="Overlay"
                              className="w-12 h-12 object-cover rounded"
                            />
                          )}
                          <span className="text-sm font-medium text-surface-200">Logo #{index + 1}</span>
                        </div>
                        <button
                          onClick={() => removeImageOverlay(index)}
                          className="btn-ghost !p-1.5 text-red-400 hover:text-red-300"
                          title="Xóa"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">X:</span>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            value={overlay.x}
                            onChange={(e) => updateImageOverlay(index, { x: parseFloat(e.target.value) })}
                            className="flex-1 accent-primary-500"
                          />
                          <span className="text-surface-300 w-10 text-right">{Math.round(overlay.x * 100)}%</span>
                        </label>
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">Y:</span>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            value={overlay.y}
                            onChange={(e) => updateImageOverlay(index, { y: parseFloat(e.target.value) })}
                            className="flex-1 accent-primary-500"
                          />
                          <span className="text-surface-300 w-10 text-right">{Math.round(overlay.y * 100)}%</span>
                        </label>
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">Scale:</span>
                          <input
                            type="range"
                            min="0.05"
                            max="0.5"
                            step="0.01"
                            value={overlay.scale}
                            onChange={(e) => updateImageOverlay(index, { scale: parseFloat(e.target.value) })}
                            className="flex-1 accent-primary-500"
                          />
                          <span className="text-surface-300 w-10 text-right">{Math.round(overlay.scale * 100)}%</span>
                        </label>
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">Opacity:</span>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={overlay.opacity}
                            onChange={(e) => updateImageOverlay(index, { opacity: parseFloat(e.target.value) })}
                            className="flex-1 accent-primary-500"
                          />
                          <span className="text-surface-300 w-10 text-right">{Math.round(overlay.opacity * 100)}%</span>
                        </label>
                        <label className="flex items-center gap-1">
                          <span className="text-surface-400">Rotate:</span>
                          <input
                            type="range"
                            min="-180"
                            max="180"
                            step="1"
                            value={overlay.rotation}
                            onChange={(e) => updateImageOverlay(index, { rotation: parseInt(e.target.value) })}
                            className="flex-1 accent-primary-500"
                          />
                          <span className="text-surface-300 w-10 text-right">{overlay.rotation}°</span>
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Text Overlays Tab (dedicated) */}
        {activeTab === 'text' && (
          <div className="glass-card !p-4 space-y-4">
            <h4 className="font-semibold text-surface-100 flex items-center gap-2">
              <Type className="w-5 h-5 text-primary-400" />
              Quản lý văn bản chèn thêm
            </h4>
            <p className="text-sm text-surface-500">Quản lý chi tiết các lớp văn bản. Kéo thả trên preview để định vị.</p>

            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={newTextOverlay}
                onChange={(e) => setNewTextOverlay(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addTextOverlay()}
                placeholder="Nhập văn bản muốn chèn..."
                className="glass-input flex-1"
              />
              <button onClick={addTextOverlay} className="btn-primary">
                <Plus className="w-4 h-4" />
                Thêm
              </button>
            </div>

            {config.text_overlays.map((overlay, index) => (
              <div key={overlay.id} className="glass-input !bg-surface-800/50 p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-medium text-surface-200">#{index + 1}</span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => startEditingText(index)}
                      className="btn-ghost !p-1.5"
                      title="Sửa nội dung"
                    >
                      <Type className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => removeTextOverlay(index)}
                      className="btn-ghost !p-1.5 text-red-400 hover:text-red-300"
                      title="Xóa"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {editingTextIndex === index ? (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={editingTextValue}
                      onChange={(e) => setEditingTextValue(e.target.value)}
                      onBlur={saveEditingText}
                      onKeyDown={(e) => e.key === 'Enter' && saveEditingText()}
                      autoFocus
                      className="glass-input flex-1"
                    />
                    <button onClick={saveEditingText} className="btn-primary !px-4">Lưu</button>
                  </div>
                ) : (
                  <p className="text-surface-200">{overlay.text}</p>
                )}

                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-3">
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-surface-400">Vị trí X: {Math.round(overlay.x * 100)}%</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={overlay.x}
                      onChange={(e) => updateTextOverlay(index, { x: parseFloat(e.target.value) })}
                      className="accent-primary-500"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-surface-400">Vị trí Y: {Math.round(overlay.y * 100)}%</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={overlay.y}
                      onChange={(e) => updateTextOverlay(index, { y: parseFloat(e.target.value) })}
                      className="accent-primary-500"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-surface-400">Cỡ chữ: {overlay.font_size}px</span>
                    <input
                      type="range"
                      min="10"
                      max="72"
                      step="1"
                      value={overlay.font_size}
                      onChange={(e) => updateTextOverlay(index, { font_size: parseInt(e.target.value) })}
                      className="accent-primary-500"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-surface-400">Màu chữ</span>
                    <input
                      type="color"
                      value={overlay.font_color}
                      onChange={(e) => updateTextOverlay(index, { font_color: e.target.value })}
                      className="w-8 h-8 cursor-pointer border-none bg-transparent"
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Image Overlays Tab (dedicated) */}
        {activeTab === 'images' && (
          <div className="glass-card !p-4 space-y-4">
            <h4 className="font-semibold text-surface-100 flex items-center gap-2">
              <Image className="w-5 h-5 text-primary-400" />
              Quản lý hình ảnh / Logo
            </h4>
            <p className="text-sm text-surface-500">Upload logo, watermark hoặc hình ảnh chèn thêm. Kéo thả trên preview để định vị.</p>

            <input
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="glass-input !py-2"
              multiple
            />

            {config.image_overlays.map((overlay, index) => (
              <div key={overlay.id} className="glass-input !bg-surface-800/50 p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {overlay.image_data && (
                      <img src={overlay.image_data} alt="Overlay" className="w-16 h-16 object-cover rounded" />
                    )}
                    <div>
                      <p className="font-medium text-surface-200">Logo #{index + 1}</p>
                      <p className="text-xs text-surface-500">Kéo thả trên preview để di chuyển</p>
                    </div>
                  </div>
                  <button
                    onClick={() => removeImageOverlay(index)}
                    className="btn-ghost !p-1.5 text-red-400 hover:text-red-300"
                    title="Xóa"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-surface-400">Vị trí X: {Math.round(overlay.x * 100)}%</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={overlay.x}
                      onChange={(e) => updateImageOverlay(index, { x: parseFloat(e.target.value) })}
                      className="accent-primary-500"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-surface-400">Vị trí Y: {Math.round(overlay.y * 100)}%</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={overlay.y}
                      onChange={(e) => updateImageOverlay(index, { y: parseFloat(e.target.value) })}
                      className="accent-primary-500"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-surface-400">Kích thước: {Math.round(overlay.scale * 100)}%</span>
                    <input
                      type="range"
                      min="0.05"
                      max="0.5"
                      step="0.01"
                      value={overlay.scale}
                      onChange={(e) => updateImageOverlay(index, { scale: parseFloat(e.target.value) })}
                      className="accent-primary-500"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-surface-400">Độ trong: {Math.round(overlay.opacity * 100)}%</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={overlay.opacity}
                      onChange={(e) => updateImageOverlay(index, { opacity: parseFloat(e.target.value) })}
                      className="accent-primary-500"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm md:col-span-2">
                    <span className="text-surface-400">Xoay: {overlay.rotation}°</span>
                    <input
                      type="range"
                      min="-180"
                      max="180"
                      step="1"
                      value={overlay.rotation}
                      onChange={(e) => updateImageOverlay(index, { rotation: parseInt(e.target.value) })}
                      className="accent-primary-500"
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Aspect Ratio Selection - Always visible at bottom */}
        <div className="glass-card !p-4">
          <h4 className="font-semibold text-surface-100 flex items-center gap-2 mb-3">
            <Square className="w-5 h-5 text-primary-400" />
            Tỷ lệ khung hình Video
          </h4>
          <div className="flex flex-wrap gap-2">
            {ASPECT_RATIOS.map(ratio => (
              <button
                key={ratio.id}
                onClick={() => updateConfig({ aspect_ratio: ratio.id })}
                className={cn(
                  'px-4 py-2 rounded-lg border text-sm font-medium transition-all',
                  config.aspect_ratio === ratio.id
                    ? 'bg-primary-600/20 text-primary-400 border-primary-500/30'
                    : 'border-surface-700/50 text-surface-400 hover:border-surface-600 hover:text-surface-200'
                )}
              >
                {ratio.name}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}