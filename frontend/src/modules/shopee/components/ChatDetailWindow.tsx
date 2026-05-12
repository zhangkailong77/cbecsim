import React from 'react';
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

interface ChatDetailWindowProps {
  chat: any;
  onClose: () => void;
}

export default function ChatDetailWindow({ chat, onClose }: ChatDetailWindowProps) {
  if (!chat) return null;

  return (
    <div className="w-[360px] h-[500px] flex flex-col bg-white">
      
      {/* 顶部 Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 flex-shrink-0">
        <div className="flex items-center gap-2 cursor-pointer group">
          <div className="w-8 h-8 rounded-full bg-black flex-shrink-0">
             {chat.avatar && <img src={chat.avatar} className="w-full h-full rounded-full" />}
          </div>
          <span className="text-[14px] font-bold text-gray-800">{chat.name}</span>
          <ChevronDown size={14} className="text-gray-400 group-hover:text-gray-600" />
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
          <X size={20} />
        </button>
      </div>

      {/* 聊天内容区 */}
      <div className="flex-1 overflow-y-auto bg-[#f5f5f5] p-3 space-y-4 custom-scrollbar relative">
        
        {/* 时间分割线 */}
        <div className="flex justify-center">
          <span className="bg-gray-200 text-white text-[11px] px-2 py-0.5 rounded-full">3月31日</span>
        </div>

        {/* 商品卡片 (买家发送) */}
        <div className="flex flex-col gap-2 max-w-[85%]">
          <div className="bg-white p-2 rounded-lg border border-gray-200 shadow-sm">
            <p className="text-[12px] text-gray-400 mb-2">商品</p>
            <div className="flex gap-2">
              <div className="w-16 h-16 bg-gray-100 rounded flex-shrink-0 overflow-hidden">
                <img src="https://via.placeholder.com/64" alt="product" className="w-full h-full object-cover" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[12px] text-gray-800 line-clamp-2 leading-tight">
                  HomeNeat 简易衣柜 卧室多功能挂衣架 组装式储物柜...
                </p>
                <div className="mt-1">
                  <span className="text-[#ee4d2d] font-bold text-[13px]">฿1,174 - ฿5,353</span>
                  <span className="text-gray-400 text-[11px] line-through ml-1">฿1,199 - ฿5,398</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 买家消息气泡 */}
        <div className="flex flex-col items-start gap-1 max-w-[85%]">
          <div className="bg-white text-[13px] text-gray-800 p-2.5 rounded-tr-xl rounded-br-xl rounded-bl-xl shadow-sm leading-relaxed">
            请问还有这个柜子吗？
          </div>
          <span className="text-[10px] text-gray-400 ml-1">22:48</span>
        </div>

        {/* 卖家回复气泡 (右侧) */}
        <div className="flex flex-col items-end gap-1 ml-auto max-w-[85%]">
          <div className="bg-[#e1f7e7] text-[13px] text-gray-800 p-2.5 rounded-tl-xl rounded-br-xl rounded-bl-xl shadow-sm leading-relaxed border border-[#d1ecd8]">
            您好！欢迎来到 #HomeNeat#。很高兴为您服务~
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[10px] text-gray-400">22:48</span>
            <div className="flex text-[#26aa99]">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="-ml-1.5"><path d="M20 6L9 17l-5-5"/></svg>
            </div>
          </div>
        </div>

        {/* 悬浮回到底部按钮 */}
        <div className="sticky bottom-2 flex justify-center pointer-events-none">
          <button className="bg-white p-1 rounded-full shadow-md border border-gray-100 pointer-events-auto text-gray-400 hover:text-[#ee4d2d]">
            <ArrowDownCircle size={20} />
          </button>
        </div>
      </div>

      {/* 底部输入区 */}
      <div className="p-2 border-t border-gray-100 bg-white">
        {/* 输入框 */}
        <textarea 
          placeholder="请输入消息..."
          className="w-full h-20 p-2 text-[13px] border-none outline-none resize-none placeholder:text-gray-300"
        />
        
        {/* 工具栏 */}
        <div className="flex items-center justify-between mt-1">
          <div className="flex items-center gap-3 text-gray-400 px-1">
            <Smile size={18} className="cursor-pointer hover:text-gray-600" />
            <ImageIcon size={18} className="cursor-pointer hover:text-gray-600" />
            <PlaySquare size={18} className="cursor-pointer hover:text-gray-600" />
            <FolderOpen size={18} className="cursor-pointer hover:text-gray-600" />
            <Ticket size={18} className="cursor-pointer hover:text-gray-600" />
            <Scissors size={18} className="cursor-pointer hover:text-gray-600" />
          </div>
          <button className="text-gray-300 hover:text-[#ee4d2d] transition-colors">
            <SendHorizontal size={22} />
          </button>
        </div>
      </div>
    </div>
  );
}