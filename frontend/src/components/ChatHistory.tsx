/**
 * Компонент истории чатов (сайдбар)
 * 
 * Отображает список всех диалогов с возможностью:
 * - Переключения между диалогами
 * - Создания нового диалога
 * - Удаления диалога
 */
import { useState, useEffect, useCallback } from 'react'
import { 
  MessageSquare, Plus, Trash2, ChevronLeft, ChevronRight, 
  Clock, Search, X
} from 'lucide-react'
import { ConversationPreview, ConversationsListResponse } from '../types/api'
import { api } from '../services/apiClient'

interface ChatHistoryProps {
  currentConversationId: string | null
  onSelectConversation: (id: string) => void
  onNewConversation: () => void
  onDeleteConversation: (id: string) => void
  isCollapsed?: boolean
  onToggleCollapse?: () => void
}

// Модальное окно подтверждения удаления
interface DeleteModalProps {
  isOpen: boolean
  conversationTitle: string
  onConfirm: () => void
  onCancel: () => void
  isDeleting: boolean
}

function DeleteModal({ isOpen, conversationTitle, onConfirm, onCancel, isDeleting }: DeleteModalProps) {
  if (!isOpen) return null

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={onCancel}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      
      {/* Modal */}
      <div 
        className="relative bg-[#16161e] border border-white/10 rounded-xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 pt-5 pb-4">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
              <Trash2 className="w-5 h-5 text-red-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-semibold text-gray-100">
                Удалить диалог?
              </h3>
              <p className="mt-1.5 text-sm text-gray-400 leading-relaxed">
                Диалог <span className="text-gray-300 font-medium">"{conversationTitle}"</span> будет удалён навсегда. Это действие нельзя отменить.
              </p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="px-5 py-4 bg-white/[0.02] border-t border-white/5 flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isDeleting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Удаление...
              </>
            ) : (
              <>
                <Trash2 className="w-4 h-4" />
                Удалить
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export function ChatHistory({
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  isCollapsed = false,
  onToggleCollapse
}: ChatHistoryProps) {
  const [conversations, setConversations] = useState<ConversationPreview[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  
  // Состояние для модального окна удаления
  const [deleteModal, setDeleteModal] = useState<{
    isOpen: boolean
    conversationId: string | null
    conversationTitle: string
  }>({
    isOpen: false,
    conversationId: null,
    conversationTitle: ''
  })
  const [isDeleting, setIsDeleting] = useState(false)

  // Загрузка списка диалогов
  const fetchConversations = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await api.conversations.list()
      setConversations(data.conversations || [])
    } catch (error) {
      console.error('Ошибка загрузки диалогов:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])

  // Обновляем список при изменении текущего диалога
  useEffect(() => {
    if (currentConversationId) {
      fetchConversations()
    }
  }, [currentConversationId, fetchConversations])

  // Получение заголовка диалога (приоритет: title от backend, затем preview)
  const getTitle = (conv: ConversationPreview): string => {
    // Заголовок теперь приходит с backend (первое сообщение пользователя)
    if (conv.title) return conv.title
    // Fallback на preview если title отсутствует
    if (conv.preview) {
      const text = conv.preview.trim()
      return text.length > 40 ? text.slice(0, 40) + '...' : text
    }
    return 'Новый диалог'
  }

  // Открытие модального окна удаления
  const handleDeleteClick = (e: React.MouseEvent, conv: ConversationPreview) => {
    e.stopPropagation()
    setDeleteModal({
      isOpen: true,
      conversationId: conv.id,
      conversationTitle: getTitle(conv)
    })
  }

  // Подтверждение удаления
  const handleConfirmDelete = async () => {
    if (!deleteModal.conversationId) return
    
    setIsDeleting(true)
    
    try {
      await api.conversations.delete(deleteModal.conversationId)
      setConversations(prev => prev.filter(c => c.id !== deleteModal.conversationId))
      onDeleteConversation(deleteModal.conversationId)
    } catch (error) {
      console.error('Ошибка удаления диалога:', error)
    } finally {
      setIsDeleting(false)
      setDeleteModal({ isOpen: false, conversationId: null, conversationTitle: '' })
    }
  }

  // Отмена удаления
  const handleCancelDelete = () => {
    if (isDeleting) return
    setDeleteModal({ isOpen: false, conversationId: null, conversationTitle: '' })
  }

  // Форматирование даты
  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)
    
    if (minutes < 1) return 'Только что'
    if (minutes < 60) return `${minutes} мин. назад`
    if (hours < 24) return `${hours} ч. назад`
    if (days < 7) return `${days} дн. назад`
    
    return date.toLocaleDateString('ru-RU', { 
      day: 'numeric', 
      month: 'short' 
    })
  }

  // Фильтрация по поиску
  const filteredConversations = conversations.filter(conv => {
    if (!searchQuery.trim()) return true
    const title = getTitle(conv).toLowerCase()
    const preview = (conv.preview || '').toLowerCase()
    const query = searchQuery.toLowerCase()
    return title.includes(query) || preview.includes(query)
  })

  // Свёрнутый режим
  if (isCollapsed) {
    return (
      <>
        <DeleteModal
          isOpen={deleteModal.isOpen}
          conversationTitle={deleteModal.conversationTitle}
          onConfirm={handleConfirmDelete}
          onCancel={handleCancelDelete}
          isDeleting={isDeleting}
        />
        
        <div className="w-12 h-full bg-[#0d0d12] border-r border-white/5 flex flex-col items-center py-3 gap-2">
          <button
            onClick={onToggleCollapse}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
            title="Развернуть историю"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
          
          <button
            onClick={onNewConversation}
            className="p-2 text-gray-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-colors"
            title="Новый чат"
          >
            <Plus className="w-5 h-5" />
          </button>
          
          <div className="flex-1 flex flex-col gap-1 mt-2 overflow-y-auto">
            {conversations.slice(0, 10).map(conv => (
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`p-2 rounded-lg transition-colors ${
                  currentConversationId === conv.id
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                }`}
                title={getTitle(conv)}
              >
                <MessageSquare className="w-4 h-4" />
              </button>
            ))}
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <DeleteModal
        isOpen={deleteModal.isOpen}
        conversationTitle={deleteModal.conversationTitle}
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
        isDeleting={isDeleting}
      />
      
      <div className="w-72 h-full bg-[#0d0d12] border-r border-white/5 flex flex-col">
        {/* Header */}
        <div className="p-3 border-b border-white/5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-300">История чатов</h2>
            <div className="flex items-center gap-1">
              <button
                onClick={onNewConversation}
                className="p-1.5 text-gray-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-colors"
                title="Новый чат"
              >
                <Plus className="w-4 h-4" />
              </button>
              {onToggleCollapse && (
                <button
                  onClick={onToggleCollapse}
                  className="p-1.5 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                  title="Свернуть"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
          
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Поиск..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-8 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-gray-500 hover:text-gray-300"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-center text-gray-500 text-sm">
              Загрузка...
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="p-4 text-center text-gray-500 text-sm">
              {searchQuery ? 'Ничего не найдено' : 'Нет диалогов'}
            </div>
          ) : (
            <div className="py-2">
              {/* Сегодня */}
              {filteredConversations.some(c => {
                const date = new Date(c.updated_at)
                const today = new Date()
                return date.toDateString() === today.toDateString()
              }) && (
                <div className="px-3 py-1.5">
                  <span className="text-xs text-gray-500 font-medium">Сегодня</span>
                </div>
              )}
              
              {filteredConversations.map(conv => {
                const isSelected = currentConversationId === conv.id
                const isHovered = hoveredId === conv.id
                
                return (
                  <div
                    key={conv.id}
                    onClick={() => onSelectConversation(conv.id)}
                    onMouseEnter={() => setHoveredId(conv.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    className={`
                      group relative mx-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all
                      ${isSelected 
                        ? 'bg-blue-500/10 border border-blue-500/20' 
                        : 'hover:bg-white/5 border border-transparent'
                      }
                    `}
                  >
                    <div className="flex items-start gap-2.5">
                      <MessageSquare className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                        isSelected ? 'text-blue-400' : 'text-gray-500'
                      }`} />
                      
                      <div className="flex-1 min-w-0">
                        <div className={`text-sm font-medium truncate ${
                          isSelected ? 'text-blue-100' : 'text-gray-200'
                        }`}>
                          {getTitle(conv)}
                        </div>
                        
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatDate(conv.updated_at)}
                          </span>
                          <span className="text-xs text-gray-600">
                            {conv.message_count} сообщ.
                          </span>
                        </div>
                      </div>
                      
                      {/* Actions */}
                      <div className={`flex items-center gap-0.5 transition-opacity ${
                        isHovered || isSelected ? 'opacity-100' : 'opacity-0'
                      }`}>
                        <button
                          onClick={(e) => handleDeleteClick(e, conv)}
                          className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                          title="Удалить"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-white/5">
          <div className="text-xs text-gray-500 text-center">
            {conversations.length} диалогов
          </div>
        </div>
      </div>
    </>
  )
}
