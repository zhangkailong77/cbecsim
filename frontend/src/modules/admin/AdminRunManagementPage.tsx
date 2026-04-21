import { useEffect, useMemo, useState } from 'react';
import { CalendarClock, RefreshCw, ShieldCheck } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface AdminRunOption {
  run_id: number;
  user_id: number;
  username: string;
  status: string;
  market: string;
  day_index: number;
  duration_days: number;
  base_real_duration_days: number;
  base_game_days: number;
  total_game_days: number;
  created_at: string;
  manual_end_time: string | null;
  end_time: string;
}

interface AdminRunOptionsResponse {
  runs: AdminRunOption[];
}

interface ExtendRunResponse {
  run_id: number;
  old_duration_days: number;
  new_duration_days: number;
  old_total_game_days: number;
  new_total_game_days: number;
  new_end_time: string;
  status: string;
}

interface RenewRunResponse {
  run_id: number;
  old_status: string;
  new_status: string;
  old_total_game_days: number;
  new_total_game_days: number;
  manual_end_time: string | null;
  new_end_time: string;
}

interface AdminRunManagementPageProps {
  currentUser: {
    username: string;
    full_name: string | null;
  } | null;
  onBackToSetup?: () => void;
  embedded?: boolean;
  onRunContextChange?: (context: {
    runId: number | null;
    username: string | null;
    status: string | null;
    market: string | null;
    dayIndex: number | null;
    createdAt: string | null;
    durationDays: number | null;
    baseRealDurationDays: number | null;
    baseGameDays: number | null;
    totalGameDays: number | null;
    manualEndTime: string | null;
    endTime: string | null;
    gameClock: string | null;
  }) => void;
}

function fmtDurationSeconds(totalSeconds: number) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const min = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${d}天 ${h}小时 ${min}分钟 ${sec}秒`;
}

function parseServerDateMs(value: string | null | undefined) {
  if (!value) return NaN;
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/.test(value);
  const normalized = hasTimezone ? value : `${value}Z`;
  return new Date(normalized).getTime();
}

function getRunRemainingSeconds(run: AdminRunOption, nowMs: number) {
  if (run.status !== 'running') return 0;
  const endMs = parseServerDateMs(run.end_time);
  if (!Number.isFinite(endMs)) return 0;
  return Math.max(0, Math.floor((endMs - nowMs) / 1000));
}

function getRunStatusTone(status: string) {
  return status === 'finished'
    ? 'bg-slate-100 text-slate-700'
    : 'bg-emerald-50 text-emerald-700';
}

export default function AdminRunManagementPage({
  currentUser,
  onBackToSetup,
  embedded = false,
  onRunContextChange,
}: AdminRunManagementPageProps) {
  const [runs, setRuns] = useState<AdminRunOption[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [customDays, setCustomDays] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(false);
  const [refreshTs, setRefreshTs] = useState<number>(Date.now());
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [submittingRunId, setSubmittingRunId] = useState<number | null>(null);
  const [nowMs, setNowMs] = useState<number>(Date.now());
  const [usernameKeyword, setUsernameKeyword] = useState('');

  const displayName = currentUser?.full_name?.trim() || currentUser?.username || '超级管理员';

  const loadRuns = async (preferredRunId?: number | null) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录态失效，请重新登录');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API_BASE_URL}/game/admin/runs/options`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const payload = await resp.json().catch(() => ({}));
        throw new Error(payload.detail || '读取对局列表失败');
      }
      const payload = (await resp.json()) as AdminRunOptionsResponse;
      const nextRuns = payload.runs ?? [];
      setRuns(nextRuns);
      setRefreshTs(Date.now());
      setSelectedRunId((current) => {
        const candidate = preferredRunId ?? current;
        if (candidate && nextRuns.some((item) => item.run_id === candidate)) {
          return candidate;
        }
        return nextRuns[0]?.run_id ?? null;
      });
      setCustomDays((current) => {
        const next: Record<number, number> = {};
        nextRuns.forEach((item) => {
          next[item.run_id] = current[item.run_id] ?? 7;
        });
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '读取对局列表失败');
      setRuns([]);
    } finally {
      setLoading(false);
    }
  };

  const submitRunAction = async (run: AdminRunOption, extendDays: number) => {
    const safeDays = Math.max(1, Math.floor(extendDays));
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录态失效，请重新登录');
      return;
    }
    const isFinished = run.status === 'finished';
    setSubmittingRunId(run.run_id);
    setError('');
    setSuccessMessage('');
    try {
      const resp = await fetch(
        `${API_BASE_URL}/game/admin/runs/${run.run_id}/${isFinished ? 'renew' : 'extend'}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ extend_days: safeDays }),
        },
      );
      if (!resp.ok) {
        const payload = await resp.json().catch(() => ({}));
        throw new Error(payload.detail || (isFinished ? '续期对局失败' : '延长对局失败'));
      }

      if (isFinished) {
        const payload = (await resp.json()) as RenewRunResponse;
        setSuccessMessage(
          `对局 #${payload.run_id} 已续期 ${safeDays} 天，状态 ${payload.old_status} → ${payload.new_status}，总游戏日更新为 ${payload.new_total_game_days} 天，新结束时间为 ${new Date(payload.new_end_time).toLocaleString()}`,
        );
      } else {
        const payload = (await resp.json()) as ExtendRunResponse;
        setSuccessMessage(
          `对局 #${payload.run_id} 已从 ${payload.old_duration_days} 天延长到 ${payload.new_duration_days} 天，总游戏日从 ${payload.old_total_game_days} 天更新为 ${payload.new_total_game_days} 天，新的结束时间为 ${new Date(payload.new_end_time).toLocaleString()}`,
        );
      }
      await loadRuns(run.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : isFinished ? '续期对局失败' : '延长对局失败');
    } finally {
      setSubmittingRunId(null);
    }
  };

  useEffect(() => {
    void loadRuns();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const filteredRuns = useMemo(() => {
    const keyword = usernameKeyword.trim().toLowerCase();
    if (!keyword) return runs;
    return runs.filter((item) => item.username.toLowerCase().includes(keyword));
  }, [runs, usernameKeyword]);

  const selectedRun = useMemo(
    () => filteredRuns.find((item) => item.run_id === selectedRunId) ?? filteredRuns[0] ?? null,
    [filteredRuns, selectedRunId],
  );

  const runningCount = useMemo(() => runs.filter((item) => item.status === 'running').length, [runs]);
  const finishedCount = useMemo(() => runs.filter((item) => item.status === 'finished').length, [runs]);
  const selectedRunRemainingSeconds = selectedRun ? getRunRemainingSeconds(selectedRun, nowMs) : 0;

  useEffect(() => {
    onRunContextChange?.({
      runId: selectedRun?.run_id ?? null,
      username: selectedRun?.username ?? null,
      status: selectedRun?.status ?? null,
      market: selectedRun?.market ?? null,
      dayIndex: selectedRun?.day_index ?? null,
      createdAt: selectedRun?.created_at ?? null,
      durationDays: selectedRun?.duration_days ?? null,
      baseRealDurationDays: selectedRun?.base_real_duration_days ?? null,
      baseGameDays: selectedRun?.base_game_days ?? null,
      totalGameDays: selectedRun?.total_game_days ?? null,
      manualEndTime: selectedRun?.manual_end_time ?? null,
      endTime: selectedRun?.end_time ?? null,
      gameClock: null,
    });
  }, [selectedRun, onRunContextChange]);

  return (
    <div className={embedded ? 'w-full' : 'fixed inset-0 overflow-y-auto bg-[#eef3fb] p-6 custom-scrollbar'}>
      <div className={embedded ? 'w-full' : 'mx-auto max-w-[1680px]'}>
        <div className="rounded-2xl border border-[#d8e5ff] bg-white px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="inline-flex items-center gap-2 text-[18px] font-black text-slate-800">
                <ShieldCheck size={18} className="text-[#2563eb]" />
                超级管理员 · 对局管理
              </div>
              <div className="mt-1 text-[13px] text-slate-500">
                当前账号：{displayName} ｜ 仅 `super_admin` 可访问
              </div>
            </div>
            <div className="flex items-center gap-2">
              {!embedded && onBackToSetup && (
                <button
                  type="button"
                  onClick={onBackToSetup}
                  className="h-10 rounded-xl border border-slate-200 px-4 text-[13px] font-semibold text-slate-600 hover:bg-slate-50"
                >
                  返回工作台
                </button>
              )}
              <button
                type="button"
                onClick={() => void loadRuns(selectedRunId)}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-[#2563eb] px-4 text-[13px] font-semibold text-white hover:bg-[#1d4ed8]"
              >
                <RefreshCw size={14} />
                刷新
              </button>
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-4 gap-4">
          <div className="rounded-2xl border border-[#dbeafe] bg-white p-4">
            <div className="text-[12px] text-slate-500">运行中对局数</div>
            <div className="mt-2 text-[28px] font-black text-[#1e3a8a]">{runningCount}</div>
          </div>
          <div className="rounded-2xl border border-[#dbeafe] bg-white p-4">
            <div className="text-[12px] text-slate-500">已结束对局数</div>
            <div className="mt-2 text-[28px] font-black text-[#1e3a8a]">{finishedCount}</div>
          </div>
          <div className="rounded-2xl border border-[#dbeafe] bg-white p-4">
            <div className="text-[12px] text-slate-500">当前选中对局</div>
            <div className="mt-2 text-[28px] font-black text-[#1e3a8a]">#{selectedRun?.run_id ?? '--'}</div>
          </div>
          <div className="rounded-2xl border border-[#dbeafe] bg-white p-4">
            <div className="text-[12px] text-slate-500">最近刷新</div>
            <div className="mt-2 inline-flex items-center gap-2 text-[18px] font-black text-[#1e3a8a]">
              <CalendarClock size={16} />
              {new Date(refreshTs).toLocaleTimeString()}
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-[13px] text-rose-600">
            {error}
          </div>
        )}
        {successMessage && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-[13px] text-emerald-700">
            {successMessage}
          </div>
        )}

        <div className="mt-4 overflow-hidden rounded-2xl border border-[#dbeafe] bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-[#f8fbff] px-5 py-4">
            <div>
              <div className="text-[13px] font-semibold text-slate-700">对局列表</div>
              <div className="mt-1 text-[12px] text-slate-500">支持按玩家账号快速筛选，并可点击整行切换右侧详情。</div>
            </div>
            <div className="flex w-full max-w-[320px] items-center gap-2 rounded-xl border border-[#dbeafe] bg-white px-3 py-2">
              <span className="text-[12px] font-semibold text-slate-500">账号筛选</span>
              <input
                type="text"
                value={usernameKeyword}
                onChange={(event) => setUsernameKeyword(event.target.value)}
                placeholder="输入玩家账号"
                className="h-8 flex-1 bg-transparent text-[13px] text-slate-700 outline-none placeholder:text-slate-400"
              />
            </div>
          </div>
          <div className="overflow-x-auto custom-scrollbar">
            <div className="min-w-[1360px]">
              <div className="grid grid-cols-[96px_1.35fr_0.9fr_0.9fr_0.95fr_0.95fr_1.4fr_1.4fr_1.8fr] gap-x-4 bg-[#f8fbff] px-5 py-3 text-[12px] font-semibold text-slate-500">
                <div>选择 / 对局ID</div>
                <div>玩家</div>
                <div>市场</div>
                <div>状态</div>
                <div>真实总周期</div>
                <div>当前Day</div>
                <div>创建时间</div>
                <div>结束时间</div>
                <div>操作</div>
              </div>
              <div className="max-h-[620px] overflow-y-auto custom-scrollbar">
                {loading && filteredRuns.length === 0 && (
                  <div className="px-5 py-8 text-[13px] text-slate-500">加载中...</div>
                )}
                {!loading && filteredRuns.length === 0 && (
                  <div className="px-5 py-8 text-[13px] text-slate-500">未找到匹配的玩家对局</div>
                )}
                {filteredRuns.map((run) => {
                  const active = selectedRun?.run_id === run.run_id;
                  const currentCustomDays = customDays[run.run_id] ?? 7;
                  const busy = submittingRunId === run.run_id;
                  const isFinished = run.status === 'finished';
                  const actionLabel = isFinished ? '续期' : '延长';
                  return (
                    <div
                      key={run.run_id}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedRunId(run.run_id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          setSelectedRunId(run.run_id);
                        }
                      }}
                      className={`grid grid-cols-[96px_1.35fr_0.9fr_0.9fr_0.95fr_0.95fr_1.4fr_1.4fr_1.8fr] items-center gap-x-4 border-t border-slate-100 px-5 py-4 text-[13px] transition ${
                        active ? 'bg-blue-50/80' : 'bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className={`flex h-5 w-5 items-center justify-center rounded border text-[12px] font-bold ${
                            active
                              ? 'border-[#2563eb] bg-[#2563eb] text-white'
                              : 'border-slate-300 bg-white text-transparent'
                          }`}
                        >
                          ✓
                        </span>
                        <span className="font-bold text-[#2563eb]">#{run.run_id}</span>
                      </div>
                      <div className="font-semibold text-slate-800">{run.username}</div>
                      <div className="text-slate-700">{run.market}</div>
                      <div>
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${getRunStatusTone(run.status)}`}>
                          {run.status}
                        </span>
                      </div>
                      <div className="text-slate-700">{run.duration_days} 天</div>
                      <div className="text-slate-700">Day {run.day_index}</div>
                      <div className="text-slate-500">{new Date(run.created_at).toLocaleString()}</div>
                      <div className="text-slate-500">{new Date(run.end_time).toLocaleString()}</div>
                      <div
                        className="flex items-center justify-start"
                        onClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => event.stopPropagation()}
                      >
                        <div className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1.5 shadow-sm">
                          <input
                            type="number"
                            min={1}
                            step={1}
                            value={currentCustomDays}
                            onFocus={() => setSelectedRunId(run.run_id)}
                            onChange={(event) => {
                              const next = Number(event.target.value);
                              setCustomDays((current) => ({
                                ...current,
                                [run.run_id]: Number.isFinite(next) ? Math.max(1, Math.floor(next)) : 1,
                              }));
                            }}
                            className="h-8 w-20 rounded border border-slate-200 px-2 text-[12px] font-semibold text-slate-700 outline-none"
                          />
                          <span className="text-[12px] text-slate-500">天</span>
                          <button
                            type="button"
                            onClick={() => void submitRunAction(run, currentCustomDays)}
                            disabled={busy}
                            className="rounded-md bg-[#2563eb] px-3 py-2 text-[12px] font-semibold text-white hover:bg-[#1d4ed8] disabled:opacity-50"
                          >
                            {busy ? '提交中...' : `${actionLabel}提交`}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-[#dbeafe] bg-white p-4 text-[13px] text-slate-600">
          <div className="font-black text-slate-800">选中对局摘要</div>
          <div className="mt-2 grid grid-cols-4 gap-3 text-[12px]">
            <div className="rounded-xl bg-slate-50 px-3 py-2">玩家：{selectedRun?.username ?? '--'}</div>
            <div className="rounded-xl bg-slate-50 px-3 py-2">状态：{selectedRun?.status ?? '--'}</div>
            <div className="rounded-xl bg-slate-50 px-3 py-2">基础游戏日：{selectedRun?.base_game_days ?? '--'}</div>
            <div className="rounded-xl bg-slate-50 px-3 py-2">总游戏日：{selectedRun?.total_game_days ?? '--'}</div>
          </div>
          <div className="mt-2 text-[12px] text-slate-500">
            运行中对局使用延长接口；已结束对局使用续期接口，便于在右侧时间中心查看 finished-run renew 后的最新时间轴。
          </div>
          {selectedRun && (
            <div className="mt-2 text-[12px] text-slate-500">
              结束时间：{new Date(selectedRun.end_time).toLocaleString()} ｜ 实际周期：{selectedRun.duration_days} 天 ｜ 基准真实周期：{selectedRun.base_real_duration_days} 天
            </div>
          )}
          {selectedRun?.status === 'running' && (
            <div className="mt-1 text-[12px] text-slate-500">当前剩余：{fmtDurationSeconds(selectedRunRemainingSeconds)}</div>
          )}
        </div>
      </div>
    </div>
  );
}
