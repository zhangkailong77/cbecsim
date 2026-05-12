import { useEffect, useState } from 'react';
import {
  HelpCircle,
  ChevronDown,
  ChevronRight,
  PenLine,
  Trash2,
  GripVertical,
  Plus
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface QuickReplySettingsViewProps {
  runId?: number | null;
  readOnly?: boolean;
  onCreateQuickReply: () => void;
  onEditQuickReply: (group: QuickReplyGroup) => void;
}

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

interface QuickReplyListResponse {
  preference: {
    auto_hint_enabled: boolean;
  };
  limits: {
    max_groups: number;
    max_messages_per_group: number;
    max_group_name_length: number;
    max_message_length: number;
    max_tags_per_message: number;
  };
  groups: QuickReplyGroup[];
}

const fallbackData: QuickReplyListResponse = {
  preference: { auto_hint_enabled: true },
  limits: {
    max_groups: 25,
    max_messages_per_group: 20,
    max_group_name_length: 200,
    max_message_length: 500,
    max_tags_per_message: 3,
  },
  groups:[],
};

export default function QuickReplySettingsView({ runId = null, readOnly = false, onCreateQuickReply, onEditQuickReply }: QuickReplySettingsViewProps) {
  const[data, setData] = useState<QuickReplyListResponse>(fallbackData);
  const[expandedGroupIds, setExpandedGroupIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [savingPreference, setSavingPreference] = useState(false);
  const [savingGroupId, setSavingGroupId] = useState<number | null>(null);

  // ================= 拖拽排序相关状态 =================
  const[draggedGroupIndex, setDraggedGroupIndex] = useState<number | null>(null);
  const [draggableGroupId, setDraggableGroupId] = useState<number | null>(null);

  useEffect(() => {
    if (!runId) {
      setData(fallbackData);
      setError('当前没有可用对局，无法加载快捷回复配置。');
      return;
    }

    let cancelled = false;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    setLoading(true);
    setError('');
    fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/quick-replies`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(await response.text());
        return response.json();
      })
      .then((payload: QuickReplyListResponse) => {
        if (cancelled) return;
        setData(payload);
        setExpandedGroupIds(new Set(payload.groups.map((group) => group.id)));
      })
      .catch(() => {
        if (!cancelled) setError('快捷回复配置加载失败，请稍后重试。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  const updatePreference = async (enabled: boolean) => {
    if (readOnly) {
      setError('历史对局仅支持回溯查看，不能修改快捷回复配置。');
      return;
    }
    if (!runId || savingPreference) return;

    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    setSavingPreference(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/quick-replies/preference`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ auto_hint_enabled: enabled }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || '保存快捷回复提示设置失败');
      setData((prev) => ({ ...prev, preference: payload.preference }));
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存快捷回复提示设置失败');
    } finally {
      setSavingPreference(false);
    }
  };

  const refreshData = async () => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/quick-replies`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error(payload?.detail || '快捷回复配置加载失败');
    setData(payload);
    setExpandedGroupIds(new Set(payload.groups.map((group: QuickReplyGroup) => group.id)));
  };

  const updateGroupEnabled = async (groupId: number, enabled: boolean) => {
    if (readOnly) {
      setError('历史对局仅支持回溯查看，不能修改快捷回复配置。');
      return;
    }
    if (!runId || savingGroupId) return;

    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    setSavingGroupId(groupId);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/quick-reply-groups/${groupId}/enabled`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ enabled }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || '保存快捷回复分组状态失败');
      setData((prev) => ({
        ...prev,
        groups: prev.groups.map((group) => group.id === groupId ? payload.group : group),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存快捷回复分组状态失败');
    } finally {
      setSavingGroupId(null);
    }
  };

  const deleteGroup = async (groupId: number) => {
    if (readOnly) {
      setError('历史对局仅支持回溯查看，不能删除快捷回复分组。');
      return;
    }
    if (!runId || savingGroupId) return;
    if (!window.confirm('确定删除这个快捷回复分组吗？删除后不可恢复。')) return;

    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    setSavingGroupId(groupId);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/quick-reply-groups/${groupId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || '删除快捷回复分组失败');
      }
      await refreshData();
      setExpandedGroupIds((prev) => {
        const next = new Set(prev);
        next.delete(groupId);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除快捷回复分组失败');
    } finally {
      setSavingGroupId(null);
    }
  };

  // ================= 前端拖拽排序方法 =================
  const syncGroupOrderToServer = async (groups: QuickReplyGroup[]) => {
    if (!runId || readOnly) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/quick-reply-groups/reorder`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ group_ids: groups.map((group) => group.id) }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || '保存快捷回复分组排序失败');
      setData(payload);
      setExpandedGroupIds(new Set(payload.groups.map((group: QuickReplyGroup) => group.id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存快捷回复分组排序失败');
      void refreshData();
    }
  };

  const handleDragStart = (e: React.DragEvent<HTMLDivElement>, index: number) => {
    if (controlDisabled || readOnly) return;
    setDraggedGroupIndex(index);
    setTimeout(() => {
       if (e.target instanceof HTMLElement) {
          e.target.classList.add('opacity-40');
       }
    }, 0);
  };

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>, index: number) => {
    e.preventDefault();
    if (controlDisabled || readOnly || draggedGroupIndex === null || draggedGroupIndex === index) return;

    // 前端实时交换数组顺序
    setData((prev) => {
      const newGroups = [...prev.groups];
      const draggedItem = newGroups[draggedGroupIndex];
      newGroups.splice(draggedGroupIndex, 1);
      newGroups.splice(index, 0, draggedItem);
      return { ...prev, groups: newGroups };
    });
    setDraggedGroupIndex(index);
  };

  const handleDragEnd = (e: React.DragEvent<HTMLDivElement>) => {
    setDraggedGroupIndex(null);
    setDraggableGroupId(null); // 拖拽结束恢复不可拖拽状态
    if (e.target instanceof HTMLElement) {
       e.target.classList.remove('opacity-40');
    }
    void syncGroupOrderToServer(data.groups);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };
  // =================================================

  const toggleGroupExpanded = (groupId: number) => {
    setExpandedGroupIds((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  };

  const ToggleSwitch = ({ enabled, disabled, onChange }: { enabled: boolean; disabled?: boolean; onChange: () => void }) => (
    <div
      onClick={(e) => {
        e.stopPropagation();
        if (!disabled) onChange();
      }}
      className={`w-[44px] h-[24px] rounded-full relative transition-colors duration-200 ease-in-out flex-shrink-0 ${
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
      } ${enabled ? 'bg-[#26aa99]' : 'bg-[#e5e5e5]'}`}
    >
      <div
        className={`absolute top-[2px] w-[20px] h-[20px] bg-white rounded-full shadow-sm transition-transform duration-200 ease-in-out ${
          enabled ? 'translate-x-[22px]' : 'translate-x-[2px]'
        }`}
      />
    </div>
  );

  const controlDisabled = loading || !runId;

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333]">
      <div className="mx-auto w-[1360px] max-w-full flex flex-col gap-5">
        {readOnly && (
          <div className="border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700 shrink-0">
            当前为历史对局回溯模式：可浏览快捷回复配置，但无法修改。
          </div>
        )}
        {error && (
          <div className="border border-red-100 bg-red-50 px-4 py-2 text-[13px] text-red-600 shrink-0">
            {error}
          </div>
        )}

        <div className="w-full bg-white rounded shadow-sm border border-gray-200 px-6 py-5 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-1.5 mb-1">
              <h2 className="text-[18px] font-medium text-gray-800">自动显示消息提示</h2>
              <HelpCircle size={15} className="text-gray-400 cursor-pointer hover:text-gray-600" />
            </div>
            <p className="text-[14px] text-gray-500">开启后，在输入时会自动检索并弹出相关的快捷回复提示。</p>
          </div>
          <ToggleSwitch
            enabled={data.preference.auto_hint_enabled}
            disabled={controlDisabled || readOnly || savingPreference}
            onChange={() => updatePreference(!data.preference.auto_hint_enabled)}
          />
        </div>

        <div className="w-full bg-white rounded shadow-sm border border-gray-200 px-6 py-6 flex flex-col">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h2 className="text-[18px] font-medium text-gray-800 mb-1">我的快捷回复 ({data.groups.length}/{data.limits.max_groups})</h2>
              <p className="text-[14px] text-gray-500">快捷回复允许您为常用消息创建模板，提高回复效率。</p>
            </div>
            <button
              type="button"
              onClick={onCreateQuickReply}
              disabled={readOnly || !runId}
              className="flex items-center gap-1.5 bg-[#ee4d2d] text-white px-4 py-2 rounded text-[14px] font-medium hover:bg-[#d73f22] transition-colors shadow-sm disabled:bg-[#f4a592] disabled:cursor-not-allowed"
            >
              <Plus size={16} />
              新建快捷回复
            </button>
          </div>

          <div className="flex flex-col">
            {data.groups.length === 0 ? (
              <div className="border border-gray-200 rounded px-5 py-10 text-center text-[14px] text-gray-400">
                暂无快捷回复分组
              </div>
            ) : data.groups.map((group, index) => {
              const isExpanded = expandedGroupIds.has(group.id);
              return (
                <div 
                  key={group.id} 
                  className="mb-3 last:mb-0 transition-transform"
                  // 只有当鼠标放到拖拽图标上时，这行才允许被拖拽
                  draggable={draggableGroupId === group.id}
                  onDragStart={(e) => handleDragStart(e, index)}
                  onDragEnter={(e) => handleDragEnter(e, index)}
                  onDragEnd={handleDragEnd}
                  onDragOver={handleDragOver}
                >
                  <div
                    onClick={() => toggleGroupExpanded(group.id)}
                    className={`w-full bg-[#fafafa] border border-gray-200 px-4 py-3 flex justify-between items-center cursor-pointer select-none ${
                      isExpanded ? 'rounded-t border-b-0' : 'rounded'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown size={18} className="text-gray-600" />
                      ) : (
                        <ChevronRight size={18} className="text-gray-600" />
                      )}
                      <span className="text-[14px] text-gray-800 font-medium">{group.group_name}</span>
                    </div>

                    <div className="flex items-center gap-4" onClick={(e) => e.stopPropagation()}>
                      <ToggleSwitch
                        enabled={group.enabled}
                        disabled={controlDisabled || readOnly || savingGroupId === group.id}
                        onChange={() => updateGroupEnabled(group.id, !group.enabled)}
                      />
                      <div className="w-px h-4 bg-gray-300 mx-1"></div>
                      <button
                        type="button"
                        onClick={() => onEditQuickReply(group)}
                        disabled={controlDisabled || readOnly || savingGroupId === group.id}
                        className="text-gray-500 hover:text-[#ee4d2d] transition-colors disabled:text-gray-300 disabled:cursor-not-allowed"
                        title="编辑"
                      >
                        <PenLine size={16} />
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteGroup(group.id)}
                        disabled={controlDisabled || readOnly || savingGroupId === group.id}
                        className="text-gray-500 hover:text-[#ee4d2d] transition-colors disabled:text-gray-300 disabled:cursor-not-allowed"
                        title="删除"
                      >
                        <Trash2 size={16} />
                      </button>
                      
                      {/* 只有鼠标在这个图标上时，激活拖拽 */}
                      <div 
                        className={`text-gray-400 hover:text-gray-600 transition-colors ${
                          controlDisabled || readOnly || savingGroupId === group.id ? 'opacity-50 cursor-not-allowed' : 'cursor-grab active:cursor-grabbing'
                        }`} 
                        title="按住拖拽排序"
                        onMouseEnter={() => {
                          if (!controlDisabled && !readOnly && savingGroupId !== group.id) {
                            setDraggableGroupId(group.id);
                          }
                        }}
                        onMouseLeave={() => setDraggableGroupId(null)}
                      >
                        <GripVertical size={16} />
                      </div>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="w-full border border-gray-200 rounded-b bg-white">
                      {group.messages.map((item, index) => (
                        <div
                          key={item.id}
                          className={`px-5 py-4 text-[13px] text-gray-700 hover:bg-gray-50 transition-colors ${
                            index !== group.messages.length - 1 ? 'border-b border-gray-100' : ''
                          }`}
                        >
                          {item.message}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}