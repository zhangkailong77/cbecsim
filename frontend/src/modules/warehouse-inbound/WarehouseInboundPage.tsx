import { CalendarClock, CheckCircle2, CircleDot, PackageCheck, Warehouse } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import logoImg from '../../assets/home/logo.png';
import {
  BUYER_ZONES_MY,
  WarehouseLocationKey,
  WarehouseModeKey,
  calcZoneForecast,
} from '../sim/buyerZones';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';
const BASE_WIDTH = 1920;
const BASE_HEIGHT = 1080;

const WAREHOUSE_POINTS: Record<WarehouseLocationKey, { label: string; lngLat: [number, number]; note: string }> = {
  near_kl: {
    label: '近吉隆坡仓位',
    lngLat: [101.7068, 3.1543],
    note: '时效快 · 成本高',
  },
  far_kl: {
    label: '远吉隆坡仓位',
    lngLat: [101.3867, 2.9909],
    note: '时效略慢 · 成本低',
  },
};

const MODE_META: Record<WarehouseModeKey, { label: string; markerClass: string }> = {
  official: {
    label: '官方仓',
    markerClass: 'bg-blue-600 rounded-full',
  },
  third_party: {
    label: '第三方仓',
    markerClass: 'bg-cyan-500 rounded-full',
  },
  self_built: {
    label: '自建仓',
    markerClass: 'bg-indigo-700 rounded-[3px]',
  },
};

type WarehouseModePoint = { id: string; name: string; lngLat: [number, number] };
type WarehouseModePointsMap = Record<
  WarehouseLocationKey,
  Record<WarehouseModeKey, WarehouseModePoint[]>
>;

const EMPTY_WAREHOUSE_MODE_POINTS: WarehouseModePointsMap = {
  near_kl: {
    official: [],
    third_party: [],
    self_built: [],
  },
  far_kl: {
    official: [],
    third_party: [],
    self_built: [],
  },
};

interface WarehouseInboundPageProps {
  run: {
    id: number;
    market: string;
    initial_cash: number;
  } | null;
  currentUser: {
    username: string;
    full_name: string | null;
  } | null;
  onBackToSetup: () => void;
  onEnterShopee: () => void;
}

interface ProcurementSummary {
  total_cash: number;
  remaining_cash: number;
}

interface WarehouseModeOption {
  key: WarehouseModeKey;
  label: string;
  one_time_base: number;
  inbound_rate: number;
  rent_base: number;
  delivery_eta_score: number;
  fulfillment_accuracy: number;
  warehouse_cost_per_order: number;
}

interface WarehouseLocationOption {
  key: WarehouseLocationKey;
  label: string;
  rent_delta: number;
  eta_delta: number;
}

interface WarehouseOptionsResp {
  warehouse_modes: WarehouseModeOption[];
  warehouse_locations: WarehouseLocationOption[];
}

interface WarehouseLandmarkPointResp {
  point_code: string;
  point_name: string;
  warehouse_mode: WarehouseModeKey;
  warehouse_location: WarehouseLocationKey;
  lng: number;
  lat: number;
  sort_order: number;
}

interface WarehouseLandmarksResp {
  market: string;
  points: WarehouseLandmarkPointResp[];
}

function buildWarehouseModePoints(points: WarehouseLandmarkPointResp[] | undefined): WarehouseModePointsMap {
  if (!points || points.length === 0) return EMPTY_WAREHOUSE_MODE_POINTS;

  const next: WarehouseModePointsMap = {
    near_kl: { official: [], third_party: [], self_built: [] },
    far_kl: { official: [], third_party: [], self_built: [] },
  };
  const sorted = [...points].sort((a, b) => {
    if (a.warehouse_location !== b.warehouse_location) return a.warehouse_location.localeCompare(b.warehouse_location);
    if (a.warehouse_mode !== b.warehouse_mode) return a.warehouse_mode.localeCompare(b.warehouse_mode);
    return a.sort_order - b.sort_order;
  });
  for (const row of sorted) {
    const loc = row.warehouse_location;
    const mode = row.warehouse_mode;
    if (!(loc in next) || !(mode in next[loc])) continue;
    next[loc][mode].push({
      id: row.point_code,
      name: row.point_name,
      lngLat: [row.lng, row.lat],
    });
  }
  (Object.keys(next) as WarehouseLocationKey[]).forEach((loc) => {
    (Object.keys(next[loc]) as WarehouseModeKey[]).forEach((mode) => {
      next[loc][mode] = next[loc][mode];
    });
  });
  return next;
}

interface CandidateItem {
  shipment_id: number;
  cargo_value: number;
  total_quantity: number;
  created_at: string;
  forwarder_label: string;
  customs_label: string;
  status: string;
}

interface CandidatesResp {
  candidates: CandidateItem[];
}

interface WarehouseSummaryResp {
  strategy: {
    id: number;
    warehouse_mode: WarehouseModeKey;
    warehouse_location: WarehouseLocationKey;
    one_time_cost: number;
    inbound_cost: number;
    rent_cost: number;
    total_cost: number;
    delivery_eta_score: number;
    fulfillment_accuracy: number;
    warehouse_cost_per_order: number;
    created_at: string;
  } | null;
  pending_inbound_count: number;
  completed_inbound_count: number;
  inventory_total_quantity: number;
  inventory_total_sku: number;
}

const fmtMoney = (n: number) => `${Math.max(0, Math.round(n)).toLocaleString()} RMB`;

export default function WarehouseInboundPage({ run, currentUser, onBackToSetup, onEnterShopee }: WarehouseInboundPageProps) {
  const [scale, setScale] = useState(1);
  const [options, setOptions] = useState<WarehouseOptionsResp | null>(null);
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [summary, setSummary] = useState<WarehouseSummaryResp | null>(null);
  const [procurementSummary, setProcurementSummary] = useState<ProcurementSummary | null>(null);
  const [warehouseModePoints, setWarehouseModePoints] = useState<WarehouseModePointsMap>(EMPTY_WAREHOUSE_MODE_POINTS);
  const [selectedMode, setSelectedMode] = useState<WarehouseModeKey>('official');
  const [selectedLocation, setSelectedLocation] = useState<WarehouseLocationKey>('near_kl');
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const playerDisplayName = currentUser?.full_name?.trim() || currentUser?.username || '玩家';

  useEffect(() => {
    const resize = () => {
      const vw = document.documentElement.clientWidth;
      const vh = document.documentElement.clientHeight;
      const ws = vw / BASE_WIDTH;
      const hs = vh / BASE_HEIGHT;
      setScale(Math.max(ws, hs));
    };
    window.addEventListener('resize', resize);
    resize();
    return () => window.removeEventListener('resize', resize);
  }, []);

  const loadData = async () => {
    if (!run?.id) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;

    const [optResp, candResp, summaryResp, cashResp, landmarksResp] = await Promise.all([
      fetch(`${API_BASE_URL}/game/runs/${run.id}/warehouse/options`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetch(`${API_BASE_URL}/game/runs/${run.id}/warehouse/inbound-candidates`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetch(`${API_BASE_URL}/game/runs/${run.id}/warehouse/summary`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetch(`${API_BASE_URL}/game/runs/${run.id}/procurement/cart-summary`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetch(`${API_BASE_URL}/game/runs/${run.id}/warehouse/landmarks`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    ]);

    if (optResp.ok) {
      const data = (await optResp.json()) as WarehouseOptionsResp;
      setOptions(data);
    }
    if (candResp.ok) {
      const data = (await candResp.json()) as CandidatesResp;
      setCandidates(data.candidates);
    }
    if (summaryResp.ok) {
      const data = (await summaryResp.json()) as WarehouseSummaryResp;
      setSummary(data);
      if (data.strategy) {
        setSelectedMode(data.strategy.warehouse_mode);
        setSelectedLocation(data.strategy.warehouse_location);
      }
    }
    if (cashResp.ok) {
      const data = (await cashResp.json()) as ProcurementSummary;
      setProcurementSummary(data);
    }
    if (landmarksResp.ok) {
      const data = (await landmarksResp.json()) as WarehouseLandmarksResp;
      setWarehouseModePoints(buildWarehouseModePoints(data.points));
    } else {
      setWarehouseModePoints(EMPTY_WAREHOUSE_MODE_POINTS);
    }
  };

  useEffect(() => {
    void loadData();
  }, [run?.id]);

  const modeOption = useMemo(
    () => options?.warehouse_modes.find((item) => item.key === selectedMode) ?? options?.warehouse_modes[0] ?? null,
    [options, selectedMode],
  );
  const locationOption = useMemo(
    () => options?.warehouse_locations.find((item) => item.key === selectedLocation) ?? options?.warehouse_locations[0] ?? null,
    [options, selectedLocation],
  );
  const currentModePoints = useMemo(
    () => warehouseModePoints[selectedLocation][selectedMode] ?? [],
    [warehouseModePoints, selectedLocation, selectedMode],
  );

  useEffect(() => {
    setSelectedPointId(currentModePoints[0]?.id ?? null);
  }, [currentModePoints]);

  const cargoTotal = useMemo(() => candidates.reduce((sum, item) => sum + item.cargo_value, 0), [candidates]);
  const qtyTotal = useMemo(() => candidates.reduce((sum, item) => sum + item.total_quantity, 0), [candidates]);
  const isFirstSelfBuilt = selectedMode === 'self_built' && !summary?.strategy;
  const oneTimeCost = modeOption ? (isFirstSelfBuilt ? modeOption.one_time_base : 0) : 0;
  const inboundCost = modeOption ? Math.round(cargoTotal * modeOption.inbound_rate) : 0;
  const rentCost = modeOption && locationOption ? Math.max(0, modeOption.rent_base + locationOption.rent_delta) : 0;
  const totalCost = oneTimeCost + inboundCost + rentCost;
  const cashRemain = procurementSummary?.remaining_cash ?? 0;
  const cashAfter = cashRemain - totalCost;
  const canConfirm = Boolean(run?.id && modeOption && locationOption && candidates.length > 0 && cashAfter >= 0 && !submitting);
  const disableReason = useMemo(() => {
    if (!modeOption || !locationOption) return '请先完成仓型与仓位选择。';
    if (candidates.length <= 0) return '当前没有已清关完成的物流单，无法入仓。';
    if (cashAfter < 0) return `资金不足，还差 ${fmtMoney(-cashAfter)}。`;
    if (submitting) return '正在提交，请稍候...';
    return '';
  }, [modeOption, locationOption, candidates.length, cashAfter, submitting]);

  const compareAgainstCurrent = useMemo(() => {
    if (!summary?.strategy || !modeOption || !locationOption) return null;
    const base = summary.strategy;
    const nextEta = Math.max(1, Math.min(100, (modeOption.delivery_eta_score ?? 0) + (locationOption.eta_delta ?? 0)));
    return {
      deltaCost: totalCost - base.total_cost,
      deltaEtaScore: nextEta - base.delivery_eta_score,
      deltaAccuracy: modeOption.fulfillment_accuracy - base.fulfillment_accuracy,
    };
  }, [summary?.strategy, modeOption, locationOption, totalCost]);
  const zoneForecast = useMemo(() => calcZoneForecast(selectedMode, selectedLocation), [selectedMode, selectedLocation]);

  const handleConfirmInbound = async () => {
    if (!run?.id || !modeOption || !locationOption) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    if (!canConfirm) {
      setError('请先选择完整仓型/仓位，并确保有清关完成物流单且资金足够。');
      return;
    }

    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      const strategyResp = await fetch(`${API_BASE_URL}/game/runs/${run.id}/warehouse/strategy`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          warehouse_mode: modeOption.key,
          warehouse_location: locationOption.key,
        }),
      });
      if (!strategyResp.ok) {
        const data = await strategyResp.json().catch(() => ({}));
        setError(data.detail || '仓策略保存失败。');
        return;
      }

      const inboundResp = await fetch(`${API_BASE_URL}/game/runs/${run.id}/warehouse/inbound`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          shipment_ids: [],
        }),
      });
      if (!inboundResp.ok) {
        const data = await inboundResp.json().catch(() => ({}));
        setError(data.detail || '入仓失败。');
        return;
      }
      setSuccess('已按当前策略一次性完成全部可入仓物流单入仓。');
      await loadData();
    } catch {
      setError('入仓提交失败，请检查网络后重试。');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 overflow-hidden bg-[#eef4ff]">
      <div
        style={{
          width: `${BASE_WIDTH}px`,
          height: `${BASE_HEIGHT}px`,
          transform: `scale(${scale})`,
          transformOrigin: 'top left',
          position: 'absolute',
          left: 0,
          top: 0,
        }}
        className="bg-[#eef4ff]"
      >
        <header className="h-[78px] border-b border-[#e5ecfb] bg-white px-5">
          <div className="flex h-full items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative h-11 w-11">
                <span className="logo-breathe absolute inset-[-7px] rounded-full bg-blue-400/30 blur-lg" />
                <span className="logo-breathe logo-breathe-delay absolute inset-[-13px] rounded-full bg-cyan-300/20 blur-xl" />
                <div className="relative h-11 w-11 overflow-hidden rounded-full border border-blue-100 bg-white p-1 shadow-[0_8px_24px_rgba(37,99,235,0.22)]">
                  <img src={logoImg} alt="CbecSim" className="h-full w-full rounded-full object-cover" />
                </div>
              </div>
              <div>
                <div className="text-[30px] font-black leading-none text-[#2563eb]">CbecSim</div>
                <div className="-mt-0.5 text-[12px] font-semibold text-[#60a5fa]">跨境运营仿真平台</div>
              </div>
            </div>

            <div className="flex items-center gap-3 text-[13px] font-semibold text-slate-700">
              <div className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-blue-700">STEP 04 海外仓选择与入仓</div>
              <div className="rounded-full border border-slate-200 px-3 py-1.5">玩家：{playerDisplayName}</div>
              <div className="rounded-full border border-slate-200 px-3 py-1.5">局 #{run?.id ?? '-'}</div>
              <button onClick={onBackToSetup} className="rounded-full border border-slate-200 px-4 py-1.5">
                返回工作台
              </button>
              <button
                onClick={onEnterShopee}
                disabled={(summary?.completed_inbound_count ?? 0) <= 0}
                className="rounded-full bg-[#2563eb] px-5 py-1.5 text-white disabled:cursor-not-allowed disabled:opacity-40"
                title={(summary?.completed_inbound_count ?? 0) > 0 ? '' : '至少完成 1 票入仓后可进入运营'}
              >
                进入运营
              </button>
            </div>
          </div>
        </header>

        <main className="h-[calc(1080px-78px)] overflow-auto p-5">
          <div className="mb-4 rounded-2xl border border-[#dbeafe] bg-gradient-to-r from-[#eff6ff] to-[#f8fbff] px-5 py-4 text-[14px] text-[#1e3a8a]">
            Step 04 需要先选择仓型与仓位，再一次性将“已清关完成”的物流单全部入仓，生成后续运营库存能力参数。
          </div>

          <div className="grid grid-cols-[360px_1fr_430px] gap-4">
            <section className="rounded-2xl border border-[#e5ecfb] bg-white p-4">
              <div className="mb-3 text-[17px] font-black text-slate-800">A. 仓型方案（3选1）</div>
              <div className="space-y-3">
                {(options?.warehouse_modes ?? []).map((mode) => {
                  const active = mode.key === selectedMode;
                  return (
                    <button
                      key={mode.key}
                      type="button"
                      onClick={() => setSelectedMode(mode.key)}
                      className={`w-full rounded-xl border p-3 text-left ${active ? 'border-blue-300 bg-blue-50' : 'border-slate-200 bg-white'}`}
                    >
                      <div className="text-[14px] font-black text-slate-800">{mode.label}</div>
                      <div className="mt-1 text-[12px] text-slate-500">
                        入仓费率 {(mode.inbound_rate * 100).toFixed(2)}% · 仓租基准 {fmtMoney(mode.rent_base)}
                      </div>
                      <div className="mt-1 text-[12px] text-slate-500">
                        准确率 {(mode.fulfillment_accuracy * 100).toFixed(1)}% · 单单成本 {fmtMoney(mode.warehouse_cost_per_order)}
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="rounded-2xl border border-[#e5ecfb] bg-white p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-[17px] font-black text-slate-800">B. 真实地图仓位选择（马来）</div>
                <div className="text-[12px] text-slate-500">目标市场 {run?.market ?? 'MY'}</div>
              </div>
              <RealMalaysiaMap
                selectedMode={selectedMode}
                selectedLocation={selectedLocation}
                selectedPointId={selectedPointId}
                warehouseModePoints={warehouseModePoints}
                modeOptions={options?.warehouse_modes ?? []}
                locationOptions={options?.warehouse_locations ?? []}
                onSelectPoint={(mode, location) => {
                  setSelectedMode(mode);
                  setSelectedLocation(location);
                }}
                onTogglePoint={(pointId) => {
                  setSelectedPointId((prev) => (prev === pointId ? null : pointId));
                }}
              />
              <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/70 px-3 py-2 text-[12px] text-slate-600">
                已选方案：{modeOption?.label ?? '--'} · {locationOption?.label ?? '--'}；支持拖拽、滚轮缩放与点位点击联动选择。
              </div>
              <div className="mt-3 rounded-xl border border-blue-100 bg-white p-3">
                <div className="mb-2 text-[13px] font-bold text-slate-800">
                  当前仓型地标点位（{modeOption?.label ?? '--'} · {locationOption?.label ?? '--'}）
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {currentModePoints.length === 0 && (
                    <div className="col-span-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-700">
                      当前仓型未配置地标点，请先在数据库 `warehouse_landmarks` 表中维护该仓型点位。
                    </div>
                  )}
                  {currentModePoints.map((point, idx) => (
                    <button
                      key={point.id}
                      type="button"
                      onClick={() => setSelectedPointId((prev) => (prev === point.id ? null : point.id))}
                      className={`rounded-lg border px-2.5 py-2 text-left text-[12px] transition ${
                        selectedPointId === point.id
                          ? 'border-blue-300 bg-blue-50 shadow-[0_0_0_4px_rgba(37,99,235,0.12)]'
                          : 'border-slate-200 bg-slate-50 hover:border-blue-200 hover:bg-blue-50/60'
                      }`}
                    >
                      <div className="font-semibold text-slate-700">点位 {idx + 1} · {point.name}</div>
                      <div className="mt-1 text-slate-500">Lng: {point.lngLat[0].toFixed(5)}</div>
                      <div className="text-slate-500">Lat: {point.lngLat[1].toFixed(5)}</div>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <aside className="space-y-4">
              <section className="rounded-2xl border border-[#e5ecfb] bg-white p-4">
                <div className="mb-3 text-[17px] font-black text-slate-800">C. 入仓决策面板</div>
                <div className="mb-3 rounded-xl border border-blue-100 bg-blue-50/70 px-3 py-2">
                  <div className="text-[12px] font-semibold text-slate-700">选择进度（2步）</div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-blue-100">
                    <div
                      className="h-full rounded-full bg-blue-500 transition-all"
                      style={{ width: `${((modeOption ? 1 : 0) + (locationOption ? 1 : 0)) * 50}%` }}
                    />
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500">
                    第1步仓型：{modeOption ? '已完成' : '未完成'}；第2步仓位：{locationOption ? '已完成' : '未完成'}
                  </div>
                </div>
                <div className="space-y-2 text-[13px]">
                  <KV label="待入仓物流单" value={`${candidates.length} 单`} icon={<PackageCheck size={14} />} />
                  <KV label="待入仓件数" value={`${qtyTotal.toLocaleString()} 件`} />
                  <KV label="待入仓货值" value={fmtMoney(cargoTotal)} />
                  <KV label="一次性费用" value={fmtMoney(oneTimeCost)} />
                  <KV label="入仓处理费" value={fmtMoney(inboundCost)} />
                  <KV label="仓租周期费用" value={fmtMoney(rentCost)} />
                  <KV label="本次总仓储费用" value={fmtMoney(totalCost)} strong />
                  <KV label="预计配送时效分" value={`${Math.max(1, Math.min(100, (modeOption?.delivery_eta_score ?? 0) + (locationOption?.eta_delta ?? 0)))}`} icon={<CalendarClock size={14} />} />
                  <KV label="履约准确率" value={`${(((modeOption?.fulfillment_accuracy ?? 0) * 100)).toFixed(1)}%`} icon={<CheckCircle2 size={14} />} />
                  <KV label="预计平均配送时长" value={`${zoneForecast.avgDeliveryDays.toFixed(2)} 天`} />
                  <KV label="超时率（热区加权）" value={`${(zoneForecast.overdueRate * 100).toFixed(1)}%`} danger={zoneForecast.overdueRate > 0.25} />
                  <KV label="退款风险（热区加权）" value={`${(zoneForecast.refundRisk * 100).toFixed(1)}%`} danger={zoneForecast.refundRisk > 0.08} />
                  <KV label="预计评分" value={`${zoneForecast.expectedRating.toFixed(2)} / 5`} success={zoneForecast.expectedRating >= 4.4} />
                  <KV label="扣款后余额" value={fmtMoney(cashAfter)} success={cashAfter >= 0} danger={cashAfter < 0} />
                </div>
                {compareAgainstCurrent && (
                  <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px]">
                    <div className="font-semibold text-slate-700">与当前生效方案对比</div>
                    <div className="mt-1 text-slate-600">
                      总成本 {compareAgainstCurrent.deltaCost >= 0 ? '+' : ''}
                      {compareAgainstCurrent.deltaCost.toLocaleString()} RMB
                    </div>
                    <div className="text-slate-600">
                      时效评分 {compareAgainstCurrent.deltaEtaScore >= 0 ? '+' : ''}
                      {compareAgainstCurrent.deltaEtaScore}
                    </div>
                    <div className="text-slate-600">
                      准确率 {compareAgainstCurrent.deltaAccuracy >= 0 ? '+' : ''}
                      {(compareAgainstCurrent.deltaAccuracy * 100).toFixed(1)}%
                    </div>
                  </div>
                )}
                {error && <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-2 py-1.5 text-[12px] text-rose-600">{error}</div>}
                {success && <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-[12px] text-emerald-700">{success}</div>}
                <button
                  type="button"
                  onClick={handleConfirmInbound}
                  disabled={!canConfirm}
                  className="mt-3 h-10 w-full rounded-xl bg-[#2563eb] text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  确认入仓并生效（全部入仓）
                </button>
                {!canConfirm && <div className="mt-2 text-[12px] text-rose-600">{disableReason}</div>}
              </section>

              <section className="rounded-2xl border border-[#e5ecfb] bg-white p-4">
                <div className="mb-2 text-[15px] font-black text-slate-800">D. 入仓进度与汇总</div>
                <div className="space-y-2 text-[13px]">
                  <KV label="已入仓批次" value={`${summary?.completed_inbound_count ?? 0} 单`} icon={<Warehouse size={14} />} />
                  <KV label="库存 SKU" value={`${summary?.inventory_total_sku ?? 0}`} />
                  <KV label="库存总件数" value={`${(summary?.inventory_total_quantity ?? 0).toLocaleString()} 件`} />
                </div>
                <div className="mt-3 max-h-[220px] overflow-auto rounded-xl border border-slate-100">
                  <table className="w-full text-left text-[12px]">
                    <thead className="bg-slate-50 text-slate-500">
                      <tr>
                        <th className="px-2 py-1.5">物流单</th>
                        <th className="px-2 py-1.5">货值</th>
                        <th className="px-2 py-1.5">件数</th>
                        <th className="px-2 py-1.5">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.length === 0 && (
                        <tr>
                          <td colSpan={4} className="px-2 py-6 text-center text-slate-400">当前无待入仓候选（可能已全部入仓）</td>
                        </tr>
                      )}
                      {candidates.map((item) => (
                        <tr key={item.shipment_id} className="border-t border-slate-100 text-slate-700">
                          <td className="px-2 py-1.5">#{item.shipment_id}</td>
                          <td className="px-2 py-1.5">{fmtMoney(item.cargo_value)}</td>
                          <td className="px-2 py-1.5">{item.total_quantity.toLocaleString()}</td>
                          <td className="px-2 py-1.5">
                            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">
                              <CircleDot size={11} />
                              可入仓
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="rounded-2xl border border-[#e5ecfb] bg-white p-4">
                <div className="mb-2 text-[15px] font-black text-slate-800">E. 买家热区预估（6区）</div>
                <div className="max-h-[240px] overflow-auto rounded-xl border border-slate-100">
                  <table className="w-full text-left text-[12px]">
                    <thead className="bg-slate-50 text-slate-500">
                      <tr>
                        <th className="px-2 py-1.5">热区</th>
                        <th className="px-2 py-1.5">占比</th>
                        <th className="px-2 py-1.5">预估时长</th>
                        <th className="px-2 py-1.5">退款风险</th>
                      </tr>
                    </thead>
                    <tbody>
                      {zoneForecast.zoneRows.map((row) => (
                        <tr key={row.zoneCode} className="border-t border-slate-100 text-slate-700">
                          <td className="px-2 py-1.5">{row.zoneName}</td>
                          <td className="px-2 py-1.5">{(row.orderShare * 100).toFixed(0)}%</td>
                          <td className="px-2 py-1.5">{row.etaDays.toFixed(2)} 天</td>
                          <td className="px-2 py-1.5">{(row.refundRisk * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}

function RealMalaysiaMap({
  selectedMode,
  selectedLocation,
  selectedPointId,
  warehouseModePoints,
  modeOptions,
  locationOptions,
  onSelectPoint,
  onTogglePoint,
}: {
  selectedMode: WarehouseModeKey;
  selectedLocation: WarehouseLocationKey;
  selectedPointId: string | null;
  warehouseModePoints: WarehouseModePointsMap;
  modeOptions: WarehouseModeOption[];
  locationOptions: WarehouseLocationOption[];
  onSelectPoint: (mode: WarehouseModeKey, loc: WarehouseLocationKey) => void;
  onTogglePoint: (pointId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<Record<string, maplibregl.Marker>>({});
  const zoneMarkerRef = useRef<maplibregl.Marker[]>([]);
  const [mapReady, setMapReady] = useState(false);
  const [lineSegments, setLineSegments] = useState<Array<{ id: string; x1: number; y1: number; x2: number; y2: number; w: number }>>([]);
  const activeHubCoord = useMemo(() => {
    if (!selectedPointId) return null;
    return warehouseModePoints[selectedLocation][selectedMode].find((item) => item.id === selectedPointId)?.lngLat ?? null;
  }, [warehouseModePoints, selectedLocation, selectedMode, selectedPointId]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'osm',
            type: 'raster',
            source: 'osm',
          },
        ],
      },
      center: [101.6869, 3.139],
      zoom: 11.2,
      minZoom: 8,
      maxZoom: 17,
      pitch: 0,
      bearing: 0,
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
    mapRef.current = map;
    map.on('load', () => setMapReady(true));

    (Object.keys(warehouseModePoints) as WarehouseLocationKey[]).forEach((location) => {
      (Object.keys(MODE_META) as WarehouseModeKey[]).forEach((mode) => {
        warehouseModePoints[location][mode].forEach((point, idx) => {
          const markerEl = document.createElement('button');
          markerEl.type = 'button';
          markerEl.dataset.mode = mode;
          markerEl.dataset.location = location;
          markerEl.dataset.group = `${mode}:${location}:${point.id}`;
          markerEl.dataset.point = String(idx);
          markerEl.style.cursor = 'pointer';
          markerEl.className = 'warehouse-marker';
          markerEl.style.width = '16px';
          markerEl.style.height = '16px';
          markerEl.style.border = '2px solid #fff';
          markerEl.style.boxSizing = 'border-box';
          markerEl.style.transition = 'opacity .18s ease, box-shadow .18s ease, transform .18s ease';
          markerEl.style.transform = 'translateZ(0)';
          const markerLngLat: [number, number] = point.lngLat;
          markerEl.addEventListener('click', () => {
            onSelectPoint(mode, location);
            onTogglePoint(point.id);
          });

          const modeMeta = modeOptions.find((item) => item.key === mode);
          const locMeta = locationOptions.find((item) => item.key === location);
          const forecast = calcZoneForecast(mode, location);
          const etaScore = Math.max(1, Math.min(100, (modeMeta?.delivery_eta_score ?? 84) + (locMeta?.eta_delta ?? 0)));
          const accuracy = ((modeMeta?.fulfillment_accuracy ?? 0.95) * 100).toFixed(1);
          const popup = new maplibregl.Popup({ offset: 20, closeButton: false, closeOnClick: false }).setHTML(`
            <div style="min-width:220px;font-size:12px;line-height:1.35;">
              <div style="font-weight:800;color:#0f172a;">${MODE_META[mode].label} · ${point.name}</div>
              <div style="margin-top:4px;color:#64748b;">${WAREHOUSE_POINTS[location].note}</div>
              <div style="margin-top:8px;display:grid;grid-template-columns:1fr auto;gap:4px 10px;">
                <span style="color:#64748b;">预计配送时效分</span><b style="color:#1d4ed8;">${etaScore}</b>
                <span style="color:#64748b;">履约准确率</span><b style="color:#16a34a;">${accuracy}%</b>
                <span style="color:#64748b;">预计平均配送时长</span><b>${forecast.avgDeliveryDays.toFixed(2)} 天</b>
                <span style="color:#64748b;">超时率（热区加权）</span><b>${(forecast.overdueRate * 100).toFixed(1)}%</b>
                <span style="color:#64748b;">退款风险（热区加权）</span><b>${(forecast.refundRisk * 100).toFixed(1)}%</b>
              </div>
            </div>
          `);
          const marker = new maplibregl.Marker({ element: markerEl, anchor: 'center' })
            .setLngLat(markerLngLat)
            .setPopup(popup)
            .addTo(map);
          markerEl.addEventListener('mouseenter', () => {
            if (!marker.getPopup()?.isOpen()) marker.togglePopup();
          });
          markerEl.addEventListener('mouseleave', () => {
            if (marker.getPopup()?.isOpen()) marker.togglePopup();
          });
          markerRef.current[`${mode}:${location}:${point.id}`] = marker;
        });
      });
    });

    BUYER_ZONES_MY.forEach((zone) => {
      const zoneEl = document.createElement('div');
      const size = Math.max(12, Math.round(11 + zone.orderShare * 38));
      zoneEl.className = 'relative';
      zoneEl.innerHTML = `
        <span style="
          display:block;
          width:${size}px;
          height:${size}px;
          border-radius:9999px;
          border:2px solid rgba(255,255,255,.95);
          background:rgba(245,158,11,.72);
          box-shadow:0 0 0 6px rgba(245,158,11,.18), 0 8px 16px rgba(217,119,6,.28);
        "></span>
        <span style="
          position:absolute;
          left:${size + 6}px;
          top:50%;
          transform:translateY(-50%);
          padding:1px 6px;
          border-radius:8px;
          border:1px solid rgba(255,255,255,.8);
          background:rgba(255,255,255,.88);
          color:#334155;
          font-size:11px;
          font-weight:700;
          white-space:nowrap;
          backdrop-filter:blur(3px);
        ">${zone.zoneName}</span>
      `;
      const popup = new maplibregl.Popup({ offset: 18 }).setHTML(
        `<div style="font-size:12px;"><b>${zone.zoneName}</b><div style="color:#64748b;margin-top:4px;">订单占比 ${(zone.orderShare * 100).toFixed(0)}% · 时效敏感度 ${(zone.slaSensitivity * 100).toFixed(0)}%</div></div>`,
      );
      const marker = new maplibregl.Marker({ element: zoneEl, anchor: 'center' }).setLngLat(zone.lngLat).setPopup(popup).addTo(map);
      zoneMarkerRef.current.push(marker);
    });

    return () => {
      Object.values(markerRef.current).forEach((marker) => {
        marker.remove();
      });
      markerRef.current = {};
      zoneMarkerRef.current.forEach((marker) => marker.remove());
      zoneMarkerRef.current = [];
      setMapReady(false);
      setLineSegments([]);
      map.remove();
      mapRef.current = null;
    };
  }, [locationOptions, modeOptions, onSelectPoint, onTogglePoint, warehouseModePoints]);

  const recomputeLines = useCallback(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    if (!activeHubCoord) {
      setLineSegments([]);
      return;
    }
    const sourceP = map.project(activeHubCoord);
    const next = BUYER_ZONES_MY.map((zone) => {
      const p = map.project(zone.lngLat);
      return {
        id: zone.zoneCode,
        x1: sourceP.x,
        y1: sourceP.y,
        x2: p.x,
        y2: p.y,
        w: Number((2.6 + zone.orderShare * 10).toFixed(2)),
      };
    });
    setLineSegments(next);
  }, [activeHubCoord, mapReady]);

  useEffect(() => {
    recomputeLines();
  }, [recomputeLines]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const onMove = () => recomputeLines();
    map.on('move', onMove);
    map.on('zoom', onMove);
    map.on('resize', onMove);
    map.on('drag', onMove);
    return () => {
      map.off('move', onMove);
      map.off('zoom', onMove);
      map.off('resize', onMove);
      map.off('drag', onMove);
    };
  }, [mapReady, recomputeLines]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    Object.entries(markerRef.current).forEach(([key, marker]) => {
      const el = marker.getElement();
      const [mode, location] = key.split(':') as [WarehouseModeKey, WarehouseLocationKey, string];
      const sameLocation = location === selectedLocation;
      const isActive = Boolean(selectedPointId && mode === selectedMode && location === selectedLocation && key.endsWith(`:${selectedPointId}`));
      const isDim = mode !== selectedMode;
      el.style.display = sameLocation ? 'block' : 'none';
      if (!sameLocation) {
        return;
      }
      el.style.borderRadius = mode === 'self_built' ? '3px' : '9999px';
      el.style.background = mode === 'official' ? '#2563eb' : mode === 'third_party' ? '#06b6d4' : '#4338ca';
      el.style.opacity = isDim ? '0.35' : '0.92';
      if (isActive) {
        el.style.opacity = '1';
        el.style.boxShadow = '0 0 0 8px rgba(37,99,235,.24), 0 10px 20px rgba(30,64,175,.32)';
      } else {
        el.style.boxShadow = '0 6px 12px rgba(37,99,235,.32)';
      }
    });

    const fallback = warehouseModePoints[selectedLocation][selectedMode][0]?.lngLat;
    const hubPoint = activeHubCoord ?? fallback;
    if (!hubPoint) return;
    map.easeTo({
      center: hubPoint,
      zoom: 10.8,
      duration: 520,
      essential: true,
    });
  }, [activeHubCoord, selectedMode, selectedLocation, selectedPointId, warehouseModePoints]);

  return (
    <div className="relative warehouse-map-wrap">
      <div ref={containerRef} className="h-[520px] overflow-hidden rounded-2xl border border-blue-100" />
      <svg className="pointer-events-none absolute inset-0 z-[5] h-full w-full">
        {lineSegments.map((line) => (
          <g key={line.id}>
            <line
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke="#dbeafe"
              strokeWidth={line.w + 2.8}
              strokeLinecap="round"
              opacity={0.95}
            />
            <line
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke="#2563eb"
              strokeWidth={line.w}
              strokeLinecap="round"
              opacity={0.92}
            />
          </g>
        ))}
      </svg>
      <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-white/70 bg-white/85 px-2 py-1 text-[11px] text-slate-600 backdrop-blur">
        地图可拖拽缩放，点击仓点可切换仓型；将显示该仓到各买家热区的蓝色直连线
      </div>
      <div className="pointer-events-none absolute right-[56px] top-3 rounded-lg border border-white/70 bg-white/85 px-2 py-1 text-[11px] text-slate-600 backdrop-blur">
        <div className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-blue-600" />官方仓</div>
        <div className="inline-flex items-center gap-1 ml-2"><span className="h-2.5 w-2.5 rounded-full bg-cyan-500" />第三方仓</div>
        <div className="inline-flex items-center gap-1 ml-2"><span className="inline-block h-2.5 w-2.5 rotate-45 rounded-[2px] bg-indigo-700" />自建仓</div>
        <div className="inline-flex items-center gap-1 ml-2"><span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500/80" />买家热区</div>
        <div className="inline-flex items-center gap-1 ml-2"><span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-500/90" />热区连线</div>
      </div>
    </div>
  );
}

function KV({
  label,
  value,
  icon,
  strong,
  danger,
  success,
}: {
  label: string;
  value: string;
  icon?: JSX.Element;
  strong?: boolean;
  danger?: boolean;
  success?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="inline-flex items-center gap-1 text-slate-500">
        {icon}
        <span>{label}</span>
      </div>
      <span className={`font-semibold ${strong ? 'text-slate-900' : 'text-slate-700'} ${danger ? 'text-rose-600' : ''} ${success ? 'text-emerald-600' : ''}`}>
        {value}
      </span>
    </div>
  );
}
