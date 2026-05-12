import { useEffect, useState, type DragEvent } from 'react';
import { HelpCircle, Trash2, GripVertical, Plus, X } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface QuickReplyMessage {
  id: number;
  message: string;
  tags: string[];
  sort_order: number;
}

interface QuickReplyGroup {
  id: number;
  group_name: string;
  enabled: boolean;
  sort_order: number;
  message_count: number;
  messages: QuickReplyMessage[];
}

interface QuickReplyCreateViewProps {
  runId?: number | null;
  readOnly?: boolean;
  editingGroup?: QuickReplyGroup | null;
  onBackToQuickReply: () => void;
}

interface QuickReplyDraftMessage {
  id: number;
  text: string;
  tags: string;
}

const MAX_MESSAGES = 20;
const MAX_GROUP_NAME_LENGTH = 200;
const MAX_MESSAGE_LENGTH = 500;
const MAX_TAGS = 3;

export default function QuickReplyCreateView({ runId = null, readOnly = false, editingGroup = null, onBackToQuickReply }: QuickReplyCreateViewProps) {
  const [groupName, setGroupName] = useState(editingGroup?.group_name ?? '');
  const [messages, setMessages] = useState<QuickReplyDraftMessage[]>(() => (editingGroup?.messages ?? []).map((item) => ({
    id: item.id,
    text: item.message,
    tags: item.tags.join('\n'),
  })));
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [draggableRowId, setDraggableRowId] = useState<number | null>(null);

  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false);
  const [activeTemplateTab, setActiveTemplateTab] = useState('通用');
  const [selectedTemplates, setSelectedTemplates] = useState<string[]>([]);

  const remainingSlots = MAX_MESSAGES - messages.length;
  const writeDisabled = readOnly || !runId || saving;

  const templateTabs = ['通用', '订单', '物流', '售后服务'];
  const mockTemplatesData: Record<string, {id: string, text: string, tag: string}[]> = {
    '通用': [
      { id: 'c1', text: '您好，测试消息', tag: 'welcome' },
      { id: 'c2', text: '感谢您的咨询，客服目前较忙，我们会尽快回复您。感谢您的耐心等待。', tag: 'delay reply' },
      { id: 'c3', text: '如果您还有任何问题，请随时联系我们，谢谢。祝您有美好的一天。', tag: 'end chat' },
      { id: 'c4', text: '您好，请问您对这款商品感兴趣吗？目前有现货哦！', tag: 'available' },
      { id: 'c5', text: '感谢您对本店的关注。非常抱歉地通知您，您咨询的商品目前暂时缺货。', tag: 'not available' },
    ],
    '订单': [
      { id: 'o1', text: '您的订单已确认，我们将尽快为您安排发货，请耐心等待。', tag: 'order confirmed' },
      { id: 'o2', text: '非常抱歉，您订购的商品目前缺货，请问是否愿意更换其他颜色/款式？', tag: 'change item' },
    ],
    '物流': [
      { id: 'l1', text: '您的包裹已经发出，您可以随时在订单页面查看最新的物流动态。', tag: 'shipped' },
      { id: 'l2', text: '物流显示您的包裹已派送，麻烦您注意查收。如果未收到，请联系我们。', tag: 'delivered' },
    ],
    '售后服务': [
      { id: 'a1', text: '如果您对收到的商品不满意，支持7天无理由退换货，请保持商品及包装完好。', tag: 'return policy' },
      { id: 'a2', text: '您的退款申请已通过，款项将按原支付路径退回，请您注意查收账户。', tag: 'refund issued' },
    ]
  };

  const currentTabTemplates = mockTemplatesData[activeTemplateTab] || [];
  const isEditing = Boolean(editingGroup);

  useEffect(() => {
    setGroupName(editingGroup?.group_name ?? '');
    setMessages((editingGroup?.messages ?? []).map((item) => ({
      id: item.id,
      text: item.message,
      tags: item.tags.join('\n'),
    })));
  }, [editingGroup]);

  const parseTags = (raw: string) => raw
    .split(/[\n,，]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
    .slice(0, MAX_TAGS);

  const handleAddMessage = () => {
    if (writeDisabled || messages.length >= MAX_MESSAGES) return;
    setMessages([...messages, { id: Date.now(), text: '', tags: '' }]);
  };

  const handleDeleteMessage = (idToRemove: number) => {
    if (writeDisabled) return;
    setMessages(messages.filter(msg => msg.id !== idToRemove));
  };

  const handleTextChange = (id: number, newText: string) => {
    setMessages(messages.map(msg =>
      msg.id === id ? { ...msg, text: newText } : msg
    ));
  };

  const handleTagsChange = (id: number, newTags: string) => {
    setMessages(messages.map(msg =>
      msg.id === id ? { ...msg, tags: newTags } : msg
    ));
  };

  const handleDragStart = (e: DragEvent<HTMLDivElement>, index: number) => {
    if (writeDisabled) return;
    setDraggedIndex(index);
    setTimeout(() => {
       if (e.target instanceof HTMLElement) {
          e.target.classList.add('opacity-40', 'bg-gray-50');
       }
    }, 0);
  };

  const handleDragEnter = (e: DragEvent<HTMLDivElement>, index: number) => {
    e.preventDefault();
    if (writeDisabled || draggedIndex === null || draggedIndex === index) return;

    const newMessages = [...messages];
    const draggedItem = newMessages[draggedIndex];

    newMessages.splice(draggedIndex, 1);
    newMessages.splice(index, 0, draggedItem);

    setDraggedIndex(index);
    setMessages(newMessages);
  };

  const handleDragEnd = (e: DragEvent<HTMLDivElement>) => {
    setDraggedIndex(null);
    setDraggableRowId(null);
    if (e.target instanceof HTMLElement) {
       e.target.classList.remove('opacity-40', 'bg-gray-50');
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const toggleTemplateSelection = (templateId: string) => {
    if (writeDisabled) return;
    if (selectedTemplates.includes(templateId)) {
      setSelectedTemplates(prev => prev.filter(id => id !== templateId));
    } else {
      if (selectedTemplates.length >= remainingSlots) return;
      setSelectedTemplates(prev => [...prev, templateId]);
    }
  };

  const toggleAllInCurrentTab = () => {
    if (writeDisabled) return;
    const currentTabIds = currentTabTemplates.map(t => t.id);
    const isAllSelectedInTab = currentTabIds.length > 0 && currentTabIds.every(id => selectedTemplates.includes(id));

    if (isAllSelectedInTab) {
      setSelectedTemplates(prev => prev.filter(id => !currentTabIds.includes(id)));
    } else {
      const availableSpace = remainingSlots - selectedTemplates.length;
      if (availableSpace <= 0) return;
      const unselectedIds = currentTabIds.filter(id => !selectedTemplates.includes(id));
      const idsToAdd = unselectedIds.slice(0, availableSpace);
      setSelectedTemplates(prev => [...prev, ...idsToAdd]);
    }
  };

  const handleConfirmTemplates = () => {
    if (writeDisabled || selectedTemplates.length === 0) return;
    const allTemplates = Object.values(mockTemplatesData).flat();
    const templatesToAdd = allTemplates.filter(t => selectedTemplates.includes(t.id));

    const newMessages = templatesToAdd.map((t, index) => ({
      id: Date.now() + index,
      text: t.text,
      tags: t.tag
    }));

    const combinedMessages = [...messages, ...newMessages].slice(0, MAX_MESSAGES);
    setMessages(combinedMessages);
    setIsTemplateModalOpen(false);
    setSelectedTemplates([]);
  };

  const handleSave = async () => {
    if (readOnly) {
      setError(`历史对局仅支持回溯查看，不能${isEditing ? '编辑' : '创建'}快捷回复。`);
      return;
    }
    if (!runId || saving) return;

    const trimmedGroupName = groupName.trim();
    const payloadMessages = messages
      .map((msg) => ({ message: msg.text.trim(), tags: parseTags(msg.tags) }))
      .filter((msg) => msg.message.length > 0);

    if (!trimmedGroupName) {
      setError('请输入分组名称。');
      return;
    }
    if (payloadMessages.length === 0) {
      setError('请至少添加一条快捷回复消息。');
      return;
    }

    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    setSaving(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/quick-reply-groups${editingGroup ? `/${editingGroup.id}` : ''}`, {
        method: editingGroup ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          group_name: trimmedGroupName,
          enabled: editingGroup?.enabled ?? true,
          messages: payloadMessages,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || `${isEditing ? '编辑' : '创建'}快捷回复失败`);
      onBackToQuickReply();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${isEditing ? '编辑' : '创建'}快捷回复失败`);
    } finally {
      setSaving(false);
    }
  };

  const isAllSelectedInCurrentTab = currentTabTemplates.length > 0 && currentTabTemplates.every(t => selectedTemplates.includes(t.id));
  const saveDisabled = writeDisabled || groupName.trim().length === 0 || messages.length === 0;

  const ActionButtons = () => (
    <>
      <button
        type="button"
        onClick={handleAddMessage}
        disabled={writeDisabled || messages.length >= MAX_MESSAGES}
        className={`flex-1 border border-dashed rounded-sm py-2.5 flex items-center justify-center gap-2 text-[13px] font-medium transition-colors
          ${writeDisabled || messages.length >= MAX_MESSAGES
            ? 'border-gray-300 text-gray-400 bg-gray-50 cursor-not-allowed'
            : 'border-[#2673dd] text-[#2673dd] bg-white hover:bg-[#eff6ff]'
          }
        `}
      >
        <Plus size={16} />
        添加消息 ({messages.length}/{MAX_MESSAGES})
      </button>

      <button
        type="button"
        onClick={() => setIsTemplateModalOpen(true)}
        disabled={writeDisabled || messages.length >= MAX_MESSAGES}
        className={`flex-1 border border-dashed rounded-sm py-2.5 flex items-center justify-center gap-2 text-[13px] font-medium transition-colors
          ${writeDisabled || messages.length >= MAX_MESSAGES
            ? 'border-gray-300 text-gray-400 bg-gray-50 cursor-not-allowed'
            : 'border-[#2673dd] text-[#2673dd] bg-white hover:bg-[#eff6ff]'
          }
        `}
      >
        <Plus size={16} />
        从模板添加消息
      </button>
    </>
  );

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333] relative">
      <div className="mx-auto w-[1360px] max-w-full flex flex-col gap-4">
        {readOnly && (
          <div className="border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700 shrink-0">
            当前为历史对局回溯模式：可浏览快捷回复{isEditing ? '编辑' : '创建'}页，但无法保存。
          </div>
        )}
        {error && (
          <div className="border border-red-100 bg-red-50 px-4 py-2 text-[13px] text-red-600 shrink-0">
            {error}
          </div>
        )}

        <div className="w-full bg-white rounded shadow-sm border border-gray-200 p-8 flex flex-col gap-8">
          <h2 className="text-[20px] font-medium text-gray-800">{isEditing ? '编辑个人快捷回复' : '创建个人快捷回复'}</h2>

          <div className="flex items-start">
            <div className="w-[180px] pt-2 text-[14px] text-gray-800 font-medium">分组名称</div>
            <div className="flex-1 relative">
              <input
                type="text"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value.slice(0, MAX_GROUP_NAME_LENGTH))}
                maxLength={MAX_GROUP_NAME_LENGTH}
                disabled={writeDisabled}
                placeholder="输入分组名称"
                className="w-full border border-gray-200 rounded px-4 py-2 text-[14px] placeholder:text-gray-400 focus:border-[#ee4d2d] focus:outline-none transition-colors pr-16 disabled:bg-gray-50 disabled:cursor-not-allowed"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[12px] text-gray-400">{groupName.length}/{MAX_GROUP_NAME_LENGTH}</span>
            </div>
          </div>

          <div className="flex items-start">
            <div className="w-[180px] pt-2 text-[14px] text-gray-800 font-medium">快捷回复消息</div>

            {messages.length === 0 ? (
              <div className="flex-1 flex gap-4 h-fit">
                <ActionButtons />
              </div>
            ) : (
              <div className="flex-1 border border-gray-200 rounded-sm flex flex-col">
                <div className="flex items-center bg-[#fafafa] border-b border-gray-200 px-4 py-3 text-[13px] text-gray-500">
                  <div className="w-10">编号</div>
                  <div className="flex-1">消息内容</div>
                  <div className="w-[300px] flex items-center gap-1">标签 <HelpCircle size={14} className="cursor-pointer hover:text-gray-700"/></div>
                  <div className="w-16 text-center">操作</div>
                </div>

                {messages.map((msg, index) => (
                  <div
                    key={msg.id}
                    draggable={!writeDisabled && draggableRowId === msg.id}
                    onDragStart={(e) => handleDragStart(e, index)}
                    onDragEnter={(e) => handleDragEnter(e, index)}
                    onDragEnd={handleDragEnd}
                    onDragOver={handleDragOver}
                    className="flex items-start p-4 bg-white relative border-b border-gray-50 last:border-b-0 transition-transform"
                  >
                    <div className="w-10 pt-3 text-[14px] text-gray-800">{index + 1}</div>

                    <div className="flex-1 flex flex-col mr-4">
                      <textarea
                        value={msg.text}
                        onChange={(e) => handleTextChange(msg.id, e.target.value)}
                        maxLength={MAX_MESSAGE_LENGTH}
                        disabled={writeDisabled}
                        placeholder="添加消息"
                        className="w-full h-[90px] border border-gray-200 rounded p-3 text-[14px] placeholder:text-gray-300 resize-none focus:border-[#ee4d2d] focus:outline-none transition-colors disabled:bg-gray-50 disabled:cursor-not-allowed"
                      ></textarea>
                      <span className="text-[12px] text-gray-400 text-right mt-1">{msg.text.length}/{MAX_MESSAGE_LENGTH}</span>
                    </div>

                    <div className="w-[300px] flex flex-col mr-4">
                      <textarea
                         value={msg.tags}
                         onChange={(e) => handleTagsChange(msg.id, e.target.value)}
                         disabled={writeDisabled}
                         placeholder="按回车键创建新标签，或使用现有标签"
                         className="w-full h-[90px] border border-gray-200 rounded p-3 text-[14px] placeholder:text-gray-300 resize-none focus:border-[#ee4d2d] focus:outline-none transition-colors bg-white disabled:bg-gray-50 disabled:cursor-not-allowed"
                      ></textarea>
                      <span className="text-[12px] text-gray-400 text-right mt-1">{parseTags(msg.tags).length}/{MAX_TAGS}</span>
                    </div>

                    <div className="w-16 flex items-start justify-center gap-3 pt-3 text-[#2673dd]">
                      <button type="button" onClick={() => handleDeleteMessage(msg.id)} disabled={writeDisabled} className="hover:opacity-70 cursor-pointer transition-opacity disabled:cursor-not-allowed disabled:text-gray-300" title="删除">
                        <Trash2 size={16} />
                      </button>

                      <div
                        className={`text-gray-400 hover:text-gray-600 transition-colors ${writeDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-grab active:cursor-grabbing'}`}
                        title="按住拖拽排序"
                        onMouseEnter={() => {
                          if (!writeDisabled) setDraggableRowId(msg.id);
                        }}
                        onMouseLeave={() => setDraggableRowId(null)}
                      >
                        <GripVertical size={16} />
                      </div>
                    </div>
                  </div>
                ))}

                <div className="px-4 pb-4 pt-4 flex gap-4 border-t border-gray-100 bg-[#fafafa]">
                  <ActionButtons />
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="w-full bg-white rounded shadow-sm border border-gray-200 px-8 py-4 flex justify-end gap-3">
           <button type="button" onClick={onBackToQuickReply} className="px-6 py-2 border border-gray-300 rounded-sm text-[14px] text-gray-700 font-medium hover:bg-gray-50 transition-colors">取消</button>
           <button
              type="button"
              onClick={handleSave}
              disabled={saveDisabled}
              className={`px-6 py-2 rounded-sm text-[14px] font-medium transition-colors ${
                saveDisabled ? 'bg-[#f4a592] text-white cursor-not-allowed' : 'bg-[#ee4d2d] text-white hover:bg-[#d73f22]'
              }`}
            >
             {saving ? '保存中...' : '保存'}
           </button>
        </div>
      </div>

      {isTemplateModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center animate-in fade-in duration-200">
          <div className="bg-white rounded shadow-xl w-[880px] max-h-[85vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center px-6 py-4 border-b border-gray-100 flex-shrink-0">
              <h2 className="text-[18px] font-medium text-gray-800">从模板添加消息</h2>
              <button type="button" onClick={() => setIsTemplateModalOpen(false)} className="text-gray-400 hover:text-gray-600 transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="flex px-6 border-b border-gray-100 flex-shrink-0">
              {templateTabs.map(tab => (
                <div
                  key={tab}
                  onClick={() => setActiveTemplateTab(tab)}
                  className={`py-3 px-4 text-[14px] cursor-pointer font-medium border-b-2 transition-colors ${
                    activeTemplateTab === tab ? 'text-[#ee4d2d] border-[#ee4d2d]' : 'text-gray-600 border-transparent hover:text-[#ee4d2d]'
                  }`}
                >
                  {tab}
                </div>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-2 custom-scrollbar bg-white">
              <div className="sticky top-0 bg-[#fafafa] flex items-center gap-3 px-4 py-3 rounded-t-sm z-10 border border-gray-100">
                <input
                  type="checkbox"
                  checked={isAllSelectedInCurrentTab}
                  onChange={toggleAllInCurrentTab}
                  disabled={writeDisabled || remainingSlots <= 0}
                  className="w-4 h-4 rounded border-gray-300 text-[#ee4d2d] focus:ring-[#ee4d2d] cursor-pointer accent-[#ee4d2d] disabled:cursor-not-allowed disabled:opacity-50"
                />
                <span className="text-[14px] text-gray-500">快捷回复消息</span>
              </div>

              <div className="border border-t-0 border-gray-100 rounded-b-sm min-h-[300px]">
                {currentTabTemplates.length > 0 ? (
                  currentTabTemplates.map((template) => {
                    const isSelected = selectedTemplates.includes(template.id);
                    const isDisabled = !isSelected && selectedTemplates.length >= remainingSlots;

                    return (
                      <label
                        key={template.id}
                        className={`flex items-start gap-4 px-4 py-4 border-b border-gray-100 last:border-b-0 transition-colors
                          ${writeDisabled || isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-50 cursor-pointer'}
                        `}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={writeDisabled || isDisabled}
                          onChange={() => toggleTemplateSelection(template.id)}
                          className="w-4 h-4 mt-1 rounded border-gray-300 text-[#ee4d2d] focus:ring-[#ee4d2d] cursor-pointer accent-[#ee4d2d] flex-shrink-0 disabled:cursor-not-allowed"
                        />
                        <div className="flex flex-col gap-2">
                          <span className="text-[14px] text-gray-700 leading-relaxed">{template.text}</span>
                          <div>
                            <span className="inline-block border border-gray-200 rounded px-2 py-0.5 text-[12px] text-gray-500 bg-white">
                              {template.tag}
                            </span>
                          </div>
                        </div>
                      </label>
                    );
                  })
                ) : (
                  <div className="flex items-center justify-center h-full py-20 text-gray-400 text-[14px]">
                    暂无模板数据
                  </div>
                )}
              </div>
            </div>

            <div className="px-6 py-4 bg-white border-t border-gray-100 flex justify-between items-center flex-shrink-0">
              <span className="text-[13px] text-gray-600">
                已选模板: {selectedTemplates.length} / {remainingSlots}
              </span>
              <div className="flex items-center gap-3">
                <button type="button" onClick={() => setIsTemplateModalOpen(false)} className="px-6 py-2 border border-gray-300 rounded-sm text-[14px] text-gray-700 font-medium hover:bg-gray-50 transition-colors">
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleConfirmTemplates}
                  disabled={writeDisabled || selectedTemplates.length === 0}
                  className={`px-8 py-2 rounded-sm text-[14px] font-medium transition-colors ${
                    !writeDisabled && selectedTemplates.length > 0
                      ? 'bg-[#ee4d2d] text-white hover:bg-[#d73f22] shadow-sm'
                      : 'bg-[#f4a592] text-white cursor-not-allowed'
                  }`}
                >
                  确认
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
