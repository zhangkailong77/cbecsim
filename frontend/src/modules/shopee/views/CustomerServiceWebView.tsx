import React, { useEffect, useState } from 'react';
import {
  MessageSquare, Search, SlidersHorizontal, ChevronDown, ChevronRight,
  MapPin, Star, SearchCheck, CalendarCheck,
  Smile, Image as ImageIcon, MonitorPlay, Send,
  PlusSquare, PackageX, CheckCheck, MoreHorizontal,
  Reply, CheckCircle2, Copy, Edit3
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface CustomerServiceWebViewProps {
  runId?: number | null;
  readOnly?: boolean;
}

export default function CustomerServiceWebView({ runId, readOnly = false }: CustomerServiceWebViewProps) {
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<'serving' | 'all'>('all');
  const [expandedGroups, setExpandedGroups] = useState({ replied: true, inquiry: true, allBuyers: false });
  const [activeRightTab, setActiveRightTab] = useState('快捷回复');
  const [activeOrderStatus, setActiveOrderStatus] = useState('已完成');
  const [conversations, setConversations] = useState<any[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [buyerTyping, setBuyerTyping] = useState(false);

  const token = typeof window !== 'undefined' ? window.localStorage.getItem(ACCESS_TOKEN_KEY) : null;

  const toggleGroup = (key: keyof typeof expandedGroups) => {
    setExpandedGroups(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const loadConversations = async () => {
    if (!runId) return;
    setError(null);
    try {
      const statusQuery = activeTab === 'serving' ? '&status=open' : '';
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations?scenario=product_detail_inquiry&page=1&page_size=50${statusQuery}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json();
      const items = payload.items ?? [];
      setConversations(items);
      if (!selectedConversationId && items.length > 0) setSelectedConversationId(items[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : '客服会话加载失败');
      setConversations([]);
    }
  };

  const loadDetail = async () => {
    if (!runId || !selectedConversationId) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations/${selectedConversationId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error(await response.text());
      setDetail(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : '客服会话详情加载失败');
      setDetail(null);
    }
  };

  useEffect(() => { loadConversations(); }, [runId, activeTab]);
  useEffect(() => { loadDetail(); }, [runId, selectedConversationId]);

  const sendMessage = async () => {
    const content = message.trim();
    if (!runId || !selectedConversationId || !content || !detail?.can_send || readOnly || submitting) return;
    setDetail({
      ...detail,
      messages: [
        ...(detail.messages ?? []),
        {
          id: `local-${Date.now()}`,
          sender_type: 'seller',
          content,
          sent_game_at: new Date().toISOString(),
        },
      ],
    });
    setMessage('');
    setSubmitting(true);
    setBuyerTyping(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations/${selectedConversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ content }),
      });
      if (!response.ok) throw new Error(await response.text());
      setDetail(await response.json());
      loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : '消息发送失败');
    } finally {
      setBuyerTyping(false);
      setSubmitting(false);
    }
  };

  const resolveConversation = async () => {
    if (!runId || !selectedConversationId || !detail?.can_resolve || readOnly || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations/${selectedConversationId}/resolve`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json();
      setDetail(payload.conversation);
      loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : '结束会话失败');
    } finally {
      setSubmitting(false);
    }
  };

  const formatDate = (value?: string) => {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
  };

  const formatTime = (value?: string) => {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  const toChat = (item: any) => ({
    id: item.id,
    name: item.buyer_name,
    date: formatDate(item.last_message_game_at),
    msg: item.last_message || '商品咨询',
    active: selectedConversationId === item.id,
    avatar: '',
  });
  const openChats = conversations.filter((item) => ['open', 'waiting_seller'].includes(item.status)).map(toChat);
  const allBuyerChats = conversations.map(toChat);

  const mockOrders: any[] = [];
  const mockShortcuts = [
    '商品有现货哦', '谢谢', '感谢您的支持！我们会尽快为您发货。', '我们已经发货了，您可以查看订单页面获取物流状态...',
    '亲爱的顾客，您订购的商品正在运输途中...', '本店经常有促销活动，请关注我们的店铺以获取最新优惠...',
    '这是给您的专属特殊折扣', '抱歉，我们目前无法降低该商品的价格了', '如果您喜欢这款商品，请点击购买，我们会立即为您安排发货',
    '请告诉我您需要的尺寸或重量，以便我们推荐合适的型号',
  ];

  const renderChatItem = (chat: any) => (
    <div key={chat.id} onClick={() => setSelectedConversationId(chat.id)} className={`flex items-start gap-3 px-4 py-3 border-b border-gray-50 cursor-pointer transition-colors ${chat.active ? 'bg-[#f8f8f8] border-l-4 border-l-[#ee4d2d] pl-3' : 'hover:bg-gray-50 border-l-4 border-transparent'}`}>
      <div className="w-10 h-10 rounded-full bg-gray-300 flex-shrink-0 overflow-hidden border border-gray-200">
        {chat.avatar ? <img src={chat.avatar} alt="Avatar" className="w-full h-full object-cover"/> : <div className="w-full h-full flex items-center justify-center text-white text-[16px] font-bold bg-gray-400">{chat.name.charAt(0).toUpperCase()}</div>}
      </div>
      <div className="flex-1 min-w-0 pt-0.5">
        <div className="flex justify-between items-center mb-1">
          <span className="text-[14px] font-medium text-gray-900 truncate">{chat.name}</span>
          <span className="text-[12px] text-gray-400 flex-shrink-0">{chat.date}</span>
        </div>
        <p className={`text-[13px] truncate ${chat.active ? 'text-gray-700' : 'text-gray-500'}`}>{chat.msg}</p>
      </div>
    </div>
  );

  const renderProductTab = () => {
    const listing = detail?.listing;
    if (!listing) {
      return (
        <div className="flex flex-col h-full">
          <div className="flex border-b border-gray-100 bg-white">
            <div className="flex-1 text-center py-2 text-[12px] cursor-pointer text-gray-500 hover:text-[#ee4d2d]">全部</div>
            <div className="flex-1 text-center py-2 text-[12px] cursor-pointer text-[#ee4d2d] font-medium">买家感兴趣</div>
            <div className="flex-1 text-center py-2 text-[12px] cursor-pointer text-gray-500 hover:text-[#ee4d2d]">推荐</div>
          </div>
          <div className="flex-1 flex flex-col items-center justify-center bg-[#fcfcfc]">
            <PackageX size={80} className="text-gray-200 mb-4 stroke-1" />
            <h3 className="text-[15px] text-gray-800 font-medium mb-2">未找到商品</h3>
            <p className="text-[13px] text-gray-400 text-center px-8 mb-6 leading-relaxed">在卖家中心通过下方链接添加商品</p>
            <button className="flex items-center gap-1.5 text-[13px] text-[#2673dd] hover:underline cursor-pointer"><PlusSquare size={14} /> 添加新商品</button>
          </div>
        </div>
      );
    }
    return (
      <div className="flex flex-col h-full bg-[#f6f6f6] p-3 overflow-y-auto">
        <div className="bg-white rounded border border-gray-200 p-3 shadow-sm">
          <div className="flex gap-3">
            <div className="w-20 h-20 bg-gray-100 rounded overflow-hidden border border-gray-100 flex-shrink-0">{listing.image_url && <img src={listing.image_url} alt="Product" className="w-full h-full object-cover" />}</div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] text-gray-800 line-clamp-2">{listing.title}</p>
              <p className="text-[#ee4d2d] font-bold text-[14px] mt-2">RM {listing.price ?? 0}</p>
              <p className="text-[12px] text-gray-500 mt-1">库存：{listing.stock_available ?? 0}</p>
              {listing.quality_total_score != null && <p className="text-[12px] text-gray-500 mt-1">质量分：{listing.quality_total_score}</p>}
            </div>
          </div>
          {listing.specs?.length > 0 && <div className="mt-3 pt-3 border-t border-gray-100 space-y-1">{listing.specs.map((spec: any, index: number) => <div key={index} className="flex justify-between text-[12px]"><span className="text-gray-500">{spec.label}</span><span className="text-gray-800">{spec.value || '-'}</span></div>)}</div>}
          {detail?.satisfaction_score != null && <div className="mt-3 pt-3 border-t border-gray-100 text-[12px] text-gray-700">满意度：{detail.satisfaction_score}（{detail.satisfaction_level}）</div>}
        </div>
      </div>
    );
  };

  const renderOrderTab = () => (
    <div className="flex flex-col h-full bg-[#f6f6f6]">
      <div className="flex border-b border-gray-100 bg-white px-2 overflow-x-auto custom-scrollbar whitespace-nowrap relative">
        {['全部', '未付款', '待发货', '运送中', '已完成', '已取消', '退款/退货'].map((status) => (
          <div key={status} onClick={() => setActiveOrderStatus(status)} className={`px-3 py-2 text-[12px] cursor-pointer font-medium border-b-2 transition-colors flex-shrink-0 ${activeOrderStatus === status ? 'text-[#ee4d2d] border-[#ee4d2d]' : 'text-gray-500 border-transparent hover:text-[#ee4d2d]'}`}>{status}</div>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {mockOrders.length === 0 ? <div className="h-full flex items-center justify-center text-[13px] text-gray-400">售前商品咨询暂无关联订单</div> : mockOrders.map((order, index) => (
          <div key={index} className="bg-white rounded border border-gray-200 mb-2 p-3 shadow-sm"><CheckCircle2 size={14} className="mr-1.5" /> {order.status}<Copy size={12} className="ml-1 opacity-70" /></div>
        ))}
      </div>
    </div>
  );

  const renderShortcutTab = () => (
    <div className="flex flex-col h-full bg-white relative">
      <div className="flex items-center gap-2 p-3 border-b border-gray-100 flex-shrink-0">
        <div className="flex-1 relative"><Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" /><input type="text" placeholder="搜索快捷回复" className="w-full pl-8 pr-2 py-1.5 text-[13px] border border-gray-200 rounded-sm outline-none focus:border-[#ee4d2d] transition-colors" /></div>
        <div className="flex items-center gap-1 cursor-pointer group flex-shrink-0"><span className="text-[13px] text-gray-600 group-hover:text-gray-900">全部分组</span><ChevronDown size={14} className="text-gray-400 group-hover:text-gray-600" /></div>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar"><div className="flex flex-col pb-[60px]">{mockShortcuts.map((text, index) => <div key={index} className="flex items-center gap-3 px-3 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors group"><span className="text-[13px] text-gray-400 w-5 text-right flex-shrink-0">{index + 1}</span><span className="text-[13px] text-gray-800 flex-1 truncate" title={text}>{text}</span><button onClick={() => setMessage(text)} className="px-3 py-1 border border-gray-200 rounded text-[12px] text-gray-600 font-medium bg-white hover:bg-gray-50 transition-colors flex-shrink-0 shadow-sm">发送</button></div>)}</div></div>
      <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-100 p-3 flex justify-center z-10 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]"><button className="flex items-center justify-center gap-2 text-[#ee4d2d] hover:text-[#d73f22] transition-colors text-[13px] font-medium cursor-pointer"><Edit3 size={16} />编辑 / 添加快捷回复</button></div>
    </div>
  );

  const messages = detail?.messages ?? [];
  const listing = detail?.listing;
  const canSend = Boolean(detail?.can_send && !readOnly && !submitting);

  return (
    <div className="flex w-full h-full bg-[#f6f6f6] font-sans text-[#333] overflow-hidden min-w-[800px]">
      <nav className="w-[72px] bg-white border-r border-gray-200 flex flex-col items-center py-4 flex-shrink-0 z-10 h-full"><div className="flex flex-col gap-6 w-full"><div className="flex flex-col items-center gap-1 cursor-pointer group relative"><div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-[#ee4d2d] rounded-r-md"></div><MessageSquare size={24} className="text-[#ee4d2d]" /><span className="text-[11px] text-[#ee4d2d] font-medium">聊天</span></div></div></nav>
      <aside className="w-[320px] bg-white border-r border-gray-200 flex flex-col flex-shrink-0 z-10 h-full">
        <div className="p-3 border-b border-gray-100 flex gap-2"><div className="flex-1 relative"><Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" /><input type="text" placeholder="搜索全部" className="w-full pl-8 pr-3 py-1.5 text-[13px] border border-gray-200 rounded-sm outline-none focus:border-[#ee4d2d] bg-gray-50 focus:bg-white transition-colors" /></div><button className="px-2 border border-gray-200 rounded-sm text-gray-500 hover:bg-gray-50 transition-colors flex items-center justify-center"><SlidersHorizontal size={14} /></button></div>
        <div className="flex border-b border-gray-200"><div onClick={() => setActiveTab('serving')} className={`flex-1 flex justify-center items-center py-3 cursor-pointer text-[13px] font-medium border-b-2 transition-colors ${activeTab === 'serving' ? 'text-[#ee4d2d] border-[#ee4d2d]' : 'text-gray-600 border-transparent hover:text-[#ee4d2d]'}`}>今日接待 <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full ml-1 mb-2" /></div><div onClick={() => setActiveTab('all')} className={`flex-1 flex justify-center items-center py-3 cursor-pointer text-[13px] font-medium border-b-2 transition-colors ${activeTab === 'all' ? 'text-[#ee4d2d] border-[#ee4d2d]' : 'text-gray-600 border-transparent hover:text-[#ee4d2d]'}`}>全部聊天 <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full ml-1 mb-2" /></div></div>
        <div className="flex-1 overflow-y-auto custom-scrollbar">{error && <div className="px-4 py-2 text-[12px] text-red-500 bg-red-50">{error}</div>}{activeTab === 'serving' ? <div><div onClick={() => toggleGroup('replied')} className="flex items-center gap-2 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors select-none group">{expandedGroups.replied ? <ChevronDown size={14} className="text-gray-500 group-hover:text-gray-700"/> : <ChevronRight size={14} className="text-gray-500 group-hover:text-gray-700"/>}<span className="font-medium text-[13px] text-gray-800">已回复 ({openChats.length})</span></div>{expandedGroups.replied && openChats.map(renderChatItem)}</div> : <div className="flex flex-col"><div><div onClick={() => toggleGroup('inquiry')} className="flex items-center gap-2 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors select-none group">{expandedGroups.inquiry ? <ChevronDown size={14} className="text-gray-500 group-hover:text-gray-700"/> : <ChevronRight size={14} className="text-gray-500 group-hover:text-gray-700"/>}<span className="font-medium text-[13px] text-gray-800">无订单咨询 ({openChats.length})</span></div>{expandedGroups.inquiry && openChats.map(renderChatItem)}</div><div><div onClick={() => toggleGroup('allBuyers')} className="flex items-center gap-2 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors select-none group border-t border-gray-50">{expandedGroups.allBuyers ? <ChevronDown size={14} className="text-gray-500 group-hover:text-gray-700"/> : <ChevronRight size={14} className="text-gray-500 group-hover:text-gray-700"/>}<span className="font-medium text-[13px] text-gray-800">所有买家</span></div>{expandedGroups.allBuyers && allBuyerChats.map(renderChatItem)}</div></div>}</div>
      </aside>
      <main className="flex flex-col flex-1 h-full min-w-[400px]">
        <div className="h-[70px] bg-white border-b border-gray-200 px-6 flex justify-between items-center flex-shrink-0 shadow-sm z-10"><div className="flex flex-col justify-center"><div className="flex items-center gap-2"><span className="text-[16px] font-bold text-gray-800">{detail?.buyer_name ?? '请选择会话'}</span><ChevronDown size={14} className="text-gray-400 cursor-pointer hover:text-gray-600" /></div><div className="flex items-center gap-4 text-[12px] text-gray-500 mt-1"><span className="flex items-center gap-1"><MapPin size={12}/> Shopee 买家</span><span className="flex items-center gap-1"><Star size={12} className="text-gray-300 fill-gray-300"/> 0.0</span><span className="flex items-center gap-1 text-green-600"><SearchCheck size={12}/> 售前咨询</span><span className="flex items-center gap-1"><CalendarCheck size={12}/> 商品细节追问</span></div></div><button onClick={() => setIsRightPanelOpen(!isRightPanelOpen)} className={`p-2 rounded hover:bg-gray-100 transition-colors ${!isRightPanelOpen ? 'text-[#ee4d2d] bg-red-50 hover:bg-red-100' : 'text-gray-400'}`}><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><line x1="15" y1="3" x2="15" y2="21" />{isRightPanelOpen ? <path d="M19 12l-3-3v6z" fill="currentColor" stroke="none" /> : <path d="M11 12l-3-3v6z" fill="currentColor" stroke="none" />}</svg></button></div>
        <div className="flex-1 overflow-y-auto bg-[#f5f5f5] p-6 space-y-6"><div className="flex justify-center"><span className="bg-white text-gray-500 text-[12px] px-3 py-1 rounded-full shadow-sm border border-gray-100">商品咨询</span></div>{listing && <div className="flex flex-col items-start max-w-[70%]"><span className="text-[12px] text-gray-500 mb-1 ml-1">商品</span><div className="flex flex-col items-end w-fit"><div className="bg-white p-3 rounded-lg border border-gray-200 shadow-sm flex gap-3 cursor-pointer hover:shadow-md transition-shadow"><div className="w-20 h-20 bg-gray-100 rounded overflow-hidden flex-shrink-0 border border-gray-100">{listing.image_url && <img src={listing.image_url} alt="product" className="w-full h-full object-cover opacity-80" />}</div><div className="flex-1 flex flex-col justify-between py-0.5 min-w-0"><p className="text-[13px] text-gray-800 leading-snug line-clamp-2">{listing.title}</p><div className="mt-2"><span className="text-[#ee4d2d] font-bold text-[14px]">RM {listing.price ?? 0}</span>{listing.original_price ? <span className="text-gray-400 text-[12px] line-through ml-2">RM {listing.original_price}</span> : null}</div></div></div></div></div>}{messages.map((item: any) => item.sender_type === 'seller' ? <div key={item.id} className="flex flex-col items-end max-w-[70%] ml-auto"><div className="bg-[#e1f7e7] text-[14px] text-gray-800 p-3 rounded-tl-xl rounded-br-xl rounded-bl-xl shadow-sm border border-[#d1ecd8] flex items-end gap-2"><span>{item.content}</span><div className="flex items-center gap-1 mb-[-2px]"><span className="text-[11px] text-gray-500">{formatTime(item.sent_game_at)}</span><CheckCheck size={14} className="text-[#26aa99]"/></div></div></div> : <div key={item.id} className="flex flex-col items-start max-w-[70%] group"><div className="flex items-center gap-2"><div className="bg-white text-[14px] text-gray-800 p-3 rounded-tr-xl rounded-br-xl rounded-bl-xl shadow-sm border border-gray-100">{item.content}<div className="text-[11px] text-gray-400 mt-2 flex justify-between items-center border-t border-gray-100 pt-1 min-w-[120px]"><span></span><span>{formatTime(item.sent_game_at)}</span></div></div><div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1"><button className="p-1.5 bg-white rounded-full shadow-sm text-gray-400 hover:text-gray-600 border border-gray-100"><MoreHorizontal size={14} /></button><button className="flex items-center gap-1 px-3 py-1.5 bg-white rounded shadow-sm text-gray-600 text-[12px] hover:bg-gray-50 border border-gray-100"><Reply size={14} className="text-gray-400" /><span>Reply</span></button></div></div></div>)}{buyerTyping && <div className="flex flex-col items-start max-w-[70%] group"><div className="flex items-center gap-2"><div className="bg-white text-[14px] text-gray-800 px-4 py-3 rounded-tr-xl rounded-br-xl rounded-bl-xl shadow-sm border border-gray-100 flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.2s]" /><span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.1s]" /><span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" /></div></div></div>}{detail?.satisfaction_score != null && <div className="bg-white border border-gray-200 rounded-lg p-3 text-[13px] text-gray-700">满意度：{detail.satisfaction_score}（{detail.satisfaction_level}）</div>}</div>
        <div className="bg-white border-t border-gray-200 p-3 flex flex-col z-10 flex-shrink-0 h-[160px]"><div className="flex items-center justify-between mb-2"><div className="flex items-center gap-4 text-[#4f8ff7]"><Smile size={20} className="cursor-pointer hover:opacity-80 transition-opacity" /><ImageIcon size={20} className="cursor-pointer hover:opacity-80 transition-opacity" /><MonitorPlay size={20} className="cursor-pointer hover:opacity-80 transition-opacity" /></div>{detail?.can_resolve && !readOnly && <button onClick={resolveConversation} disabled={submitting} className="text-[13px] text-[#ee4d2d] hover:text-[#d73f22] disabled:text-gray-300">结束会话</button>}</div><textarea value={message} onChange={(event) => setMessage(event.target.value)} disabled={!canSend} className="flex-1 w-full text-[14px] resize-none outline-none placeholder:text-gray-400 mt-1 disabled:bg-white disabled:text-gray-400" placeholder={readOnly ? '历史对局不可回复' : '在此输入消息...'}></textarea><div className="flex justify-between items-center mt-2"><span className="text-[12px] text-gray-400">按 Shift + Enter 换行</span><button onClick={sendMessage} disabled={!message.trim() || !canSend} className="text-gray-300 hover:text-[#ee4d2d] transition-colors disabled:cursor-not-allowed disabled:hover:text-gray-300"><Send size={24} /></button></div></div>
      </main>
      <aside className={`bg-white h-full flex-shrink-0 z-10 transition-[width,border] duration-300 ease-in-out overflow-hidden ${isRightPanelOpen ? 'w-[360px] border-l border-gray-200' : 'w-0 border-l-0 border-transparent'}`}><div className="w-[360px] flex flex-col h-full relative"><div className="flex border-b border-gray-200 flex-shrink-0">{['商品', '订单', '快捷回复'].map((tab) => <div key={tab} onClick={() => setActiveRightTab(tab)} className={`flex-1 text-center py-3 text-[13px] cursor-pointer font-medium border-b-2 transition-colors ${activeRightTab === tab ? 'text-[#ee4d2d] border-[#ee4d2d]' : 'text-gray-600 border-transparent hover:text-[#ee4d2d]'}`}>{tab}</div>)}</div>{activeRightTab === '快捷回复' ? renderShortcutTab() : activeRightTab === '订单' ? renderOrderTab() : renderProductTab()}</div></aside>
    </div>
  );
}
