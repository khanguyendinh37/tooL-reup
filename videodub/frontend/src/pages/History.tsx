import { useState, useEffect } from 'react'
import { Search, Grid3X3, List, Trash2, Download, Play, Clock, MoreVertical, Loader2, AlertCircle, X } from 'lucide-react'
import { getHistory, deleteHistoryItem } from '@/lib/api'
import { formatDate } from '@/lib/utils'

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
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [openMenu, setOpenMenu] = useState<string | null>(null)

  // Video preview state
  const [previewVideo, setPreviewVideo] = useState<{ id: string; url: string; title: string } | null>(null)

  useEffect(() => {
    loadHistory()
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
    } catch (err) {
      alert('Không thể xóa video')
    }
  }

  const handleDownload = (item: HistoryItem) => {
    if (item.status === 'completed') {
      window.open(`/api/dubbing/${item.id}/download`, '_blank')
    }
  }

  const handlePreview = (item: HistoryItem) => {
    if (item.status === 'completed') {
      setPreviewVideo({
        id: item.id,
        url: `/api/dubbing/${item.id}/download`,
        title: item.title || 'Video đã lồng tiếng'
      })
    }
  }

  const closePreview = () => {
    setPreviewVideo(null)
  }

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
      // Convert server path to accessible URL
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
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-surface-100">Lịch sử lồng tiếng</h2>
        <div className="flex items-center gap-2">
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
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
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
          className="glass-input appearance-none cursor-pointer"
        >
          <option value="all">Tất cả</option>
          <option value="completed">Hoàn thành</option>
          <option value="error">Lỗi</option>
        </select>
      </div>

      {/* Grid View */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredData.map((item) => (
            <div key={item.id} className="glass-card hover:scale-[1.02] transition-all duration-300">
              {/* Thumbnail */}
              <div className="aspect-video bg-surface-800 rounded-xl mb-4 flex items-center justify-center relative overflow-hidden group">
                {renderThumbnail(item)}
                <Play className="w-12 h-12 text-surface-500 relative z-10 group-hover:text-primary-400 transition-colors" />
                {item.file_size && (
                  <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-1 rounded text-xs text-white">
                    {item.file_size}
                  </div>
                )}
              </div>

              <h3 className="font-medium text-surface-100 mb-2 line-clamp-2">
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
                      onClick={() => handleDownload(item)}
                      className="btn-ghost flex-1 text-sm"
                    >
                      <Download className="w-4 h-4 mr-1" />
                      Tải
                    </button>
                    <button
                      onClick={() => handlePreview(item)}
                      className="btn-primary flex-1 text-sm"
                    >
                      <Play className="w-4 h-4 mr-1" />
                      Xem
                    </button>
                  </>
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
            <div key={item.id} className="glass-card !p-4 flex items-center gap-4 hover:bg-surface-800/30 transition-colors">
              <div className="w-24 h-14 bg-surface-800 rounded-lg flex items-center justify-center flex-shrink-0 relative overflow-hidden">
                {renderThumbnail(item)}
                <Play className="w-6 h-6 text-surface-500 relative z-10" />
              </div>

              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-surface-100 truncate">
                  {item.title || 'Video không có tiêu đề'}
                </h3>
                <div className="flex items-center gap-3 text-xs text-surface-500 mt-1">
                  <span>{item.source_lang?.toUpperCase()} → {item.target_lang?.toUpperCase()}</span>
                  {item.file_size && <span>{item.file_size}</span>}
                  <span>{formatDate(item.created_at)}</span>
                </div>
              </div>

              {getStatusBadge(item.status)}

              <div className="flex items-center gap-2">
                {item.status === 'completed' && (
                  <>
                    <button
                      onClick={() => handleDownload(item)}
                      className="btn-ghost !px-2"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handlePreview(item)}
                      className="btn-ghost !px-2"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                  </>
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

      {/* Video Preview Modal */}
      {previewVideo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={closePreview}>
          <div className="relative w-full max-w-4xl bg-surface-900 rounded-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-surface-700">
              <h3 className="font-semibold text-surface-100 truncate pr-4">{previewVideo.title}</h3>
              <div className="flex items-center gap-2">
                <a
                  href={`/api/dubbing/${previewVideo.id}/download`}
                  target="_blank"
                  className="btn-primary inline-flex items-center gap-2 text-sm"
                >
                  <Download className="w-4 h-4" />
                  Tải
                </a>
                <button
                  onClick={closePreview}
                  className="btn-ghost p-2"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Video Player */}
            <div className="relative" style={{ paddingTop: '56.25%' }}>
              <video
                src={previewVideo.url}
                controls
                className="absolute top-0 left-0 w-full h-full"
                style={{ objectFit: 'contain', backgroundColor: '#000' }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}