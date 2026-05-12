import { useEffect, useState } from 'react';
import { Info, X, PenLine } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type AutoReplyType = 'default' | 'off_work';

interface AutoReplySetting {
  id: number | null;
  reply_type: AutoReplyType;
  enabled: boolean;
  message: string;
  work_time_enabled: boolean;
  work_start_time?: string | null;
  work_end_time?: string | null;
  trigger_interval_minutes: number;
  trigger_once_per_game_day: boolean;
  status: string;
}

interface AutoReplySettingsResponse {
  default_reply: AutoReplySetting;
  off_work_reply: AutoReplySetting;
  rules: {
    max_message_length: number;
    default_reply_interval_minutes: number;
    off_work_once_per_game_day: boolean;
  };
}

interface AutoReplySettingsViewProps {
  runId?: number | null;
  readOnly?: boolean;
}

const fallbackData: AutoReplySettingsResponse = {
  default_reply: {
    id: null,
    reply_type: 'default',
    enabled: false,
    message: '您好，欢迎光临本店！请问有什么可以帮您？',
    work_time_enabled: false,
    trigger_interval_minutes: 1440,
    trigger_once_per_game_day: false,
    status: 'disabled',
  },
  off_work_reply: {
    id: null,
    reply_type: 'off_work',
    enabled: false,
    message: '亲爱的买家，您的消息已收到。由于目前是非工作时间，我们暂时无法回复您。我们一上线就会立即回复您。感谢您的理解。',
    work_time_enabled: true,
    work_start_time: '09:00',
    work_end_time: '18:00',
    trigger_interval_minutes: 1440,
    trigger_once_per_game_day: true,
    status: 'disabled',
  },
  rules: {
    max_message_length: 500,
    default_reply_interval_minutes: 1440,
    off_work_once_per_game_day: true,
  },
};

export default function AutoReplySettingsView({ runId = null, readOnly = false }: AutoReplySettingsViewProps) {
  const [isBannerVisible, setIsBannerVisible] = useState(true);
  const [data, setData] = useState<AutoReplySettingsResponse>(fallbackData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [savingType, setSavingType] = useState<AutoReplyType | null>(null);

  useEffect(() => {
    if (!runId) {
      setData(fallbackData);
      setError('当前没有可用对局，无法加载自动回复配置。');
      return;
    }

    let cancelled = false;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    setLoading(true);
    setError('');
    fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/auto-replies`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (response) => {
        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || '加载自动回复配置失败');
        }
        return response.json();
      })
      .then((payload: AutoReplySettingsResponse) => {
        if (!cancelled) setData(payload);
      })
      .catch(() => {
        if (!cancelled) setError('自动回复配置加载失败，请稍后重试。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  const updateReplyEnabled = async (replyType: AutoReplyType, enabled: boolean) => {
    if (readOnly) {
      setError('历史对局仅支持回溯查看，不能修改自动回复配置。');
      return;
    }
    if (!runId || savingType) return;

    const currentSetting = replyType === 'default' ? data.default_reply : data.off_work_reply;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    setSavingType(replyType);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/customer-service/auto-replies/${replyType}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          enabled,
          message: currentSetting.message,
          work_start_time: currentSetting.work_start_time,
          work_end_time: currentSetting.work_end_time,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || '保存自动回复配置失败');

      setData((prev) => ({
        ...prev,
        [replyType === 'default' ? 'default_reply' : 'off_work_reply']: payload.setting,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存自动回复配置失败');
    } finally {
      setSavingType(null);
    }
  };

  const ToggleSwitch = ({ enabled, disabled, onChange }: { enabled: boolean; disabled?: boolean; onChange: () => void }) => (
    <div
      onClick={disabled ? undefined : onChange}
      className={`w-[44px] h-[24px] rounded-full relative transition-colors duration-200 ease-in-out ${
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

  const controlDisabled = loading || Boolean(savingType) || !runId;
  const defaultReply = data.default_reply;
  const offWorkReply = data.off_work_reply;

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333]">
      <div className="mx-auto w-[1360px] max-w-full flex flex-col gap-5">
        {readOnly && (
          <div className="border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700 shrink-0">
            当前为历史对局回溯模式：可浏览自动回复配置，但无法修改。
          </div>
        )}

        {error && (
          <div className="border border-red-100 bg-red-50 px-4 py-2 text-[13px] text-red-600 shrink-0">
            {error}
          </div>
        )}

        {isBannerVisible && (
          <div className="w-full bg-[#fffdf2] border border-[#ffdfb3] rounded px-5 py-4 flex items-start gap-3 relative shadow-sm">
            <Info size={16} className="text-[#ff9800] mt-0.5 flex-shrink-0" />
            <div className="text-[14px] text-gray-600 leading-relaxed">
              <p>1. 默认自动回复对每个买家每 24 小时只触发一次。</p>
              <p>2. 离线自动回复对每个买家每天只触发一次。</p>
            </div>
            <button
              onClick={() => setIsBannerVisible(false)}
              className="absolute right-4 top-4 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        )}

        <div className="w-full bg-white rounded shadow-sm border border-gray-200 p-6 flex flex-col gap-4">
          <div>
            <h2 className="text-[18px] font-medium text-gray-800 mb-1">默认自动回复</h2>
            <p className="text-[14px] text-gray-500">开启后，此自动回复将在买家发起对话时发送一次。</p>
          </div>

          <div className="w-full bg-[#fcfcfc] border border-gray-200 rounded px-6 py-5 flex justify-between items-center">
            <span className="text-[14px] text-gray-800 font-medium">店铺设置</span>
            <div className="flex items-center gap-6">
              <ToggleSwitch
                enabled={defaultReply.enabled}
                disabled={controlDisabled || readOnly}
                onChange={() => updateReplyEnabled('default', !defaultReply.enabled)}
              />
              <button disabled={readOnly || loading} className="text-gray-400 hover:text-[#ee4d2d] transition-colors disabled:cursor-not-allowed disabled:opacity-50" title="编辑">
                <PenLine size={18} />
              </button>
            </div>
          </div>
        </div>

        <div className="w-full bg-white rounded shadow-sm border border-gray-200 p-6 flex flex-col gap-4">
          <div>
            <h2 className="text-[18px] font-medium text-gray-800 mb-1">离线自动回复</h2>
            <p className="text-[14px] text-gray-500">开启后，如果在工作时间外买家发起对话，将发送此自动回复消息。</p>
          </div>

          <div className="w-full flex flex-col">
            <div className="w-full bg-[#fcfcfc] border border-gray-200 border-b-0 rounded-t px-6 py-5 flex justify-between items-center">
              <span className="text-[14px] text-gray-800 font-medium">店铺设置</span>
              <div className="flex items-center gap-6">
                <ToggleSwitch
                  enabled={offWorkReply.enabled}
                  disabled={controlDisabled || readOnly}
                  onChange={() => updateReplyEnabled('off_work', !offWorkReply.enabled)}
                />
                <button disabled={readOnly || loading} className="text-gray-400 hover:text-[#ee4d2d] transition-colors disabled:cursor-not-allowed disabled:opacity-50" title="编辑">
                  <PenLine size={18} />
                </button>
              </div>
            </div>

            <div className="w-full bg-white border border-gray-200 rounded-b px-6 py-5">
              <p className="text-[14px] text-gray-500 leading-relaxed">
                {offWorkReply.message}
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
