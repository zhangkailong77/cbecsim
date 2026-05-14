import { useEffect, useState } from 'react';
import {
  ChevronsRight,
  ChevronDown,
  ChevronRight,
  Search,
  ExternalLink
} from 'lucide-react';
import ChatDetailWindow from './ChatDetailWindow';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface ChatMessagesDrawerProps {
  open: boolean;
  runId?: number | null;
  readOnly?: boolean;
  onClose?: () => void;
  onOpenWebVersion?: () => void;
  onUnreadCountChange?: (count: number) => void;
}

export default function ChatMessagesDrawer({ open, runId, readOnly = false, onClose, onOpenWebVersion, onUnreadCountChange }: ChatMessagesDrawerProps) {
  const [activeTab, setActiveTab] = useState<'serving' | 'all'>('serving');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [selectedChat, setSelectedChat] = useState<any>(null);
  const [conversations, setConversations] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [expanded, setExpanded] = useState({
    replied: true,
    inquiry: true,
    allBuyers: true
  });

  const token = typeof window !== 'undefined' ? window.localStorage.getItem(ACCESS_TOKEN_KEY) : null;

  const loadConversations = async () => {
    if (!runId || !open) return;
    setError(null);
    try {
      const statusQuery = activeTab === 'serving' ? '&status=open' : '';
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations?page=1&page_size=50${statusQuery}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json();
      const items = payload.items ?? [];
      setConversations(items);
      onUnreadCountChange?.(items.reduce((sum: number, item: any) => sum + Number(item.unread_count ?? 0), 0));
    } catch (err) {
      setError(err instanceof Error ? err.message : '客服会话加载失败');
      setConversations([]);
    }
  };

  useEffect(() => {
    loadConversations();
  }, [runId, open, activeTab]);

  const toggleGroup = (key: keyof typeof expanded) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const scenarioLabels: Record<string, string> = {
    product_detail_inquiry: '商品咨询',
    logistics_stalled_urge: '物流停滞催单',
    delivered_damage_refund: '签收破损退款',
  };

  const toChat = (item: any) => ({
    id: item.id,
    name: item.buyer_name,
    date: item.last_message_game_at ? new Date(item.last_message_game_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) : '',
    msg: item.last_message || scenarioLabels[item.scenario_code] || '客服咨询',
    avatar: '',
    listing: item.listing,
    scenario_code: item.scenario_code,
    raw: item,
  });

  const openConversations = conversations.filter((item) => ['open', 'waiting_seller'].includes(item.status));
  const noOrderConversations = openConversations.filter((item) => item.scenario_code === 'product_detail_inquiry');
  const hasUnreadMessages = conversations.some((item) => Number(item.unread_count ?? 0) > 0);
  const hasOpenUnreadMessages = openConversations.some((item) => Number(item.unread_count ?? 0) > 0);
  const openChats = openConversations.map(toChat);
  const noOrderChats = noOrderConversations.map(toChat);
  const allChats = conversations.map(toChat);

  const renderChatItem = (chat: any) => {
    const isActive = selectedChat?.id === chat.id;
    const avatarInitial = (chat.name || '?').charAt(0).toUpperCase();
    return (
      <div
        key={chat.id}
        onClick={() => setSelectedChat(chat)}
        className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
          isActive ? 'bg-[#fff1ed]' : 'hover:bg-gray-50'
        }`}
      >
        <div className="w-10 h-10 rounded-full bg-gray-300 flex-shrink-0 overflow-hidden border border-gray-200">
          {chat.avatar ? (
            <img src={chat.avatar} alt="avatar" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-white text-[16px] font-bold bg-gray-400">{avatarInitial}</div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-center mb-0.5">
            <span className={`text-[13px] font-medium truncate pr-2 ${isActive ? 'text-[#ee4d2d]' : 'text-gray-900'}`}>
              {chat.name}
            </span>
            <span className="text-[11px] text-gray-400 flex-shrink-0">{chat.date}</span>
          </div>
          <p className="text-[12px] text-gray-500 truncate">{chat.msg}</p>
        </div>
      </div>
    );
  };

  return (
    <>
      <aside
        className={`h-full border-l border-gray-200 bg-white transition-[width] duration-300 ease-out flex-shrink-0 relative z-40 ${
          open ? 'w-[360px]' : 'w-0'
        }`}
      >
        {selectedChat && (
          <div
            className={`absolute bottom-0 right-full mr-3 z-50 mb-3 rounded-lg shadow-[0_4px_24px_rgba(0,0,0,0.12)] bg-white overflow-hidden transition-opacity duration-300 ${
              open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
            }`}
          >
            <ChatDetailWindow
              chat={selectedChat}
              runId={runId}
              readOnly={readOnly}
              onClose={() => setSelectedChat(null)}
              onConversationUpdated={loadConversations}
            />
          </div>
        )}

        <div className={`${open ? 'opacity-100' : 'opacity-0 pointer-events-none'} h-full transition-opacity duration-200 flex flex-col`}>
          <div className="flex items-center justify-between px-3 py-3 border-b border-gray-100 relative">
            <div className="flex items-center gap-3">
              <span className="text-[#ee4d2d] font-bold text-[18px]">Chat</span>

              <div className="relative">
                <div
                  onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                  className={`flex items-center gap-1.5 border rounded-sm px-2 py-1 cursor-pointer transition-colors ${isDropdownOpen ? 'border-[#ee4d2d] bg-gray-50' : 'border-gray-200 hover:bg-gray-50'}`}
                >
                  <span className="text-[12px] text-gray-600">与买家聊...</span>
                  {hasUnreadMessages ? <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full" /> : null}
                  <ChevronDown size={14} className="text-gray-400" />
                </div>

                {isDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setIsDropdownOpen(false)} />
                    <div className="absolute top-full left-0 mt-1 bg-white border border-gray-100 shadow-lg rounded-sm py-2 z-20 w-[180px]">
                      <div className="px-3 py-2 hover:bg-gray-50 text-[13px] text-[#ee4d2d] font-medium flex items-center justify-between">
                        与买家聊天 {hasUnreadMessages ? <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full" /> : null}
                      </div>
                      <div className="px-3 py-2 hover:bg-gray-50 text-[13px] text-gray-600">
                        与联盟伙伴聊天
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onOpenWebVersion}
                className="flex items-center gap-1 text-[12px] text-blue-500 hover:text-blue-600"
              >
                <ExternalLink size={13} />
                <span>网页版</span>
              </button>
              <div className="w-px h-3 bg-gray-200 mx-1" />
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <ChevronsRight size={18} />
              </button>
            </div>
          </div>

          <div className="px-3 pt-3 pb-2">
            <div className="relative group">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-[#ee4d2d]" />
              <input
                type="text"
                placeholder="搜索名称"
                className="w-full pl-8 pr-3 py-1.5 text-[13px] border border-gray-200 rounded-sm outline-none focus:border-[#ee4d2d] transition-colors"
              />
            </div>
          </div>

          <div className="flex border-b border-gray-200">
            <div
              onClick={() => setActiveTab('serving')}
              className={`flex-1 flex justify-center items-center py-2.5 cursor-pointer border-b-2 transition-colors ${activeTab === 'serving' ? 'border-[#ee4d2d]' : 'border-transparent hover:bg-gray-50'}`}
            >
              <span className={`text-[13px] font-medium ${activeTab === 'serving' ? 'text-[#ee4d2d]' : 'text-gray-600'}`}>今日接待</span>
              {hasOpenUnreadMessages ? <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full ml-1 mb-2" /> : null}
            </div>
            <div
              onClick={() => setActiveTab('all')}
              className={`flex-1 flex justify-center items-center py-2.5 cursor-pointer border-b-2 transition-colors ${activeTab === 'all' ? 'border-[#ee4d2d]' : 'border-transparent hover:bg-gray-50'}`}
            >
              <span className={`text-[13px] font-medium ${activeTab === 'all' ? 'text-[#ee4d2d]' : 'text-gray-600'}`}>全部聊天</span>
              {hasUnreadMessages ? <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full ml-1 mb-2" /> : null}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {error && <div className="px-3 py-2 text-[12px] text-red-500 bg-red-50">{error}</div>}
            {activeTab === 'serving' ? (
              <div>
                <div
                  onClick={() => toggleGroup('replied')}
                  className="flex items-center gap-1.5 px-3 py-2.5 text-[13px] text-gray-700 font-medium cursor-pointer hover:bg-gray-50 select-none"
                >
                  {expanded.replied ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <span>已回复 ({openChats.length})</span>
                </div>
                {expanded.replied && openChats.map(renderChatItem)}
              </div>
            ) : (
              <div className="flex flex-col">
                <div>
                  <div
                    onClick={() => toggleGroup('inquiry')}
                    className="flex items-center gap-1.5 px-3 py-2.5 text-[13px] text-gray-700 font-medium cursor-pointer hover:bg-gray-50 select-none"
                  >
                    {expanded.inquiry ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    <span>无订单咨询 ({noOrderChats.length})</span>
                  </div>
                  {expanded.inquiry && noOrderChats.map(renderChatItem)}
                </div>

                <div className="mt-1">
                  <div className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 select-none">
                    <div
                      onClick={() => toggleGroup('allBuyers')}
                      className="flex items-center gap-1.5 text-[13px] text-gray-700 font-medium cursor-pointer flex-1"
                    >
                      {expanded.allBuyers ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      <span>所有买家</span>
                    </div>
                    <button className="flex items-center gap-1 border border-gray-200 bg-gray-50 px-2 py-1 rounded-sm text-[12px] text-gray-600 hover:bg-gray-100 transition-colors">
                      <span>筛选</span>
                    </button>
                  </div>
                  {expanded.allBuyers && allChats.map(renderChatItem)}
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
