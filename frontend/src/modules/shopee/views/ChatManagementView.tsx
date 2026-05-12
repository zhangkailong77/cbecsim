import React from 'react';
import { 
  ChevronRight, 
  HelpCircle, 
  Flame,
  MessageCircle,
  MessageSquare,
  MessageSquareQuote
} from 'lucide-react';

interface ChatManagementViewProps {
  onOpenAutoReply: () => void;
  onOpenQuickReply: () => void;
}

export default function ChatManagementView({ onOpenAutoReply, onOpenQuickReply }: ChatManagementViewProps) {
  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar">
      <div className="mx-auto max-w-[1600px] flex flex-col gap-5">
        
        {/* ================= 1. 聊天表现 (Chat Performance) ================= */}
        <section className="border border-[#ececec] bg-white rounded-[2px] shadow-sm">
          {/* Header */}
          <div className="px-6 py-4 flex items-center justify-between border-b border-[#f2f2f2]">
            <div className="flex items-center gap-3">
              <h2 className="text-[16px] font-medium text-[#333]">聊天表现</h2>
              <span className="text-[12px] text-gray-400 font-normal">
                (数据来自 2024/04/11 至 2024/05/11 GMT+08)
              </span>
            </div>
            <a href="#" className="flex items-center text-[13px] text-[#2673dd] hover:underline cursor-pointer">
              更多 <ChevronRight size={14} className="ml-0.5" />
            </a>
          </div>
          
          {/* Data Grid */}
          <div className="grid grid-cols-3 py-6">
            {/* Col 1 */}
            <div className="flex flex-col px-8 border-r border-[#f2f2f2]">
              <div className="flex items-center gap-1.5 text-[13px] text-gray-600 mb-2">
                咨询人数 <HelpCircle size={14} className="text-gray-300 cursor-help" />
              </div>
              <div className="text-[28px] text-[#333] mb-2 leading-none">0</div>
              <div className="flex items-center gap-1 text-[12px] text-gray-400 mt-auto">
                较前30天 <span className="text-[#ee4d2d] flex items-center font-medium">▼ 100.00%</span>
              </div>
            </div>

            {/* Col 2 */}
            <div className="flex flex-col px-8 border-r border-[#f2f2f2]">
              <div className="flex items-center gap-1.5 text-[13px] text-gray-600 mb-2">
                聊天回复率 <HelpCircle size={14} className="text-gray-300 cursor-help" />
              </div>
              <div className="text-[28px] text-[#333] mb-2 leading-none">-</div>
              <div className="flex items-center gap-1 text-[12px] text-gray-400 mt-auto">
                较前30天 -
              </div>
            </div>

            {/* Col 3 */}
            <div className="flex flex-col px-8">
              <div className="flex items-center gap-1.5 text-[13px] text-gray-600 mb-2">
                响应时间 <HelpCircle size={14} className="text-gray-300 cursor-help" />
              </div>
              <div className="text-[28px] text-[#333] mb-2 leading-none">00:00:00</div>
              <div className="flex items-center gap-1 text-[12px] text-gray-400 mt-auto">
                较前30天 <span className="text-[#5cba47] flex items-center font-medium">▼ 100.00%</span>
              </div>
            </div>
          </div>
        </section>

        {/* ================= 2. 聊天助手 (Chat Assistant) ================= */}
        <section className="border border-[#ececec] bg-white rounded-[2px] shadow-sm flex flex-col">
          <div className="px-6 py-4 border-b border-[#f2f2f2]">
            <h2 className="text-[16px] font-medium text-[#333]">聊天助手</h2>
          </div>
          
          <div className="p-6 grid grid-cols-3 gap-6">
            
            {/* Card 1: 自动回复 */}
            <div className="border border-[#e5e5e5] rounded-[2px] p-5 flex flex-col hover:shadow-sm transition-shadow">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-[#ee4d2d] flex items-center justify-center flex-shrink-0 text-white">
                  <MessageCircle size={20} fill="currentColor" className="text-white" />
                </div>
                <div>
                  <div className="flex items-center gap-1.5 text-[14px] font-medium text-[#333] mb-1.5">
                    自动回复 <HelpCircle size={14} className="text-gray-300 cursor-help" />
                  </div>
                  <p className="text-[12px] text-gray-500 leading-relaxed min-h-[40px]">
                    买家发起对话时自动发送欢迎语。
                  </p>
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  onClick={onOpenAutoReply}
                  className="px-5 py-1.5 border border-[#ee4d2d] text-[#ee4d2d] text-[13px] font-medium rounded-[2px] hover:bg-[#fff1ed] transition-colors"
                >
                  开启
                </button>
              </div>
            </div>

            {/* Card 2: 快捷回复 */}
            <div className="border border-[#e5e5e5] rounded-[2px] p-5 flex flex-col hover:shadow-sm transition-shadow">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-[#ee4d2d] flex items-center justify-center flex-shrink-0 text-white">
                  <MessageSquare size={20} fill="currentColor" className="text-white" />
                </div>
                <div>
                  <div className="flex items-center gap-1.5 text-[14px] font-medium text-[#333] mb-1.5">
                    快捷回复 <HelpCircle size={14} className="text-gray-300 cursor-help" />
                  </div>
                  <p className="text-[12px] text-gray-500 leading-relaxed min-h-[40px]">
                    帮助客服通过预设内容更快地响应买家。
                  </p>
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  onClick={onOpenQuickReply}
                  className="px-5 py-1.5 border border-[#ee4d2d] text-[#ee4d2d] text-[13px] font-medium rounded-[2px] hover:bg-[#fff1ed] transition-colors"
                >
                  编辑
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}