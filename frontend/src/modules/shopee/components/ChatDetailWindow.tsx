import React, { useEffect, useState } from 'react';
import {
  X,
  ChevronDown,
  ArrowDownCircle,
  Smile,
  Image as ImageIcon,
  PlaySquare,
  FolderOpen,
  Ticket,
  Scissors,
  SendHorizontal
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface ChatDetailWindowProps {
  chat: any;
  runId?: number | null;
  readOnly?: boolean;
  onClose: () => void;
  onConversationUpdated?: () => void;
}

export default function ChatDetailWindow({ chat, runId, readOnly = false, onClose, onConversationUpdated }: ChatDetailWindowProps) {
  const [detail, setDetail] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [buyerTyping, setBuyerTyping] = useState(false);

  const token = typeof window !== 'undefined' ? window.localStorage.getItem(ACCESS_TOKEN_KEY) : null;

  const loadDetail = async () => {
    if (!runId || !chat?.id) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations/${chat.id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json();
      setDetail(payload);
      if (!readOnly) {
        const readResponse = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations/${chat.id}/read`, {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!readResponse.ok) throw new Error(await readResponse.text());
        setDetail(await readResponse.json());
        onConversationUpdated?.();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '客服会话加载失败');
    }
  };

  useEffect(() => {
    loadDetail();
  }, [runId, chat?.id]);

  if (!chat) return null;

  const activeDetail = detail ?? chat;
  const buyerName = activeDetail.buyer_name ?? chat.name ?? '?';
  const avatarInitial = buyerName.charAt(0).toUpperCase();
  const listing = activeDetail.listing ?? chat.listing;
  const messages = activeDetail.messages ?? [];
  const canSend = Boolean(runId && activeDetail.can_send && !readOnly && !submitting);
  const scoreDetail = activeDetail.score_detail;
  const isDamageRefund = activeDetail.scenario_code === 'delivered_damage_refund' && scoreDetail?.resolution_type;
  const scenarioLabels: Record<string, string> = {
    product_detail_inquiry: '商品咨询',
    logistics_stalled_urge: '物流停滞催单',
    delivered_damage_refund: '签收破损退款',
  };
  const scenarioLabel = scenarioLabels[activeDetail.scenario_code] ?? '客服咨询';
  const resolutionLabels: Record<string, string> = {
    platform_return_refund_guidance: '引导平台退货退款流程',
    evidence_first_followup: '先索取证据并跟进',
    replacement_or_resend_promise: '承诺补发或重发',
    direct_refund_promise: '直接承诺退款',
    private_compensation: '私下补偿',
    refuse_or_blame_buyer: '拒绝或责怪买家',
    unclear_response: '处理方式不清晰',
  };

  const sendMessage = async () => {
    const content = message.trim();
    if (!content || !runId || !chat?.id || !canSend) return;
    const optimisticDetail = {
      ...activeDetail,
      messages: [
        ...messages,
        {
          id: `local-${Date.now()}`,
          sender_type: 'seller',
          content,
          sent_game_at: new Date().toISOString(),
        },
      ],
    };
    setDetail(optimisticDetail);
    setMessage('');
    setSubmitting(true);
    setBuyerTyping(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations/${chat.id}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ content }),
      });
      if (!response.ok) throw new Error(await response.text());
      setDetail(await response.json());
      onConversationUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : '消息发送失败');
    } finally {
      setBuyerTyping(false);
      setSubmitting(false);
    }
  };

  const resolveConversation = async () => {
    if (!runId || !chat?.id || readOnly || !activeDetail.can_resolve) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/conversations/${chat.id}/resolve`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json();
      setDetail(payload.conversation);
      onConversationUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : '结束会话失败');
    } finally {
      setSubmitting(false);
    }
  };

  const formatTime = (value?: string) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="w-[360px] h-[500px] flex flex-col bg-white">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 flex-shrink-0">
        <div className="flex items-center gap-2 cursor-pointer group">
          <div className="w-8 h-8 rounded-full bg-gray-300 flex-shrink-0 overflow-hidden border border-gray-200">
            {chat.avatar ? (
              <img src={chat.avatar} alt="avatar" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-white text-[14px] font-bold bg-gray-400">{avatarInitial}</div>
            )}
          </div>
          <span className="text-[14px] font-bold text-gray-800">{buyerName}</span>
          <ChevronDown size={14} className="text-gray-400 group-hover:text-gray-600" />
        </div>
        <div className="flex items-center gap-2">
          {activeDetail.can_resolve && !readOnly && (
            <button onClick={resolveConversation} disabled={submitting} className="text-[12px] text-[#ee4d2d] hover:text-[#d73f22] disabled:text-gray-300">结束</button>
          )}
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X size={20} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-[#f5f5f5] p-3 space-y-4 custom-scrollbar relative">
        <div className="flex justify-center">
          <span className="bg-gray-200 text-white text-[11px] px-2 py-0.5 rounded-full">{scenarioLabel}</span>
        </div>

        {listing && (
          <div className="flex flex-col gap-2 max-w-[85%]">
            <div className="bg-white p-2 rounded-lg border border-gray-200 shadow-sm">
              <p className="text-[12px] text-gray-400 mb-2">商品</p>
              <div className="flex gap-2">
                <div className="w-16 h-16 bg-gray-100 rounded flex-shrink-0 overflow-hidden">
                  {listing.image_url && <img src={listing.image_url} alt="product" className="w-full h-full object-cover" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] text-gray-800 line-clamp-2 leading-tight">{listing.title}</p>
                  <div className="mt-1">
                    <span className="text-[#ee4d2d] font-bold text-[13px]">RM {listing.price ?? 0}</span>
                    {listing.original_price ? <span className="text-gray-400 text-[11px] line-through ml-1">RM {listing.original_price}</span> : null}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.map((item: any) => item.sender_type === 'seller' ? (
          <div key={item.id} className="flex flex-col items-end gap-1 ml-auto max-w-[85%]">
            <div className="bg-[#e1f7e7] text-[13px] text-gray-800 p-2.5 rounded-tl-xl rounded-br-xl rounded-bl-xl shadow-sm leading-relaxed border border-[#d1ecd8]">{item.content}</div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-gray-400">{formatTime(item.sent_game_at)}</span>
              <div className="flex text-[#26aa99]">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="-ml-1.5"><path d="M20 6L9 17l-5-5"/></svg>
              </div>
            </div>
          </div>
        ) : (
          <div key={item.id} className="flex flex-col items-start gap-1 max-w-[85%]">
            <div className="bg-white text-[13px] text-gray-800 p-2.5 rounded-tr-xl rounded-br-xl rounded-bl-xl shadow-sm leading-relaxed">{item.content}</div>
            <span className="text-[10px] text-gray-400 ml-1">{formatTime(item.sent_game_at)}</span>
          </div>
        ))}

        {buyerTyping && (
          <div className="flex flex-col items-start gap-1 max-w-[85%]">
            <div className="bg-white text-[13px] text-gray-800 px-3 py-2.5 rounded-tr-xl rounded-br-xl rounded-bl-xl shadow-sm leading-relaxed flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.2s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.1s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" />
            </div>
          </div>
        )}

        {isDamageRefund ? (
          <div className="bg-white border border-gray-200 rounded-lg p-2 text-[12px] text-gray-700 space-y-1">
            <div>处理方式：{resolutionLabels[scoreDetail.resolution_type] ?? scoreDetail.resolution_type}</div>
            {(scoreDetail.commentary || scoreDetail.summary) && <div>{scoreDetail.commentary || scoreDetail.summary}</div>}
            {Array.isArray(scoreDetail.suggestions) && scoreDetail.suggestions.length > 0 && (
              <ul className="list-disc pl-4 space-y-0.5">
                {scoreDetail.suggestions.map((item: string, index: number) => <li key={index}>{item}</li>)}
              </ul>
            )}
          </div>
        ) : activeDetail.satisfaction_score != null && (
          <div className="bg-white border border-gray-200 rounded-lg p-2 text-[12px] text-gray-700 space-y-1">
            <div>满意度：{activeDetail.satisfaction_score}（{activeDetail.satisfaction_level}）</div>
            {(scoreDetail?.commentary || scoreDetail?.summary) && <div>点评：{scoreDetail.commentary || scoreDetail.summary}</div>}
            {Array.isArray(scoreDetail?.suggestions) && scoreDetail.suggestions.length > 0 && (
              <ul className="list-disc pl-4 space-y-0.5">
                {scoreDetail.suggestions.map((item: string, index: number) => <li key={index}>{item}</li>)}
              </ul>
            )}
          </div>
        )}
        {error && <div className="bg-red-50 border border-red-100 rounded-lg p-2 text-[12px] text-red-600">{error}</div>}

        <div className="sticky bottom-2 flex justify-center pointer-events-none">
          <button className="bg-white p-1 rounded-full shadow-md border border-gray-100 pointer-events-auto text-gray-400 hover:text-[#ee4d2d]">
            <ArrowDownCircle size={20} />
          </button>
        </div>
      </div>

      <div className="p-2 border-t border-gray-100 bg-white">
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={readOnly ? '历史对局不可回复' : '请输入消息...'}
          disabled={!canSend}
          className="w-full h-20 p-2 text-[13px] border-none outline-none resize-none placeholder:text-gray-300 disabled:bg-white disabled:text-gray-400"
        />
        <div className="flex items-center justify-between mt-1">
          <div className="flex items-center gap-3 text-gray-400 px-1">
            <Smile size={18} className="cursor-pointer hover:text-gray-600" />
            <ImageIcon size={18} className="cursor-pointer hover:text-gray-600" />
            <PlaySquare size={18} className="cursor-pointer hover:text-gray-600" />
            <FolderOpen size={18} className="cursor-pointer hover:text-gray-600" />
            <Ticket size={18} className="cursor-pointer hover:text-gray-600" />
            <Scissors size={18} className="cursor-pointer hover:text-gray-600" />
          </div>
          <button onClick={sendMessage} disabled={!message.trim() || !canSend} className="text-gray-300 hover:text-[#ee4d2d] transition-colors disabled:hover:text-gray-300">
            <SendHorizontal size={22} />
          </button>
        </div>
      </div>
    </div>
  );
}
