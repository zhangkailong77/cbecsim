import { useState } from 'react';
import {
  ChevronsRight,
  ChevronDown,
  ChevronRight,
  Search,
  ExternalLink
} from 'lucide-react';
import ChatDetailWindow from './ChatDetailWindow';

interface ChatMessagesDrawerProps {
  open: boolean;
  onClose?: () => void;
  onOpenWebVersion?: () => void;
}

export default function ChatMessagesDrawer({ open, onClose, onOpenWebVersion }: ChatMessagesDrawerProps) {
  // 1. 基础状态管理
  const [activeTab, setActiveTab] = useState<'serving' | 'all'>('serving');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [selectedChat, setSelectedChat] = useState<any>(null);
  
  // 2. 各分组的展开/收起状态
  const [expanded, setExpanded] = useState({
    replied: true,
    inquiry: true,
    allBuyers: true
  });

  const toggleGroup = (key: keyof typeof expanded) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // 3. 模拟数据...
  const servingChats = [
    { id: 's1', name: 'vasuchathongnoi', date: '02/04', msg: '亲爱的，我们的商品正在备货中，请耐心等待...', avatar: '' },
    { id: 's2', name: 'pattanun23289', date: '02/04', msg: '亲爱的，商品已经寄出了，物流单号是...', avatar: 'https://api.dicebear.com/7.x/notionists/svg?seed=pattanun' }
  ];

  const inquiryChats = [
    { id: 'a1', name: 'pattanun23289', date: '02/04', msg: '这款柜子还有其他颜色吗？', avatar: 'https://api.dicebear.com/7.x/notionists/svg?seed=pattanun' }
  ];
  
  const allBuyerChats = [
    { id: 'a2', name: 'vasuchathongnoi', date: '02/04', msg: '亲爱的，由于物流原因可能需要延迟发货。', avatar: '' },
    { id: 'a3', name: 'nutcha1279', date: '30/03', msg: '亲爱的，对于这次不好的体验我们深表歉意...', avatar: 'https://api.dicebear.com/7.x/notionists/svg?seed=nutcha' },
    { id: 'a4', name: 'tjitsunan51', date: '30/03', msg: '你好亲爱的，欢迎来到我们的店铺...', avatar: '' },
    { id: 'a5', name: 'khunjoejoe', date: '25/03', msg: '包裹已经加固包装了，请放心。', avatar: 'https://api.dicebear.com/7.x/notionists/svg?seed=joe' },
    { id: 'a6', name: 'minize', date: '23/03', msg: '退款已经处理，请查看您的账户。', avatar: 'https://api.dicebear.com/7.x/notionists/svg?seed=minize' },
  ];

  // 5. 渲染单个聊天列表项
  const renderChatItem = (chat: any) => {
    const isActive = selectedChat?.id === chat.id;
    return (
      <div 
        key={chat.id} 
        onClick={() => setSelectedChat(chat)} 
        className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
          isActive ? 'bg-[#fff1ed]' : 'hover:bg-gray-50'
        }`}
      >
        <div className={`w-10 h-10 rounded-full flex-shrink-0 overflow-hidden border border-gray-100 flex items-center justify-center ${!chat.avatar ? 'bg-gray-200' : ''}`}>
          {chat.avatar ? (
            <img src={chat.avatar} alt="avatar" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full bg-black rounded-full" />
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
        {/* ======================= 新增/修改核心逻辑 ======================= */}
        {/* 将聊天详情窗口包裹在这里，使用 absolute 和 right-full 紧贴父元素(右侧面板)的左边缘 */}
        {selectedChat && (
          <div 
            className={`absolute bottom-0 right-full mr-3 z-50 mb-3 rounded-lg shadow-[0_4px_24px_rgba(0,0,0,0.12)] bg-white overflow-hidden transition-opacity duration-300 ${
              open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
            }`}
          >
            {/* 提示：确保你的 ChatDetailWindow 组件内部没有写 position: fixed，而是让他自适应外层这个 div 的大小 */}
            <ChatDetailWindow 
              chat={selectedChat} 
              onClose={() => setSelectedChat(null)} 
            />
          </div>
        )}
        {/* =============================================================== */}

        <div className={`${open ? 'opacity-100' : 'opacity-0 pointer-events-none'} h-full transition-opacity duration-200 flex flex-col`}>
          
          {/* 顶部 Header */}
          <div className="flex items-center justify-between px-3 py-3 border-b border-gray-100 relative">
            <div className="flex items-center gap-3">
              <span className="text-[#ee4d2d] font-bold text-[18px]">Chat</span>
              
              <div className="relative">
                <div 
                  onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                  className={`flex items-center gap-1.5 border rounded-sm px-2 py-1 cursor-pointer transition-colors ${isDropdownOpen ? 'border-[#ee4d2d] bg-gray-50' : 'border-gray-200 hover:bg-gray-50'}`}
                >
                  <span className="text-[12px] text-gray-600">与买家聊...</span>
                  <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full" />
                  <ChevronDown size={14} className="text-gray-400" />
                </div>

                {isDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setIsDropdownOpen(false)} />
                    <div className="absolute top-full left-0 mt-1 bg-white border border-gray-100 shadow-lg rounded-sm py-2 z-20 w-[180px]">
                      <div className="px-3 py-2 hover:bg-gray-50 text-[13px] text-[#ee4d2d] font-medium flex items-center justify-between">
                        与买家聊天 <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full" />
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

          {/* 搜索框 */}
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

          {/* 标签页 (Tabs) */}
          <div className="flex border-b border-gray-200">
            <div 
              onClick={() => setActiveTab('serving')}
              className={`flex-1 flex justify-center items-center py-2.5 cursor-pointer border-b-2 transition-colors ${activeTab === 'serving' ? 'border-[#ee4d2d]' : 'border-transparent hover:bg-gray-50'}`}
            >
              <span className={`text-[13px] font-medium ${activeTab === 'serving' ? 'text-[#ee4d2d]' : 'text-gray-600'}`}>今日接待</span>
              <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full ml-1 mb-2" />
            </div>
            <div 
              onClick={() => setActiveTab('all')}
              className={`flex-1 flex justify-center items-center py-2.5 cursor-pointer border-b-2 transition-colors ${activeTab === 'all' ? 'border-[#ee4d2d]' : 'border-transparent hover:bg-gray-50'}`}
            >
              <span className={`text-[13px] font-medium ${activeTab === 'all' ? 'text-[#ee4d2d]' : 'text-gray-600'}`}>全部聊天</span>
              <div className="w-1.5 h-1.5 bg-[#ee4d2d] rounded-full ml-1 mb-2" />
            </div>
          </div>

          {/* 列表内容区域 */}
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {activeTab === 'serving' ? (
              <div>
                <div 
                  onClick={() => toggleGroup('replied')}
                  className="flex items-center gap-1.5 px-3 py-2.5 text-[13px] text-gray-700 font-medium cursor-pointer hover:bg-gray-50 select-none"
                >
                  {expanded.replied ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <span>已回复 (2)</span>
                </div>
                {expanded.replied && servingChats.map(renderChatItem)}
              </div>
            ) : (
              <div className="flex flex-col">
                <div>
                  <div 
                    onClick={() => toggleGroup('inquiry')}
                    className="flex items-center gap-1.5 px-3 py-2.5 text-[13px] text-gray-700 font-medium cursor-pointer hover:bg-gray-50 select-none"
                  >
                    {expanded.inquiry ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    <span>无订单咨询 (1)</span>
                  </div>
                  {expanded.inquiry && inquiryChats.map(renderChatItem)}
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
                  {expanded.allBuyers && allBuyerChats.map(renderChatItem)}
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}