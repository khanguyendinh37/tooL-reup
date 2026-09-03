import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Grid3X3, List, Trash2, Download, Play, Clock, MoreVertical, Loader2, AlertCircle, Pause, RotateCcw, CheckSquare } from 'lucide-react'
import { downloadFile, getHistory, deleteHistoryItem, deleteHistoryItems, retryDubbing } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { workflowFromJob } from '@/lib/workflow'
import { useAppStore } from '@/stores/appStore'

interface HistoryItem {
  id: string
  title: string | null
  url: string
  source_lang: string
  target_lang: string
  status: string
  progress: number
  created_at: string
  file_size: string | null
  result_path: string | null
  thumbnail_path: string | null
}

export default function History() {
  const navigate = useNavigate()
  const setActiveWorkflow = useAppStore((state) => state.setActiveWorkflow)
  const [items, setItems] = useState<HistoryItem[]>([])
  const [retryingId, setRetryingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [openMenu, setOpenMenu] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)

  // Inline video player state
  const [playingId, setPlayingId] = useState<string | null>(null)
  const videoRefs = useRef<Map<string, HTMLVideoElement>>(new Map())

  useEffect(() => {
    loadHistory()
  }, [])

  // Stop video when component unmounts
  useEffect(() => {
    return () => {
      videoRefs.current.forEach((video) => {
        video.pause()
        video.src = ''
      })
    }
  }, [])

  const loadHistory = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getHistory()
      setItems(data)
    } catch (err) {
      setError('Không thể tải lịch sử. Vui lòng thử lại.')
      console.error('Failed to load history:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Bạn có chắc muốn xóa video này?')) return
    try {
      await deleteHistoryItem(id)
      setItems(prev => prev.filter(item => item.id !== id))
      setOpenMenu(null)
      if (playingId === id) setPlayingId(null)
    } catch (err) {
      alert('Không thể xóa video')
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    const visibleIds = filteredData.map(item => item.id)
    if (visibleIds.every(id => selectedIds.has(id))) {
      // Deselect all visible
      setSelectedIds(prev => {
        const next = new Set(prev)
        visibleIds.forEach(id => next.delete(id))
        return next
      })
    } else {
      // Select all visible
      setSelectedIds(prev => {
        const next = new Set(prev)
        visibleIds.forEach(id => next.add(id))
        return next
      })
    }
  }

  const handleBulkDelete = async () => {
    const count = selectedIds.size
    if (count === 0) return
    if (!confirm(`Bạn có chắc muốn xóa ${count} video đã chọn? Hành động này không thể hoàn tác.`)) return

    setBulkDeleting(true)
    try {
      const ids = Array.from(selectedIds)
      const result = await deleteHistoryItems(ids)
      // Remove deleted items from local state
      setItems(prev => prev.filter(item => !selectedIds.has(item.id)))
      // Stop playing if a deleted video was playing
      if (playingId && selectedIds.has(playingId)) setPlayingId(null)
      setSelectedIds(new Set())
      const deletedCount = result?.deleted_count ?? count
      alert(`Đã xóa ${deletedCount} video khỏi lịch sử.`)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể xóa các video đã chọn')
    } finally {
      setBulkDeleting(false)
    }
  }

  const exitSelectionMode = () => setSelectedIds(new Set())

  const handleDownload = async (item: HistoryItem) => {
    if (item.status !== 'completed') return
    try {
      await downloadFile(`/api/dubbing/${item.id}/download`, `${item.id}_dubbed.mp4`)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể lưu video')
    }
  }

  const handleRetry = async (item: HistoryItem) => {
    if (item.status !== 'error' || retryingId) return
    setRetryingId(item.id)
    try {
      const job = await retryDubbing(item.id)
      setItems((current) => current.map((entry) => entry.id === item.id
        ? { ...entry, status: job.status, progress: job.progress, error: null }
        : entry))
      // Retry starts a fresh run: reset startedAt so monitoring is not
      // measured from the original job creation time.
      setActiveWorkflow({ ...workflowFromJob(job), startedAt: new Date().toISOString() })
      navigate(`/dubbing/${item.id}`)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể chạy lại quy trình')
    } finally {
      setRetryingId(null)
    }
  }

  const handlePlayToggle = (item: HistoryItem) => {
    if (item.status !== 'completed') return

    if (playingId === item.id) {
      // Pause current video
      const video = videoRefs.current.get(item.id)
      if (video) video.pause()
      setPlayingId(null)
    } else {
      // Stop any currently playing video
      if (playingId) {
        const prevVideo = videoRefs.current.get(playingId)
        if (prevVideo) prevVideo.pause()
      }
      // Start playing new video
      setPlayingId(item.id)
      // Video will auto-play via useEffect below
    }
  }

  // Auto-play when playingId changes
  useEffect(() => {
    if (playingId) {
      const video = videoRefs.current.get(playingId)
      if (video) {
        video.src = `/api/dubbing/${playingId}/download`
        video.load()
        video.play().catch(() => {})
      }
    }
  }, [playingId])

  const filteredData = items.filter(item => {
    const title = item.title || item.url
    const matchesSearch = title.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesFilter = filterStatus === 'all' || item.status === filterStatus
    return matchesSearch && matchesFilter
  })

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <span className="px-2 py-1 text-xs rounded-full bg-emerald-500/20 text-emerald-400">Hoàn thành</span>
      case 'pending':
      case 'downloading':
      case 'preview_ready':
      case 'processing':
      case 'transcribing':
      case 'translating':
      case 'tts':
      case 'removing_vocals':
      case 'merging':
        return <span className="px-2 py-1 text-xs rounded-full bg-primary-500/20 text-primary-400">Đang xử lý</span>
      case 'error':
        return <span className="px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-400">Lỗi</span>
      default:
        return <span className="px-2 py-1 text-xs rounded-full bg-surface-500/20 text-surface-400">{status}</span>
    }
  }

  // Render thumbnail or placeholder
  const renderThumbnail = (item: HistoryItem) => {
    if (item.thumbnail_path) {
      const thumbUrl = `/api/dubbing/${item.id}/thumbnail`
      return (
        <img
          src={thumbUrl}
          alt={item.title || 'Video thumbnail'}
          className="absolute inset-0 w-full h-full object-cover opacity-80"
          onError={(e) => {
            e.currentTarget.style.display = 'none'
          }}
        />
      )
    }
    return (
      <div className="absolute inset-0 bg-gradient-to-br from-primary-500/20 to-accent-cyan/20" />
    )
  }

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6 animate-fade-in">
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
          <span className="ml-3 text-surface-400">Đang tải lịch sử...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto space-y-6 animate-fade-in">
        <div className="glass-card text-center py-12">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-surface-400 mb-4">{error}</p>
          <button onClick={loadHistory} className="btn-primary">
            Thử lại
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xl sm:text-2xl font-bold text-surface-100 truncate">Lịch sử lồng tiếng</h2>
        <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
          <button
            onClick={toggleSelectAll}
            className="p-2 rounded-lg transition-colors text-surface-500 hover:bg-surface-800"
            title="Chọn tất cả"
          >
            <CheckSquare className="w-5 h-5" />
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-primary-600/20 text-primary-400' : 'text-surface-500 hover:bg-surface-800'}`}
          >
            <Grid3X3 className="w-5 h-5" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-primary-600/20 text-primary-400' : 'text-surface-500 hover:bg-surface-800'}`}
          >
            <List className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-stretch gap-3">
        <div className="relative flex-1 sm:flex-shrink-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm kiếm video..."
            className="glass-input !pl-10 w-full"
          />
        </div>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="glass-input appearance-none cursor-pointer sm:w-40"
        >
          <option value="all">Tất cả</option>
          <option value="completed">Hoàn thành</option>
          <option value="error">Lỗi</option>
        </select>
      </div>

      {/* Bulk Actions Bar */}
      {selectedIds.size > 0 && (
        <div className="glass-card !p-3 !pb-2 flex items-center justify-between mb-4 animate-fade-in">
          <div className="flex items-center gap-2 text-sm text-surface-300">
            <span>Đã chọn {selectedIds.size} video</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={exitSelectionMode}
              className="btn-ghost text-sm"
              disabled={bulkDeleting}
            >
              Bỏ chọn
            </button>
            <button
              onClick={handleBulkDelete}
              disabled={bulkDeleting}
              className="btn-ghost text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/30 disabled:cursor-wait disabled:opacity-60"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              {bulkDeleting ? 'Đang xóa...' : 'Xóa đã chọn'}
            </button>
          </div>
        </div>
      )}

      {/* Grid View */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {filteredData.map((item) => (
            <div key={item.id} className="glass-card hover:scale-[1.02] transition-all duration-300">
              {/* Thumbnail / Video Player */}
              <div className="aspect-video bg-surface-800 rounded-xl mb-4 flex items-center justify-center relative overflow-hidden group">
                <div className="flex items-center justify-center gap-1.5 absolute top-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    className="w-3 h-3 rounded border border-surface-400 cursor-pointer bg-surface-900/80"
                  />
                </div>
                {playingId === item.id ? (
                  /* Inline video player */
                  <div className="absolute inset-0 bg-black">
                    <video
                      ref={(el) => {
                        if (el) videoRefs.current.set(item.id, el)
                      }}
                      controls
                      autoPlay
                      className="w-full h-full"
                      style={{ objectFit: 'contain' }}
                      onEnded={() => setPlayingId(null)}
                    />
                    <button
                      onClick={() => handlePlayToggle(item)}
                      className="absolute top-2 right-2 z-10 bg-black/60 hover:bg-black/80 rounded-full p-1.5 transition-colors"
                      title="Dừng"
                    >
                      <Pause className="w-4 h-4 text-white" />
                    </button>
                  </div>
                ) : (
                  <>
                    {renderThumbnail(item)}
                    <button
                      onClick={() => handlePlayToggle(item)}
                      className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 hover:opacity-50 transition-opacity"
                    >
                      <div className="w-14 h-14 rounded-full bg-primary-600/80 flex items-center justify-center hover:bg-primary-500 transition-colors">
                        <Play className="w-7 h-7 text-white ml-0.5" />
                      </div>
                    </button>
                    {item.file_size && (
                      <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-1 rounded text-xs text-white">
                        {item.file_size}
                      </div>
                    )}
                  </>
                )}
              </div>

              <h3 className="font-medium text-surface-100 mb-2 line-clamp-2 text-sm sm:text-base">
                {item.title || 'Video không có tiêu đề'}
              </h3>

              <div className="flex items-center gap-2 mb-3">
                {getStatusBadge(item.status)}
              </div>

              <div className="flex items-center justify-between text-xs text-surface-500 mb-4">
                <span>{item.source_lang?.toUpperCase()} → {item.target_lang?.toUpperCase()}</span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatDate(item.created_at)}
                </span>
              </div>

              <div className="flex items-center gap-2 relative">
                {item.status === 'completed' && (
                  <>
                    <button
                      onClick={() => void handleDownload(item)}
                      className="btn-ghost flex-1 text-sm"
                    >
                      <Download className="w-4 h-4 mr-1" />
                      Tải
                    </button>
                    <button
                      onClick={() => handlePlayToggle(item)}
                      className={`flex-1 text-sm inline-flex items-center justify-center gap-1 px-3 py-2 rounded-lg font-medium transition-all ${
                        playingId === item.id
                          ? 'bg-red-600/20 text-red-400 border border-red-500/30 hover:bg-red-600/30'
                          : 'bg-primary-600/20 text-primary-400 border border-primary-500/30 hover:bg-primary-600/30'
                      }`}
                    >
                      {playingId === item.id ? (
                        <>
                          <Pause className="w-4 h-4 mr-1" />
                          Dừng
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-1" />
                          Xem
                        </>
                      )}
                    </button>
                  </>
                )}
                {item.status === 'error' && (
                  <button
                    onClick={() => void handleRetry(item)}
                    disabled={retryingId === item.id}
                    className="btn-primary flex-1 inline-flex items-center justify-center gap-2 text-sm disabled:cursor-wait disabled:opacity-60"
                  >
                    {retryingId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                    {retryingId === item.id ? 'Đang chạy lại...' : 'Chạy lại'}
                  </button>
                )}
                <div className="relative">
                  <button
                    onClick={() => setOpenMenu(openMenu === item.id ? null : item.id)}
                    className="btn-ghost !px-2"
                  >
                    <MoreVertical className="w-4 h-4" />
                  </button>
                  {openMenu === item.id && (
                    <div className="absolute right-0 bottom-full mb-2 w-36 glass rounded-xl py-1 z-10">
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-surface-800 flex items-center gap-2"
                      >
                        <Trash2 className="w-4 h-4" />
                        Xóa
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* List View */
        <div className="space-y-2">
          {filteredData.map((item) => (
            <div key={item.id} className="glass-card !p-3 sm:!p-4 flex items-center gap-3 sm:gap-4 hover:bg-surface-800/30 transition-colors">
              <input
                type="checkbox"
                checked={selectedIds.has(item.id)}
                onChange={() => toggleSelect(item.id)}
                className="w-4 h-4 rounded border border-surface-500 cursor-pointer flex-shrink-0"
              />
              <div
                className="w-20 h-12 sm:w-24 sm:h-14 bg-surface-800 rounded-lg flex items-center justify-center flex-shrink-0 relative overflow-hidden cursor-pointer"
                onClick={() => handlePlayToggle(item)}
              >
                {playingId === item.id ? (
                  <div className="absolute inset-0 bg-black flex items-center justify-center">
                    <video
                      ref={(el) => {
                        if (el) videoRefs.current.set(item.id, el)
                      }}
                      autoPlay
                      className="w-full h-full object-cover"
                      onEnded={() => setPlayingId(null)}
                    />
                    <Pause className="w-5 h-5 text-white relative z-10" />
                  </div>
                ) : (
                  <>
                    {renderThumbnail(item)}
                    <Play className="w-6 h-6 text-surface-500 relative z-10" />
                  </>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-surface-100 truncate text-sm sm:text-base">
                  {item.title || 'Video không có tiêu đề'}
                </h3>
                <div className="flex items-center gap-2 sm:gap-3 text-xs text-surface-500 mt-1 flex-wrap">
                  <span className="whitespace-nowrap">{item.source_lang?.toUpperCase()} → {item.target_lang?.toUpperCase()}</span>
                  {item.file_size && <span className="whitespace-nowrap">{item.file_size}</span>}
                  <span className="whitespace-nowrap hidden sm:inline">{formatDate(item.created_at)}</span>
                </div>
              </div>

              <div className="hidden sm:block flex-shrink-0">{getStatusBadge(item.status)}</div>

              <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
                {item.status === 'completed' && (
                  <>
                    <button
                      onClick={() => void handleDownload(item)}
                      className="btn-ghost !px-2"
                      title="Tải video"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handlePlayToggle(item)}
                      className={`btn-ghost !px-2 ${playingId === item.id ? 'text-red-400 hover:text-red-300' : 'text-primary-400 hover:text-primary-300'}`}
                      title={playingId === item.id ? 'Dừng' : 'Xem ngay'}
                    >
                      {playingId === item.id ? (
                        <Pause className="w-4 h-4" />
                      ) : (
                        <Play className="w-4 h-4" />
                      )}
                    </button>
                  </>
                )}
                {item.status === 'error' && (
                  <button
                    onClick={() => void handleRetry(item)}
                    disabled={retryingId === item.id}
                    className="btn-ghost !px-2 text-primary-400 hover:text-primary-300 disabled:cursor-wait disabled:opacity-60"
                    title="Chạy lại quy trình"
                    aria-label="Chạy lại quy trình"
                  >
                    {retryingId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                  </button>
                )}
                <button
                  onClick={() => handleDelete(item.id)}
                  className="btn-ghost !px-2 text-red-400 hover:text-red-300"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {filteredData.length === 0 && (
        <div className="text-center py-16">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-surface-800 flex items-center justify-center">
            <Search className="w-8 h-8 text-surface-500" />
          </div>
          <p className="text-surface-400">
            {items.length === 0 ? 'Chưa có video nào được lồng tiếng' : 'Không tìm thấy video nào'}
          </p>
        </div>
      )}
    </div>
  )
}
